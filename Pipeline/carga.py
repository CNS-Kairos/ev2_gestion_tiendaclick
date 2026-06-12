# =============================================================================
# ETAPA 4 — CARGA A BASE DE DATOS
# Pipeline TiendaClick · Evaluación Grupal Unidad 2
#
# Responsabilidades de esta etapa:
#   1. Leer datos validados desde /data/validated/.
#   2. Crear conexión a base de datos SQLite (o configurable a otro motor).
#   3. Definir esquema con tipos, PKs y FKs.
#   4. Insertar datos en orden (padres → hijos).
#   5. Manejar integridad (INSERT OR IGNORE / REPLACE según política).
#   6. Logging y reporte final.
# =============================================================================

import logging
import sqlite3
from pathlib import Path
import pandas as pd

# ─── Rutas del proyecto ──────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
VALIDATED_DIR = BASE_DIR / "data" / "validated"
DB_DIR = BASE_DIR / "data" / "database"
LOG_DIR = BASE_DIR / "logs"

DB_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DB_DIR / "tiendaclick.db"

# ─── Logging ─────────────────────────────────────────────────────────────────
# Obtener logger centralizado (configurado por main.py) o crear uno de respaldo
logger = logging.getLogger(__name__)
if not logger.handlers:
    # Si se ejecuta directamente (no desde main.py), crear un logger local
    handler = logging.FileHandler(LOG_DIR / "carga.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


# ─── Definición del esquema de la base de datos ─────────────────────────────
# Orden de creación: primero tablas padre (clientes, productos), luego hija (pedidos)
SCHEMA_SQL = """
-- Tabla: clientes
CREATE TABLE IF NOT EXISTS clientes (
    id_cliente INTEGER PRIMARY KEY,
    nombre TEXT NOT NULL,
    rut TEXT NOT NULL UNIQUE,
    email TEXT,
    telefono TEXT,
    comuna TEXT,
    fecha_registro TEXT,
    edad INTEGER,
    rango_etario TEXT
);

-- Tabla: productos
CREATE TABLE IF NOT EXISTS productos (
    id_producto INTEGER PRIMARY KEY,
    nombre_producto TEXT NOT NULL,
    categoria TEXT,
    precio_unitario_clp INTEGER NOT NULL,
    stock INTEGER NOT NULL
);

-- Tabla: pedidos
CREATE TABLE IF NOT EXISTS pedidos (
    id_pedido INTEGER PRIMARY KEY,
    id_cliente INTEGER NOT NULL,
    id_producto INTEGER NOT NULL,
    cantidad REAL NOT NULL,
    monto_total_clp REAL NOT NULL,
    fecha_pedido TEXT,
    fecha_despacho TEXT,
    estado TEXT,
    metodo_pago TEXT,
    dias_despacho REAL,
    monto_normalizado REAL,
    pago_debito INTEGER,
    pago_credito INTEGER,
    pago_transferencia INTEGER,
    pago_webpay INTEGER,
    FOREIGN KEY (id_cliente) REFERENCES clientes(id_cliente),
    FOREIGN KEY (id_producto) REFERENCES productos(id_producto)
);
"""

# Índices para mejorar rendimiento en consultas analíticas
INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_pedidos_cliente ON pedidos(id_cliente);",
    "CREATE INDEX IF NOT EXISTS idx_pedidos_producto ON pedidos(id_producto);",
    "CREATE INDEX IF NOT EXISTS idx_pedidos_fecha ON pedidos(fecha_pedido);",
    "CREATE INDEX IF NOT EXISTS idx_clientes_comuna ON clientes(comuna);",
    "CREATE INDEX IF NOT EXISTS idx_productos_categoria ON productos(categoria);",
]


def crear_base_datos(conn):
    """Crea las tablas e índices si no existen."""
    cursor = conn.cursor()
    cursor.executescript(SCHEMA_SQL)
    for idx_sql in INDEXES_SQL:
        cursor.execute(idx_sql)
    conn.commit()
    logger.info("Esquema de base de datos creado/verificado correctamente")
    print(" Esquema de base de datos listo")


def limpiar_tablas(conn, tablas):
    """
    Opcional: limpia tablas antes de insertar (para reiniciar pipeline).
    Por defecto comentado para no borrar datos accidentalmente.
    """
    cursor = conn.cursor()
    for tabla in tablas:
        cursor.execute(f"DELETE FROM {tabla};")
    conn.commit()
    logger.info(f"Tablas limpiadas: {', '.join(tablas)}")
    print(f"🧹 Tablas limpiadas: {', '.join(tablas)}")


def cargar_tabla(conn, df, tabla, insert_mode="replace"):
    """
    Carga un DataFrame a una tabla SQL.
    
    Parámetros:
    - conn: conexión a BD
    - df: DataFrame con datos
    - tabla: nombre de la tabla
    - insert_mode: 'append' (agrega) o 'replace' (reemplaza)
    """
    if df.empty:
        print(f"⚠️ Tabla {tabla}: sin datos para cargar")
        logger.warning(f"Tabla {tabla}: DataFrame vacío, no se cargó nada")
        return 0
    
    filas = len(df)
    
    if insert_mode == "replace":
        # Opción más segura: eliminar solo los registros que vamos a insertar
        # usando las claves primarias. Por simplicidad, truncamos la tabla.
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM {tabla};")
        logger.info(f"Tabla {tabla} truncada antes de insertar")
    
    # Insertar usando pandas.to_sql (manejo automático de tipos)
    # if_exists: 'append' porque ya truncamos manualmente
    df.to_sql(tabla, conn, if_exists="append", index=False)
    
    logger.info(f"CARGA OK | tabla={tabla} | filas_insertadas={filas}")
    print(f"  {tabla}: {filas} registros insertados")
    return filas


def verificar_integridad(conn):
    """Verifica integridad referencial después de la carga."""
    cursor = conn.cursor()
    
    # Verificar huérfanos en pedidos
    cursor.execute("""
        SELECT COUNT(*) FROM pedidos p
        LEFT JOIN clientes c ON p.id_cliente = c.id_cliente
        LEFT JOIN productos pr ON p.id_producto = pr.id_producto
        WHERE c.id_cliente IS NULL OR pr.id_producto IS NULL
    """)
    huerfanos = cursor.fetchone()[0]
    
    if huerfanos > 0:
        logger.warning(f"INTEGRIDAD: {huerfanos} pedidos con FK inválidas")
        print(f"Advertencia: {huerfanos} pedidos tienen referencias inválidas")
    else:
        logger.info("INTEGRIDAD OK: Sin huérfanos en pedidos")
        print(" Integridad referencial verificada: OK")
    
    return huerfanos


def mostrar_estadisticas(conn):
    """Muestra estadísticas resumidas de la base de datos cargada."""
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM clientes")
    total_clientes = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM productos")
    total_productos = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM pedidos")
    total_pedidos = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT SUM(monto_total_clp) FROM pedidos
        WHERE estado = 'entregado'
    """)
    ventas_totales = cursor.fetchone()[0] or 0
    
    print(f"\n{'=' * 60}")
    print("📊 ESTADÍSTICAS FINALES - BASE DE DATOS")
    print(f"{'=' * 60}")
    print(f"  Clientes:  {total_clientes:,}")
    print(f"  Productos: {total_productos:,}")
    print(f"  Pedidos:   {total_pedidos:,}")
    print(f"  Ventas totales (entregados): ${ventas_totales:,.0f} CLP")
    print(f"{'=' * 60}")
    
    logger.info(
        f"ESTADÍSTICAS FINALES | clientes={total_clientes} | "
        f"productos={total_productos} | pedidos={total_pedidos} | "
        f"ventas={ventas_totales:,.0f}"
    )


def cargar():
    """Ejecuta la carga completa a base de datos."""
    
    logger.info("INICIO Etapa 4 — Carga a Base de Datos")
    
    print("\n" + "=" * 60)
    print("ETAPA 4 — CARGA A BASE DE DATOS")
    print("=" * 60)
    
    conn = None  # Inicializamos la variable para el manejo en bloques posteriores
    try:
        # 1. Leer datos validados
        print("\n Leyendo datos validados...")
        clientes = pd.read_csv(VALIDATED_DIR / "clientes.csv")
        productos = pd.read_csv(VALIDATED_DIR / "productos.csv")
        pedidos = pd.read_csv(VALIDATED_DIR / "pedidos.csv")
        
        print(f"  clientes:  {len(clientes)} registros")
        print(f"  productos: {len(productos)} registros")
        print(f"  pedidos:   {len(pedidos)} registros")
        
        logger.info(f"Datos leídos | clientes={len(clientes)} | productos={len(productos)} | pedidos={len(pedidos)}")
        
        # 2. Conectar a BD (SQLite)
        conn = sqlite3.connect(DB_PATH)
        
        # 2.1. Activar validación de llaves foráneas (ACID compliance)
        conn.execute("PRAGMA foreign_keys = ON")
        
        # 3. Crear esquema
        crear_base_datos(conn)
        
        # 4. Cargar datos en orden (padres → hijos)
        print("\n💾 Cargando datos...")
        logger.info("Iniciando carga de datos en tablas")
        
        filas_clientes = cargar_tabla(conn, clientes, "clientes", insert_mode="replace")
        filas_productos = cargar_tabla(conn, productos, "productos", insert_mode="replace")
        filas_pedidos = cargar_tabla(conn, pedidos, "pedidos", insert_mode="replace")
        
        # Confirmación explícita de la transacción (ACID - COMMIT) si todo fue exitoso
        conn.commit()
        
        # 5. Verificar integridad referencial
        print("\n🔍 Verificando integridad...")
        verificar_integridad(conn)
        
        # 6. Mostrar estadísticas finales
        mostrar_estadisticas(conn)
        
        total_registros = filas_clientes + filas_productos + filas_pedidos
        logger.info(f"FIN Etapa 4 | registros_cargados={total_registros} | db_path={DB_PATH}")
        print(f"\n✅ CARGA COMPLETA: {total_registros} registros cargados")
        print(f"   Base de datos: {DB_PATH}")
        
        return {
            "clientes": filas_clientes,
            "productos": filas_productos,
            "pedidos": filas_pedidos,
            "db_path": str(DB_PATH)
        }
        
    except FileNotFoundError as e:
        logger.error(f"ARCHIVO NO ENCONTRADO: {e}")
        print(f"\n❌ Error: No se encontraron archivos validados en {VALIDATED_DIR}")
        raise
    except Exception as e:
        # Aplicación explícita de ACID: deshacer cambios en caso de cualquier error (ROLLBACK)
        if conn:
            conn.rollback()
            logger.warning("Transacción revertida (ROLLBACK) debido a un error durante la carga")
        logger.error(f"ERROR al cargar: {str(e)}", exc_info=True)
        raise
    finally:
        # Asegurar el cierre de la conexión bajo cualquier escenario para liberar memoria
        if conn:
            conn.close()
            logger.info("Conexión a la base de datos cerrada correctamente")


def ejecutar_pipeline_completo():
    """
    Función opcional: ejecuta todo el pipeline de extremo a extremo.
    Requiere importar las funciones de los otros módulos.
    """
    print("\n" + "=" * 70)
    print("🚀 EJECUTANDO PIPELINE COMPLETO: Ingesta → Limpieza → Validación → Carga")
    print("=" * 70)
    
    # Importar funciones de otros módulos (asumiendo que están en el mismo directorio)
    try:
        from ingesta import ingestar
        from limpieza import limpiar
        from validacion import validar
        
        print("\n--- ETAPA 1: INGESTA ---")
        datos_raw = ingestar()
        
        print("\n--- ETAPA 2: LIMPIEZA ---")
        datos_limpios = limpiar()
        
        print("\n--- ETAPA 3: VALIDACIÓN ---")
        datos_validos = validar()
        
        print("\n--- ETAPA 4: CARGA ---")
        resultado_carga = cargar()
        
        print("\n" + "=" * 70)
        print("🎉 PIPELINE COMPLETO EJECUTADO CON ÉXITO")
        print("=" * 70)
        
        return resultado_carga
        
    except ImportError:
        print("\n No se pudieron importar los módulos del pipeline.")
        print("   Ejecutando solo la etapa de carga (asumiendo datos ya validados)...")
        return cargar()
    except Exception as e:
        print(f"\n Error en pipeline completo: {e}")
        raise


if __name__ == "__main__":
    # Por defecto ejecuta solo la carga (datos ya deben estar en /validated)
    # Si quieres ejecutar todo el pipeline, usa ejecutar_pipeline_completo()
    
    # Opción 1: Solo carga
    cargar()
    
    # Opción 2: Pipeline completo (descomentar la siguiente línea)
    # ejecutar_pipeline_completo()