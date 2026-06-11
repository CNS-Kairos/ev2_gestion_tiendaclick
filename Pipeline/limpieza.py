# =============================================================================
# ETAPA 2 — LIMPIEZA
# Pipeline TiendaClick · Evaluación Grupal Unidad 2
#
# Responsabilidades de esta etapa:
#   1. Leer datos raw desde /data/raw/ (sin modificar).
#   2. Aplicar limpieza: deduplicación, tratamiento de nulos, normalización.
#   3. Guardar datos limpios en /data/processed/.
#
# =============================================================================

import logging
from pathlib import Path

import pandas as pd

# ─── Rutas del proyecto ──────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
RAW_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    filename=LOG_DIR / "pipeline.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


# ─── Tablas a procesar ────────────────────────────────────────────────────────
TABLAS = ["clientes", "pedidos", "productos"]


def limpiar_clientes(df):
    """Limpia la tabla de clientes: deduplicación, nulos, normalización."""
    
    print(f"\n{'=' * 60}\nTABLA: clientes\n{'=' * 60}")
    
    filas_iniciales = len(df)
    print(f"Filas iniciales: {filas_iniciales}")
    
    # 1. Deduplicación por id_cliente
    df = df.drop_duplicates(subset=["id_cliente"], keep="first")
    duplicados = filas_iniciales - len(df)
    print(f"Duplicados eliminados: {duplicados}")
    
    # 2. Eliminar filas con nulos en columnas críticas (id_cliente, nombre, rut)
    filas_antes = len(df)
    df = df.dropna(subset=["id_cliente", "nombre", "rut"])
    nulos_criticos = filas_antes - len(df)
    print(f"Filas con nulos críticos eliminadas: {nulos_criticos}")
    
    # 3. Imputar nulos en columnas secundarias
    df["email"].fillna("No proporcionado", inplace=True)
    df["telefono"].fillna("No disponible", inplace=True)
    
    # 4. Normalización de textos (strip + espacios múltiples)
    for col in ["nombre", "email", "telefono", "comuna", "rut"]:
        df[col] = df[col].str.strip()
        df[col] = df[col].str.replace(r'\s+', ' ', regex=True)
    
    # 5. Normalización de casing
    df["nombre"] = df["nombre"].str.title()
    df["email"] = df["email"].str.lower()
    df["comuna"] = df["comuna"].str.title()
    df["rut"] = df["rut"].str.upper()
    
    # 6. Normalización de fechas
    df["fecha_registro"] = pd.to_datetime(df["fecha_registro"], errors="coerce").dt.strftime("%Y-%m-%d")
    
    filas_finales = len(df)
    print(f"Filas finales: {filas_finales}")
    print(f"% Retención: {(filas_finales/filas_iniciales*100):.2f}%")
    
    logging.info("LIMPIEZA OK | tabla=clientes | iniciales=%d | duplicados=%d | nulos=%d | finales=%d",
                 filas_iniciales, duplicados, nulos_criticos, filas_finales)
    
    return df


def limpiar_pedidos(df):
    """Limpia la tabla de pedidos: deduplicación, nulos, normalización."""
    
    print(f"\n{'=' * 60}\nTABLA: pedidos\n{'=' * 60}")
    
    filas_iniciales = len(df)
    print(f"Filas iniciales: {filas_iniciales}")
    
    # 1. Deduplicación por id_pedido
    df = df.drop_duplicates(subset=["id_pedido"], keep="first")
    duplicados = filas_iniciales - len(df)
    print(f"Duplicados eliminados: {duplicados}")
    
    # 2. Eliminar filas con nulos en columnas críticas
    filas_antes = len(df)
    df = df.dropna(subset=["id_pedido", "id_cliente", "id_producto", "cantidad", "monto_total_clp"])
    nulos_criticos = filas_antes - len(df)
    print(f"Filas con nulos críticos eliminadas: {nulos_criticos}")
    
    # 3. Normalización de textos (strip)
    for col in ["estado", "metodo_pago"]:
        df[col] = df[col].str.strip()
    
    # 4. Normalización de casing
    df["estado"] = df["estado"].str.lower()
    df["metodo_pago"] = df["metodo_pago"].str.lower()
    
    # 5. Normalización de fechas
    df["fecha_pedido"] = pd.to_datetime(df["fecha_pedido"], errors="coerce").dt.strftime("%Y-%m-%d")
    df["fecha_despacho"] = pd.to_datetime(df["fecha_despacho"], errors="coerce").dt.strftime("%Y-%m-%d")
    
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
    df["nombre_producto"] = df["nombre_producto"].str.title()
    df["categoria"] = df["categoria"].str.title()
    
    filas_finales = len(df)
    print(f"Filas finales: {filas_finales}")
    print(f"% Retención: {(filas_finales/filas_iniciales*100):.2f}%")
    
    logging.info("LIMPIEZA OK | tabla=productos | iniciales=%d | duplicados=%d | nulos=%d | finales=%d",
                 filas_iniciales, duplicados, nulos_criticos, filas_finales)
    
    return df


def limpiar():
    """Ejecuta la limpieza completa de las tres tablas."""
    
    logging.info("INICIO Etapa 2 — Limpieza")
    
    datos_limpios = {}
    
    for tabla in TABLAS:
        try:
            # Leer desde raw
            ruta_raw = RAW_DIR / f"{tabla}.csv"
            df = pd.read_csv(ruta_raw)
            
            # Limpiar según tabla
            if tabla == "clientes":
                df_limpio = limpiar_clientes(df)
            elif tabla == "pedidos":
                df_limpio = limpiar_pedidos(df)
            elif tabla == "productos":
                df_limpio = limpiar_productos(df)
            
            # Guardar en processed
            ruta_processed = PROCESSED_DIR / f"{tabla}.csv"
            df_limpio.to_csv(ruta_processed, index=False, encoding="utf-8")
            
            datos_limpios[tabla] = df_limpio
            
        except FileNotFoundError:
            logging.error("ARCHIVO NO ENCONTRADO: %s.csv en %s", tabla, RAW_DIR)
            raise
        except Exception as e:
            logging.error("ERROR al limpiar %s: %s", tabla, str(e))
            raise
    
    total_finales = sum(len(df) for df in datos_limpios.values())
    logging.info("FIN Etapa 2 | tablas=%d | registros_totales=%d", len(datos_limpios), total_finales)
    
    print(f"\n✅ Limpieza completa: {len(datos_limpios)} tablas procesadas.")
    print(f"   Datos limpios guardados en: {PROCESSED_DIR}")
    print(f"   Logs guardados en: {LOG_DIR / 'pipeline.log'}")
    
    return datos_limpios


if __name__ == "__main__":
    limpiar()
