# =============================================================================
# ETAPA 3 — VALIDACIÓN ESTRUCTURAL Y SEMÁNTICA
# Pipeline TiendaClick · Evaluación Grupal Unidad 2
#
# Responsabilidades de esta etapa:
#   1. Leer datos limpios desde /data/clean/.
#   2. Validación ESTRUCTURAL con pandera (tipos, rangos, regex) — mínimo 3.
#   3. Validación SEMÁNTICA con reglas de negocio entre columnas — mínimo 2.
#   4. Separar válidos en /data/validated/ e inválidos en /data/errors/
#      con columna motivo_rechazo.
#   5. Logging con descripción de cada validación y su resultado.
#
# Requiere: pip install pandera
# =============================================================================

import logging
import re
from pathlib import Path

import pandas as pd
import pandera.pandas as pa
from pandera import Check, Column

# ─── Rutas del proyecto ──────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
CLEAN_DIR = BASE_DIR / "data" / "clean"
VALIDATED_DIR = BASE_DIR / "data" / "validated"
ERRORS_DIR = BASE_DIR / "data" / "errors"
LOG_DIR = BASE_DIR / "logs"
for d in [VALIDATED_DIR, ERRORS_DIR, LOG_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    filename=LOG_DIR / "validacion.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


# ─── Validación de RUT chileno (dígito verificador, módulo 11) ───────────────
def rut_valido(rut):
    """True si el RUT tiene formato correcto Y dígito verificador válido."""
    if not re.match(r"^\d{7,8}-[\dkK]$", str(rut)):
        return False
    cuerpo, dv = str(rut).split("-")
    # Dígito verificador (módulo 11): se recorre el RUT de derecha a izquierda
    # multiplicando por 2,3,4,5,6,7 y se vuelve a 2 al pasar de 7
    suma, multiplicador = 0, 2
    for digito in reversed(cuerpo):
        suma += int(digito) * multiplicador
        multiplicador = 2 if multiplicador == 7 else multiplicador + 1
    resto = 11 - suma % 11
    dv_calculado = "0" if resto == 11 else "K" if resto == 10 else str(resto)
    return dv_calculado == dv.upper()


# ─── Esquemas pandera (VALIDACIÓN ESTRUCTURAL) ───────────────────────────────
# Descripción legible de cada regla, usada para motivo_rechazo y logging
DESCRIPCION = {
    "edad": "edad fuera de rango 18-110",
    "rut": "RUT inválido (formato o dígito verificador)",
    "email": "email con formato inválido",
    "telefono": "teléfono no cumple formato +569XXXXXXXX",
    "cantidad": "cantidad nula, no numérica o menor a 1",
    "monto_total_clp": "monto nulo o menor o igual a 0",
    "precio_unitario_clp": "precio menor o igual a 0",
    "stock": "stock negativo",
}

ESQUEMA_CLIENTES = pa.DataFrameSchema({
    # 1. Rango numérico
    "edad": Column(float, Check.in_range(18, 110), coerce=True),
    # 2. Formato con regex + dígito verificador (check personalizado)
    "rut": Column(str, Check(lambda s: s.map(rut_valido), element_wise=False)),
    # 3. Formato con regex (nullable: email es opcional)
    "email": Column(str, Check.str_matches(r"^[\w\.\-]+@[\w\-]+\.\w{2,}$"), nullable=True),
    # 4. Formato con regex (nullable: teléfono es opcional)
    "telefono": Column(str, Check.str_matches(r"^\+569\d{8}$"), nullable=True),
})

ESQUEMA_PEDIDOS = pa.DataFrameSchema({
    # 5. Tipo + rango (cantidad ya convertida a numérico antes de validar)
    "cantidad": Column(float, Check.ge(1), nullable=False),
    # 6. Rango numérico
    "monto_total_clp": Column(float, Check.gt(0), nullable=False),
})

ESQUEMA_PRODUCTOS = pa.DataFrameSchema({
    "precio_unitario_clp": Column(int, Check.gt(0), coerce=True),
    "stock": Column(int, Check.ge(0), coerce=True),
})


def validar_estructural(df, esquema, tabla):
    """Valida con pandera (lazy=True revisa TODAS las reglas, no solo la
    primera) y devuelve un dict {indice_fila: [motivos]}."""
    motivos = {}
    try:
        esquema.validate(df, lazy=True)
        logging.info("ESTRUCTURAL OK | tabla=%s | sin infracciones", tabla)
    except pa.errors.SchemaErrors as e:
        casos = e.failure_cases
        for col in casos["column"].dropna().unique():
            indices = casos.loc[casos["column"] == col, "index"].dropna().unique()
            descripcion = DESCRIPCION.get(col, f"{col}: valor inválido")
            for idx in indices:
                motivos.setdefault(int(idx), []).append(descripcion)
            logging.info("ESTRUCTURAL | tabla=%s | regla='%s' | infracciones=%d",
                         tabla, descripcion, len(indices))
            print(f"  [estructural] {descripcion}: {len(indices)} filas")
    return motivos


def aplicar_regla(motivos, mascara, descripcion, tabla):
    """Marca como inválidas las filas donde la máscara es True (regla
    semántica violada) y registra el resultado en el log."""
    indices = mascara[mascara].index
    for idx in indices:
        motivos.setdefault(int(idx), []).append(descripcion)
    logging.info("SEMÁNTICA | tabla=%s | regla='%s' | infracciones=%d",
                 tabla, descripcion, len(indices))
    print(f"  [semántica] {descripcion}: {len(indices)} filas")
    return motivos


def validar_clientes(df):
    """Valida la tabla de clientes (solo estructural: edad, rut, email, fono)."""

    print(f"\n{'=' * 60}\nTABLA: clientes\n{'=' * 60}")
    print(f"Filas a validar: {len(df)}")

    motivos = validar_estructural(df, ESQUEMA_CLIENTES, "clientes")
    return motivos


def validar_pedidos(df, productos, clientes):
    """Valida pedidos: estructural (pandera) + semántica (reglas de negocio)."""

    print(f"\n{'=' * 60}\nTABLA: pedidos\n{'=' * 60}")
    print(f"Filas a validar: {len(df)}")

    # Conversión de tipo previa: cantidad llega como texto ('dos', '3 unidades')
    # to_numeric con coerce los deja NaN y pandera los reporta como inválidos
    df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce")

    # ── ESTRUCTURAL (pandera) ──
    motivos = validar_estructural(df, ESQUEMA_PEDIDOS, "pedidos")

    # ── SEMÁNTICA (reglas de negocio entre columnas) ──
    fecha_pedido = pd.to_datetime(df["fecha_pedido"], errors="coerce")
    fecha_despacho = pd.to_datetime(df["fecha_despacho"], errors="coerce")

    # Regla 1: si estado='entregado', fecha_despacho no puede ser nula
    motivos = aplicar_regla(
        motivos, (df["estado"] == "entregado") & fecha_despacho.isna(),
        "entregado sin fecha_despacho", "pedidos")

    # Regla 2: fecha_despacho debe ser posterior o igual a fecha_pedido
    motivos = aplicar_regla(
        motivos, fecha_despacho < fecha_pedido,
        "fecha_despacho anterior a fecha_pedido", "pedidos")

    # Regla 3: si estado='cancelado', no debería tener fecha_despacho
    motivos = aplicar_regla(
        motivos, (df["estado"] == "cancelado") & fecha_despacho.notna(),
        "cancelado con fecha_despacho", "pedidos")

    # Regla 4 (entre tablas): monto_total_clp == precio_unitario × cantidad
    df_check = df.merge(productos[["id_producto", "precio_unitario_clp"]],
                        on="id_producto", how="left")
    esperado = df_check["precio_unitario_clp"] * df_check["cantidad"]
    motivos = aplicar_regla(
        motivos, (df["monto_total_clp"] - esperado).abs() > 1,
        "monto no coincide con precio x cantidad", "pedidos")

    # Regla 5 — Integridad referencial PRE-CARGA (como en el caso del banco):
    # las FK deben existir en su tabla padre antes de intentar la carga
    motivos = aplicar_regla(
        motivos, ~df["id_cliente"].isin(clientes["id_cliente"]),
        "id_cliente no existe en tabla clientes", "pedidos")
    motivos = aplicar_regla(
        motivos, ~df["id_producto"].isin(productos["id_producto"]),
        "id_producto no existe en tabla productos", "pedidos")

    return motivos


def separar(df, motivos, tabla):
    """Separa válidos (/data/validated/) de inválidos (/data/errors/),
    agregando la columna motivo_rechazo a los inválidos."""

    indices_invalidos = sorted(motivos.keys())
    invalidos = df.loc[indices_invalidos].copy()
    invalidos["motivo_rechazo"] = ["; ".join(motivos[i]) for i in indices_invalidos]
    validos = df.drop(index=indices_invalidos)

    validos.to_csv(VALIDATED_DIR / f"{tabla}.csv", index=False, encoding="utf-8")
    invalidos.to_csv(ERRORS_DIR / f"{tabla}_errores.csv", index=False, encoding="utf-8")

    print(f"Válidos: {len(validos)}  |  Inválidos: {len(invalidos)}")
    print(f"% Validez: {(len(validos)/len(df)*100):.2f}%")
    logging.info("SEPARACIÓN | tabla=%s | total=%d | validos=%d | invalidos=%d",
                 tabla, len(df), len(validos), len(invalidos))
    return validos, invalidos


def validar():
    """Ejecuta la validación completa de las tres tablas."""

    logging.info("INICIO Etapa 3 — Validación Estructural y Semántica")

    try:
        productos = pd.read_csv(CLEAN_DIR / "productos.csv")
        clientes = pd.read_csv(CLEAN_DIR / "clientes.csv")
        pedidos = pd.read_csv(CLEAN_DIR / "pedidos.csv")

        # productos: catálogo, validación estructural simple
        print(f"\n{'=' * 60}\nTABLA: productos\n{'=' * 60}")
        print(f"Filas a validar: {len(productos)}")
        motivos_prod = validar_estructural(productos, ESQUEMA_PRODUCTOS, "productos")
        productos_validos, _ = separar(productos, motivos_prod, "productos")

        # clientes: estructural (edad, rut, email, telefono)
        motivos_cli = validar_clientes(clientes)
        clientes_validos, _ = separar(clientes, motivos_cli, "clientes")

        # pedidos: estructural + semántica.
        # Las FK se chequean contra los datos LIMPIOS (no solo válidos):
        # un cliente rechazado p.ej. por email inválido sigue existiendo —
        # los huérfanos reales los detecta además la BD en la Etapa 4
        motivos_ped = validar_pedidos(pedidos, productos, clientes)
        pedidos_validos, _ = separar(pedidos, motivos_ped, "pedidos")

    except FileNotFoundError:
        logging.error("ARCHIVO NO ENCONTRADO en %s — ¿ejecutaste limpieza.py?", CLEAN_DIR)
        raise
    except Exception as e:
        logging.error("ERROR al validar: %s", str(e))
        raise

    total_validos = len(productos_validos) + len(clientes_validos) + len(pedidos_validos)
    logging.info("FIN Etapa 3 | registros_validos=%d", total_validos)

    print(f"\n✅ Validación completa: {total_validos} registros válidos.")
    print(f"   Válidos en:   {VALIDATED_DIR}")
    print(f"   Inválidos en: {ERRORS_DIR} (con columna motivo_rechazo)")

    return {"productos": productos_validos, "clientes": clientes_validos,
            "pedidos": pedidos_validos}


if __name__ == "__main__":
    validar()