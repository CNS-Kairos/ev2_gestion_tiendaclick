# =============================================================================
# ETAPA 1 — INGESTA
# Pipeline TiendaClick · Evaluación Grupal Unidad 2
#
# Responsabilidades de esta etapa (según pauta 2.2):
#   1. Cargar el dataset desde su fuente (CSV).
#   2. Mostrar estadísticas iniciales: shape, dtypes, primeras filas, nulos.
#   3. Guardar una copia del raw dataset SIN MODIFICAR en /data/raw/.
#
# Decisión técnica: en la ingesta NO se corrige nada. El raw queda intacto
# como evidencia y respaldo; toda corrección ocurre en la Etapa 2.
# =============================================================================

import logging
from pathlib import Path

import pandas as pd

# ─── Rutas del proyecto ──────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
RAW_DIR = BASE_DIR / "data" / "raw"
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ─── Logging (patrón carga_profesional.py visto en clases) ──────────────────
logging.basicConfig(
    filename=LOG_DIR / "ingesta.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

# Tablas que componen el dataset: productos y clientes son tablas padre,
# pedidos es la tabla hija (FK hacia las otras dos).
TABLAS = ["productos", "clientes", "pedidos"]


def cargar_tabla(nombre: str) -> pd.DataFrame:
    """Carga un CSV desde data/raw/ y registra estadísticas iniciales."""
    ruta = RAW_DIR / f"{nombre}.csv"
    df = pd.read_csv(ruta)

    # Estadísticas iniciales exigidas por la pauta
    print(f"\n{'=' * 60}\nTABLA: {nombre}  ({ruta.name})\n{'=' * 60}")
    print(f"Shape: {df.shape[0]} filas x {df.shape[1]} columnas")
    print(f"\nDtypes:\n{df.dtypes}")
    print(f"\nPrimeras filas:\n{df.head(3).to_string()}")
    print(f"\nNulos por columna:\n{df.isna().sum()}")
    print(f"Duplicados exactos: {df.duplicated().sum()}")

    logging.info(
        "INGESTA OK | tabla=%s | filas=%d | columnas=%d | nulos=%d | duplicados=%d",
        nombre, len(df), df.shape[1], int(df.isna().sum().sum()),
        int(df.duplicated().sum()),
    )
    return df


def ingestar() -> dict[str, pd.DataFrame]:
    """Ejecuta la ingesta completa y devuelve los DataFrames raw."""
    logging.info("INICIO Etapa 1 — Ingesta")
    datos = {}
    for tabla in TABLAS:
        try:
            datos[tabla] = cargar_tabla(tabla)
        except FileNotFoundError:
            logging.error("ARCHIVO NO ENCONTRADO: %s.csv en %s", tabla, RAW_DIR)
            raise
    total = sum(len(df) for df in datos.values())
    logging.info("FIN Etapa 1 | tablas=%d | registros_totales=%d", len(datos), total)
    print(f"\n✅ Ingesta completa: {len(datos)} tablas, {total} registros totales.")
    print(f"   Raw intacto en: {RAW_DIR}")
    return datos


if __name__ == "__main__":
    ingestar()