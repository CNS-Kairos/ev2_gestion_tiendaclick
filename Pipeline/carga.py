# =============================================================================
# ETAPA 4 — CARGA A BASE DE DATOS
# Pipeline TiendaClick · Evaluación Grupal Unidad 2
#
# Responsabilidades de esta etapa:
#   1. Leer datos validados desde /data/validated/.
#   2. Crear conexión a base de datos SQLite (o configurable a otro motor).
#   3. Definir esquema con tipos, PKs y FKs.
#   4. Insertar datos en orden (padres → hijos) dentro de una transacción.
#   5. Registros rechazados por la BD → log + /data/errors/.
#   6. Verificación SQL y reporte final.
# =============================================================================

import logging
import sqlite3
from pathlib import Path
import pandas as pd

# ─── Rutas del proyecto ──────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
VALIDATED_DIR = BASE_DIR / "data" / "validated"
ERRORS_DIR = BASE_DIR / "data" / "errors"
DB_DIR = BASE_DIR / "data" / "database"
LOG_DIR = BASE_DIR / "logs"

DB_DIR.mkdir(parents=True, exist_ok=True)
ERRORS_DIR.mkdir(parents=True, exist_ok=True)
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
    cantidad INTEGER NOT NULL,
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
    Limpia tablas antes de insertar (para poder re-ejecutar el pipeline).
    IMPORTANTE: el orden debe ser hija → padres (pedidos primero), porque
    con PRAGMA foreign_keys=ON no se puede borrar un cliente que aún
    tiene pedidos apuntándole.
    """
    cursor = conn.cursor()
    for tabla in tablas:
        cursor.execute(f"DELETE FROM {tabla};")
    logger.info(f"Tablas limpiadas: {', '.join(tablas)}")
    print(f"🧹 Tablas limpiadas: {', '.join(tablas)}")


def cargar_tabla(conn, df, tabla):
    """
    Carga un DataFrame fila a fila con INSERT.

    ¿Por qué fila a fila y no df.to_sql()? Porque to_sql inserta todo el
    lote de una vez: una sola fila con FK inválida bota la tabla completa.
    Insertando fila a fila, las que la BD rechaza (PK duplicada, FK
    inexistente) se capturan con try/except, quedan en el log y en
    /data/errors/<tabla>_rechazados_bd.csv, y el resto se carga igual.
    """
    if df.empty:
        print(f"⚠️ Tabla {tabla}: sin datos para cargar")
        logger.warning(f"Tabla {tabla}: DataFrame vacío, no se cargó nada")
        return 0

    columnas = ", ".join(df.columns)
    marcadores = ", ".join(["?"] * len(df.columns))
    sql = f"INSERT INTO {tabla} ({columnas}) VALUES ({marcadores})"

    cursor = conn.cursor()
    insertadas = 0
    rechazadas = []

    for fila in df.itertuples(index=False):
        valores = tuple(None if pd.isna(v) else v for v in fila)
        try:
            cursor.execute(sql, valores)
            insertadas += 1
        except sqlite3.IntegrityError as e:
            # Registro rechazado por la BD (PK duplicada, FK rota, NOT NULL)
            rechazo = dict(zip(df.columns, valores))
            rechazo["motivo_bd"] = str(e)
            rechazadas.append(rechazo)
            logger.warning(f"RECHAZO BD | tabla={tabla} | {e} | registro={valores[0]}")

    if rechazadas:
        ruta_rechazos = ERRORS_DIR / f"{tabla}_rechazados_bd.csv"
        pd.DataFrame(rechazadas).to_csv(ruta_rechazos, index=False, encoding="utf-8")
        print(f"  {tabla}: {len(rechazadas)} registros RECHAZADOS por la BD → {ruta_rechazos.name}")

    logger.info(f"CARGA OK | tabla={tabla} | insertadas={insertadas} | rechazadas={len(rechazadas)}")
    print(f"  {tabla}: {insertadas} registros insertados")
    return insertadas


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

    # Verificación SQL con GROUP BY (pauta: SELECT COUNT, GROUP BY)
    print(f"\n  Ingresos por categoría (GROUP BY):")
    cursor.execute("""
        SELECT p.categoria, COUNT(*) AS pedidos, SUM(pe.monto_total_clp) AS ingresos
        FROM pedidos pe JOIN productos p ON pe.id_producto = p.id_producto
        GROUP BY p.categoria ORDER BY ingresos DESC
    """)
    for categoria, n_pedidos, ingresos in cursor.fetchall():
        print(f"    {categoria:<15} {n_pedidos:>4} pedidos   ${ingresos:>12,.0f} CLP")
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

        # Tipos correctos antes de insertar (cantidad llega como 2.0)
        pedidos["cantidad"] = pedidos["cantidad"].astype(int)

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

        # 4. Cargar datos dentro de UNA transacción (patrón 'with conn:' de
        #    clases): si algo falla a mitad de camino, ROLLBACK automático —
        #    todo o nada, sin cargas parciales
        print("\n💾 Cargando datos...")
        logger.info("Iniciando carga de datos en tablas (transacción única)")

        with conn:
            # Truncar en orden hija → padres (para poder re-ejecutar)
            limpiar_tablas(conn, ["pedidos", "clientes", "productos"])

            # Insertar en orden padres → hija (FK exigen que el padre exista)
            filas_clientes = cargar_tabla(conn, clientes, "clientes")
            filas_productos = cargar_tabla(conn, productos, "productos")
            filas_pedidos = cargar_tabla(conn, pedidos, "pedidos")
        # ← al salir del with sin errores: COMMIT automático

        # 5. Verificar integridad referencial
        print("\n🔍 Verificando integridad...")
        verificar_integridad(conn)

        # 6. Mostrar estadísticas finales (verificación SQL)
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
        # El 'with conn:' ya hizo ROLLBACK automático de la transacción
        logger.error(f"ERROR al cargar: {str(e)} | ROLLBACK ejecutado", exc_info=True)
        raise
    finally:
        # Asegurar el cierre de la conexión bajo cualquier escenario
        if conn:
            conn.close()
            logger.info("Conexión a la base de datos cerrada correctamente")


if __name__ == "__main__":
    cargar()