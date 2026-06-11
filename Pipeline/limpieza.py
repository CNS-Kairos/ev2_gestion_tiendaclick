# =============================================================================
# ETAPA 2 — LIMPIEZA Y TRANSFORMACIÓN
# Pipeline TiendaClick · Evaluación Grupal Unidad 2
#
# Responsabilidades de esta etapa:
#   1. Leer datos raw desde /data/raw/ (sin modificar).
#   2. Aplicar limpieza: deduplicación, tratamiento de nulos, normalización.
#   3. Aplicar transformaciones (mínimo 3 según pauta).
#   4. Guardar datos limpios en /data/clean/.
#
# Nota: los errores de contenido (RUT inválido, cantidad='dos', montos
# negativos) se dejan pasar a propósito — los detecta la Etapa 3 (pandera).
# =============================================================================

import logging
from pathlib import Path

import pandas as pd

# ─── Rutas del proyecto ──────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
RAW_DIR = BASE_DIR / "data" / "raw"
CLEAN_DIR = BASE_DIR / "data" / "clean"
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
CLEAN_DIR.mkdir(parents=True, exist_ok=True)

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    filename=LOG_DIR / "limpieza.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


# ─── Diccionarios de normalización ───────────────────────────────────────────
# str.title() no corrige tildes, por eso se mapean los casos del raw
MAPA_COMUNAS = {
    "Maipu": "Maipú",
    "Nunoa": "Ñuñoa",
    "Penalolen": "Peñalolén",
    "Estacion Central": "Estación Central",
    "Santiago Centro": "Santiago",
}
MAPA_PAGOS = {"débito": "debito", "crédito": "credito"}


def parsear_fechas(serie):
    """Unifica los 3 formatos del raw (2025-03-15, 15/03/2025, 15-03-2025,
    2025/03/15) a ISO. Probar formato por formato evita que errors='coerce'
    convierta fechas válidas en NaT."""
    fechas = pd.to_datetime(serie, format="%Y-%m-%d", errors="coerce")
    for fmt in ["%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"]:
        fechas = fechas.fillna(pd.to_datetime(serie, format=fmt, errors="coerce"))
    return fechas.dt.strftime("%Y-%m-%d")


def limpiar_clientes(df):
    """Limpia la tabla de clientes: deduplicación, nulos, normalización."""

    print(f"\n{'=' * 60}\nTABLA: clientes\n{'=' * 60}")

    filas_iniciales = len(df)
    print(f"Filas iniciales: {filas_iniciales}")

    # 1. Deduplicación por id_cliente
    #    Criterio: keep="first" → conservamos la primera aparición (registro
    #    original); las repeticiones se consideran reingresos erróneos.
    df = df.drop_duplicates(subset=["id_cliente"], keep="first")
    duplicados = filas_iniciales - len(df)
    print(f"Duplicados eliminados: {duplicados}")

    # 2. Eliminar filas con nulos en columnas críticas (id_cliente, nombre, rut)
    filas_antes = len(df)
    df = df.dropna(subset=["id_cliente", "nombre", "rut"])
    nulos_criticos = filas_antes - len(df)
    print(f"Filas con nulos críticos eliminadas: {nulos_criticos}")

    # 3. Imputar nulos en columnas secundarias (criterio por campo)
    #    - edad → mediana (robusta a outliers)
    #    - comuna → 'Desconocida' (no inventamos ubicación)
    #    - email / telefono → quedan NaN: son opcionales (nullable en la BD);
    #      un texto de relleno haría que el regex de la Etapa 3 los rechace
    df["edad"] = df["edad"].fillna(df["edad"].median())
    df["comuna"] = df["comuna"].fillna("Desconocida")

    # 4. Normalización de textos (strip + espacios múltiples)
    for col in ["nombre", "email", "telefono", "comuna", "rut"]:
        df[col] = df[col].str.strip()
        df[col] = df[col].str.replace(r'\s+', ' ', regex=True)

    # 5. Normalización de casing
    df["nombre"] = df["nombre"].str.title()
    df["email"] = df["email"].str.lower()
    df["comuna"] = df["comuna"].str.title()
    df["rut"] = df["rut"].str.upper()

    # 6. Comunas con tildes y alias (MAIPU → Maipú, Santiago Centro → Santiago)
    df["comuna"] = df["comuna"].replace(MAPA_COMUNAS)

    # 7. Normalización de fechas (3 formatos → ISO)
    df["fecha_registro"] = parsear_fechas(df["fecha_registro"])

    # 8. TRANSFORMACIÓN 1 — columna derivada: rango etario
    df["rango_etario"] = pd.cut(df["edad"], bins=[0, 30, 50, 200],
                                labels=["18-30", "31-50", "51+"])

    filas_finales = len(df)
    print(f"Filas finales: {filas_finales}")
    print(f"% Retención: {(filas_finales/filas_iniciales*100):.2f}%")

    logging.info("LIMPIEZA OK | tabla=clientes | iniciales=%d | duplicados=%d | nulos=%d | finales=%d",
                 filas_iniciales, duplicados, nulos_criticos, filas_finales)

    return df


def limpiar_pedidos(df, productos):
    """Limpia la tabla de pedidos: deduplicación, nulos, normalización."""

    print(f"\n{'=' * 60}\nTABLA: pedidos\n{'=' * 60}")

    filas_iniciales = len(df)
    print(f"Filas iniciales: {filas_iniciales}")

    # 1. Deduplicación por id_pedido (mismo criterio: keep="first")
    df = df.drop_duplicates(subset=["id_pedido"], keep="first")
    duplicados = filas_iniciales - len(df)
    print(f"Duplicados eliminados: {duplicados}")

    # 2. Eliminar filas con nulos en columnas críticas (las FK)
    filas_antes = len(df)
    df = df.dropna(subset=["id_pedido", "id_cliente", "id_producto"])
    nulos_criticos = filas_antes - len(df)
    print(f"Filas con nulos críticos eliminadas: {nulos_criticos}")

    # 3. Normalización de textos (strip)
    for col in ["estado", "metodo_pago"]:
        df[col] = df[col].str.strip()

    # 4. Normalización de casing y categorías
    df["estado"] = df["estado"].str.lower().str.replace(" ", "_")  # 'en camino' → 'en_camino'
    df["metodo_pago"] = df["metodo_pago"].str.lower().replace(MAPA_PAGOS)

    # 5. Normalización de fechas (3 formatos → ISO)
    #    fecha_despacho nula es legítima (cancelado/pendiente) — la regla
    #    'entregado ⇒ fecha_despacho no nula' la revisa la Etapa 3
    df["fecha_pedido"] = parsear_fechas(df["fecha_pedido"])
    df["fecha_despacho"] = parsear_fechas(df["fecha_despacho"])

    # 6. Imputar nulos en monto_total_clp → recalcular precio × cantidad
    #    (JOIN con productos) en vez de eliminar la fila
    nulos_monto = int(df["monto_total_clp"].isna().sum())
    df = df.merge(productos[["id_producto", "precio_unitario_clp"]],
                  on="id_producto", how="left")
    cantidad_num = pd.to_numeric(df["cantidad"], errors="coerce")
    df["monto_total_clp"] = df["monto_total_clp"].fillna(
        df["precio_unitario_clp"] * cantidad_num)
    df = df.drop(columns=["precio_unitario_clp"])
    print(f"Montos recalculados (precio x cantidad): {nulos_monto}")

    # 7. TRANSFORMACIÓN 2 — columna derivada: días entre pedido y despacho
    df["dias_despacho"] = (pd.to_datetime(df["fecha_despacho"])
                           - pd.to_datetime(df["fecha_pedido"])).dt.days

    # 8. TRANSFORMACIÓN 3 — normalización min-max del monto
    monto = df["monto_total_clp"]
    df["monto_normalizado"] = ((monto - monto.min()) / (monto.max() - monto.min())).round(4)

    # 9. TRANSFORMACIÓN 4 — encoding one-hot del método de pago
    df = pd.concat([df, pd.get_dummies(df["metodo_pago"], prefix="pago", dtype=int)], axis=1)

    filas_finales = len(df)
    print(f"Filas finales: {filas_finales}")
    print(f"% Retención: {(filas_finales/filas_iniciales*100):.2f}%")

    logging.info("LIMPIEZA OK | tabla=pedidos | iniciales=%d | duplicados=%d | nulos=%d | finales=%d",
                 filas_iniciales, duplicados, nulos_criticos, filas_finales)

    return df


def limpiar_productos(df):
    """Limpia la tabla de productos: deduplicación, nulos, normalización."""

    print(f"\n{'=' * 60}\nTABLA: productos\n{'=' * 60}")

    filas_iniciales = len(df)
    print(f"Filas iniciales: {filas_iniciales}")

    # 1. Deduplicación por id_producto
    df = df.drop_duplicates(subset=["id_producto"], keep="first")
    duplicados = filas_iniciales - len(df)
    print(f"Duplicados eliminados: {duplicados}")

    # 2. Eliminar filas con nulos en columnas críticas
    filas_antes = len(df)
    df = df.dropna(subset=["id_producto", "nombre_producto", "precio_unitario_clp", "stock"])
    nulos_criticos = filas_antes - len(df)
    print(f"Filas con nulos críticos eliminadas: {nulos_criticos}")

    # 3. Normalización de textos (strip)
    for col in ["nombre_producto", "categoria"]:
        df[col] = df[col].str.strip()

    # 4. Normalización de casing
    df["categoria"] = df["categoria"].str.title()

    filas_finales = len(df)
    print(f"Filas finales: {filas_finales}")
    print(f"% Retención: {(filas_finales/filas_iniciales*100):.2f}%")

    logging.info("LIMPIEZA OK | tabla=productos | iniciales=%d | duplicados=%d | nulos=%d | finales=%d",
                 filas_iniciales, duplicados, nulos_criticos, filas_finales)

    return df


def limpiar():
    """Ejecuta la limpieza completa de las tres tablas."""

    logging.info("INICIO Etapa 2 — Limpieza y Transformación")

    datos_limpios = {}

    try:
        # productos primero: limpiar_pedidos lo necesita para recalcular montos
        productos = limpiar_productos(pd.read_csv(RAW_DIR / "productos.csv"))
        clientes = limpiar_clientes(pd.read_csv(RAW_DIR / "clientes.csv"))
        pedidos = limpiar_pedidos(pd.read_csv(RAW_DIR / "pedidos.csv"), productos)

        datos_limpios = {"productos": productos, "clientes": clientes, "pedidos": pedidos}

        # Guardar en clean (la pauta exige /data/clean/)
        for tabla, df in datos_limpios.items():
            df.to_csv(CLEAN_DIR / f"{tabla}.csv", index=False, encoding="utf-8")

    except FileNotFoundError:
        logging.error("ARCHIVO NO ENCONTRADO en %s", RAW_DIR)
        raise
    except Exception as e:
        logging.error("ERROR al limpiar: %s", str(e))
        raise

    total_finales = sum(len(df) for df in datos_limpios.values())
    logging.info("FIN Etapa 2 | tablas=%d | registros_totales=%d", len(datos_limpios), total_finales)

    print(f"\n✅ Limpieza completa: {len(datos_limpios)} tablas procesadas.")
    print(f"   Datos limpios guardados en: {CLEAN_DIR}")
    print("   Transformaciones: rango_etario, dias_despacho, monto_normalizado, one-hot pago")

    return datos_limpios


if __name__ == "__main__":
    limpiar()