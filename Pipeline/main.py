# =============================================================================
# ORQUESTADOR CENTRAL — Pipeline TiendaClick
# Evaluación Grupal Unidad 2
#
# Responsabilidades:
#   1. Configurar logging centralizado con timestamp, nivel y mensaje.
#   2. Ejecutar las 4 etapas en orden: ingesta → limpieza → validación → carga
#   3. Registrar inicio/fin de pipeline y cada etapa.
#   4. Capturar y registrar errores sin perder trazabilidad.
# =============================================================================

import logging
import sys
from pathlib import Path

# ─── Rutas del proyecto ──────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "pipeline.log"

# ─── Configuración centralizada de logging ───────────────────────────────────
# IMPORTANTE: debe ejecutarse ANTES de importar las etapas. Cada módulo llama
# logging.basicConfig() al importarse, y basicConfig solo tiene efecto la
# PRIMERA vez — si las etapas se importaran antes, ingesta.py configuraría el
# logger raíz hacia ingesta.log y esta configuración quedaría ignorada.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),  # También a consola
    ],
)

logger = logging.getLogger(__name__)

# Importar funciones principales de cada etapa (después del basicConfig)
from ingesta import ingestar
from limpieza import limpiar
from validacion import validar
from carga import cargar


def ejecutar_etapa(nombre, funcion):
    """Ejecuta una etapa del pipeline con manejo de errores y logging."""
    logger.info(f"{'─' * 70}")
    logger.info(f"Iniciando Etapa: {nombre}")
    try:
        resultado = funcion()
        logger.info(f"✅ Etapa '{nombre}' finalizada con éxito")
        return resultado
    except Exception as e:
        logger.error(f"❌ Error en Etapa '{nombre}': {str(e)}", exc_info=True)
        raise


def main():
    """Orquesta la ejecución completa del pipeline."""
    logger.info("=" * 70)
    logger.info("INICIO — Pipeline TiendaClick (Evaluación Grupal Unidad 2)")
    logger.info("=" * 70)

    try:
        # Etapa 1: Ingesta
        ejecutar_etapa("1 — Ingesta", ingestar)

        # Etapa 2: Limpieza
        ejecutar_etapa("2 — Limpieza y Transformación", limpiar)

        # Etapa 3: Validación
        ejecutar_etapa("3 — Validación Estructural y Semántica", validar)

        # Etapa 4: Carga
        ejecutar_etapa("4 — Carga a Base de Datos", cargar)

        logger.info("=" * 70)
        logger.info("✅ PIPELINE COMPLETADO CON ÉXITO")
        logger.info("=" * 70)

    except Exception as e:
        logger.error("=" * 70)
        logger.error("❌ PIPELINE INTERRUMPIDO POR ERROR")
        logger.error("=" * 70)
        sys.exit(1)


if __name__ == "__main__":
    main()