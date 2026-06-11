"""
Módulo de Limpieza de Datos para el Pipeline de TiendaClick.

Este módulo se encarga de:
- Leer datos desde /data/raw/
- Deduplicar registros por ID
- Tratar valores nulos según criticidad de columnas
- Normalizar formatos (textos, fechas, mayúsculas/minúsculas)
- Guardar datos limpios en /data/processed/
- Registrar todas las operaciones en logs/pipeline.log

Arquitectura: Funciones reutilizables + funciones específicas por tabla + main() orquestador
"""

import pandas as pd
import logging
from pathlib import Path
from datetime import datetime
from typing import Tuple, Dict, List

# ============================================================================
# CONFIGURACIÓN DE LOGGING
# ============================================================================

def configurar_logging() -> None:
    """
    Configura el sistema de logging para escribir en archivo y consola.
    
    Salida:
    - Archivo: /logs/pipeline.log
    - Consola: INFO level
    - Formato: timestamp - nombre_modulo - nivel - mensaje
    """
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Configurar logging raíz
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.FileHandler(
                log_dir / "pipeline.log",
                encoding="utf-8"
            ),
            logging.StreamHandler()
        ]
    )


# ============================================================================
# FUNCIONES DE LECTURA Y ESCRITURA
# ============================================================================

def leer_datos(ruta: str) -> Tuple[pd.DataFrame, int]:
    """
    Lee un archivo CSV desde la ruta especificada.
    
    Args:
        ruta: Ruta del archivo CSV a leer
        
    Returns:
        Tupla (DataFrame, número de filas iniciales)
        
    Raises:
        FileNotFoundError: Si el archivo no existe
        Exception: Para otros errores de lectura (encoding, formato, permisos)
    """
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Iniciando lectura de datos desde: {ruta}")
        df = pd.read_csv(ruta, encoding="utf-8")
        num_filas_iniciales = len(df)
        logger.info(f"✓ Lectura exitosa. Filas iniciales: {num_filas_iniciales}")
        return df, num_filas_iniciales
    
    except FileNotFoundError as e:
        logger.error(f"ERROR FATAL: Archivo no encontrado en {ruta}")
        raise
    except Exception as e:
        logger.error(f"ERROR FATAL al leer {ruta}: {str(e)}", exc_info=True)
        raise


def guardar_datos(df: pd.DataFrame, ruta: str, nombre_tabla: str) -> None:
    """
    Guarda un DataFrame limpio en formato CSV.
    
    Args:
        df: DataFrame a guardar
        ruta: Ruta de destino (se crean directorios si no existen)
        nombre_tabla: Nombre de la tabla (para logging)
        
    Raises:
        Exception: Si hay error de escritura, permisos o directorio
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Crear directorios si no existen
        directorio = Path(ruta).parent
        directorio.mkdir(parents=True, exist_ok=True)
        
        # Guardar CSV
        df.to_csv(ruta, index=False, encoding="utf-8")
        logger.info(f"✓ Datos limpios de {nombre_tabla} guardados exitosamente en: {ruta}")
        logger.info(f"✓ Total de filas guardadas ({nombre_tabla}): {len(df)}")
    
    except Exception as e:
        logger.error(
            f"ERROR FATAL al guardar {nombre_tabla} en {ruta}: {str(e)}",
            exc_info=True
        )
        raise


# ============================================================================
# FUNCIONES DE LIMPIEZA GENÉRICAS
# ============================================================================

def limpiar_duplicados(
    df: pd.DataFrame,
    columna_id: str,
    nombre_tabla: str
) -> Tuple[pd.DataFrame, int]:
    """
    Elimina filas duplicadas basadas en la columna ID.
    
    Args:
        df: DataFrame a procesar
        columna_id: Nombre de la columna de identificador único (PK)
        nombre_tabla: Nombre de la tabla (para logging)
        
    Returns:
        Tupla (DataFrame sin duplicados, número de filas eliminadas)
    """
    logger = logging.getLogger(__name__)
    
    filas_antes = len(df)
    df_sin_duplicados = df.drop_duplicates(subset=[columna_id], keep="first")
    filas_eliminadas = filas_antes - len(df_sin_duplicados)
    
    if filas_eliminadas > 0:
        logger.info(
            f"  ➤ Deduplicación ({nombre_tabla}): "
            f"{filas_eliminadas} filas eliminadas (duplicadas por {columna_id})"
        )
    else:
        logger.info(f"  ➤ Deduplicación ({nombre_tabla}): No se encontraron duplicados")
    
    return df_sin_duplicados, filas_eliminadas


def limpiar_nulos(
    df: pd.DataFrame,
    columnas_criticas: List[str],
    columnas_imputable: Dict[str, str],
    nombre_tabla: str
) -> Tuple[pd.DataFrame, int]:
    """
    Trata valores nulos según criticidad:
    - Columnas críticas: elimina filas con NULL
    - Columnas secundarias: imputa con valor predeterminado
    
    Args:
        df: DataFrame a procesar
        columnas_criticas: Columnas donde NULL es inaceptable (elimina fila completa)
        columnas_imputable: Dict {columna: valor_imputacion} para columnas secundarias
        nombre_tabla: Nombre de la tabla (para logging)
        
    Returns:
        Tupla (DataFrame limpio, número de filas eliminadas por nulos críticos)
    """
    logger = logging.getLogger(__name__)
    
    filas_antes = len(df)
    
    # Fase 1: Eliminar filas con nulos en columnas críticas
    df = df.dropna(subset=columnas_criticas)
    filas_eliminadas_criticas = filas_antes - len(df)
    
    if filas_eliminadas_criticas > 0:
        columnas_str = ", ".join(columnas_criticas)
        logger.info(
            f"  ➤ Nulos en columnas críticas ({nombre_tabla}): "
            f"{filas_eliminadas_criticas} filas eliminadas ({columnas_str})"
        )
    else:
        logger.info(f"  ➤ Nulos en columnas críticas ({nombre_tabla}): ninguno detectado")
    
    # Fase 2: Imputar valores en columnas secundarias
    for columna, valor in columnas_imputable.items():
        if columna in df.columns:
            nulos_antes = df[columna].isna().sum()
            if nulos_antes > 0:
                df[columna].fillna(valor, inplace=True)
                logger.info(
                    f"  ➤ Nulos imputados en {columna} ({nombre_tabla}): "
                    f"{nulos_antes} valores → '{valor}'"
                )
    
    return df, filas_eliminadas_criticas


def normalizar_textos(
    df: pd.DataFrame,
    columnas_texto: List[str]
) -> pd.DataFrame:
    """
    Normaliza columnas de texto:
    - Elimina espacios en blanco al inicio/final (strip)
    - Reduce espacios múltiples internos a uno solo
    
    Args:
        df: DataFrame a procesar
        columnas_texto: Lista de nombres de columnas de texto
        
    Returns:
        DataFrame con textos normalizados
    """
    for columna in columnas_texto:
        if columna in df.columns and df[columna].dtype == 'object':
            # Strip de espacios
            df[columna] = df[columna].str.strip()
            # Reemplazar espacios múltiples
            df[columna] = df[columna].str.replace(r'\s+', ' ', regex=True)
    
    return df


def normalizar_fechas(
    df: pd.DataFrame,
    columnas_fecha: List[str],
    nombre_tabla: str
) -> pd.DataFrame:
    """
    Normaliza columnas de fecha al formato estándar YYYY-MM-DD.
    
    Manejo de errores:
    - Intenta parsear con pandas.to_datetime
    - Si falla, registra warning pero continúa
    
    Args:
        df: DataFrame a procesar
        columnas_fecha: Lista de columnas con fechas
        nombre_tabla: Nombre de la tabla (para logging)
        
    Returns:
        DataFrame con fechas normalizadas
    """
    logger = logging.getLogger(__name__)
    
    for columna in columnas_fecha:
        if columna in df.columns:
            try:
                # Convertir a datetime y formatear a YYYY-MM-DD
                df[columna] = pd.to_datetime(
                    df[columna],
                    errors="coerce"
                ).dt.strftime("%Y-%m-%d")
                logger.info(f"  ➤ Fechas normalizadas en {columna} ({nombre_tabla}) → YYYY-MM-DD")
            except Exception as e:
                logger.warning(
                    f"  ➤ Advertencia al normalizar fechas en {columna} "
                    f"({nombre_tabla}): {str(e)}"
                )
    
    return df


def normalizar_casing(
    df: pd.DataFrame,
    columnas_casing: Dict[str, str]
) -> pd.DataFrame:
    """
    Estandariza el formato de mayúsculas/minúsculas en columnas de texto.
    
    Args:
        df: DataFrame a procesar
        columnas_casing: Dict {columna: tipo} donde tipo puede ser:
                        'lower' (minúsculas), 'upper' (mayúsculas), 'title' (Título)
        
    Returns:
        DataFrame con casing normalizado
    """
    for columna, tipo in columnas_casing.items():
        if columna in df.columns and df[columna].dtype == 'object':
            if tipo == "lower":
                df[columna] = df[columna].str.lower()
            elif tipo == "upper":
                df[columna] = df[columna].str.upper()
            elif tipo == "title":
                df[columna] = df[columna].str.title()
    
    return df


# ============================================================================
# FUNCIONES DE LIMPIEZA ESPECÍFICA POR TABLA
# ============================================================================

def limpiar_clientes(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
    """
    Aplica limpieza específica para la tabla CLIENTES.
    
    Reglas de negocio:
    - Columnas críticas (no permiten NULL): id_cliente, nombre, rut
    - Columnas secundarias (se imputan): email, telefono
    - Normalización: textos, fechas, casing
    
    Args:
        df: DataFrame de clientes
        
    Returns:
        Tupla (DataFrame limpio, dict con estadísticas)
    """
    logger = logging.getLogger(__name__)
    logger.info("\n" + "=" * 80)
    logger.info("ETAPA: LIMPIEZA DE CLIENTES")
    logger.info("=" * 80)
    
    stats = {
        "tabla": "clientes",
        "filas_iniciales": len(df),
        "duplicados_eliminados": 0,
        "nulos_eliminados": 0,
    }
    
    try:
        # 1. Deduplicación por id_cliente
        df, duplicados = limpiar_duplicados(df, "id_cliente", "clientes")
        stats["duplicados_eliminados"] = duplicados
        
        # 2. Tratamiento de nulos
        columnas_criticas = ["id_cliente", "nombre", "rut"]
        columnas_imputable = {
            "email": "No proporcionado",
            "telefono": "No disponible"
        }
        df, nulos = limpiar_nulos(df, columnas_criticas, columnas_imputable, "clientes")
        stats["nulos_eliminados"] = nulos
        
        # 3. Normalización de textos (strip + espacios múltiples)
        columnas_texto = ["nombre", "email", "telefono", "comuna", "rut"]
        df = normalizar_textos(df, columnas_texto)
        logger.info(f"  ➤ Textos normalizados (strip + espacios múltiples)")
        
        # 4. Normalización de casing
        columnas_casing = {
            "nombre": "title",
            "email": "lower",
            "comuna": "title",
            "rut": "upper"
        }
        df = normalizar_casing(df, columnas_casing)
        logger.info(f"  ➤ Casing estandarizado (nombre=Title, email=lower, comuna=Title, rut=UPPER)")
        
        # 5. Normalización de fechas
        columnas_fecha = ["fecha_registro"]
        df = normalizar_fechas(df, columnas_fecha, "clientes")
        
        stats["filas_finales"] = len(df)
        logger.info(f"\n✓ CLIENTES LIMPIADOS: {stats['filas_iniciales']} → {stats['filas_finales']}")
        
    except Exception as e:
        logger.error(f"ERROR en limpieza de CLIENTES: {str(e)}", exc_info=True)
        raise
    
    return df, stats


def limpiar_pedidos(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
    """
    Aplica limpieza específica para la tabla PEDIDOS.
    
    Reglas de negocio:
    - Columnas críticas (no permiten NULL): id_pedido, id_cliente, id_producto, 
                                             cantidad, monto_total_clp
    - Columnas secundarias (se imputan): (ninguna)
    - Normalización: textos, fechas, casing
    
    Args:
        df: DataFrame de pedidos
        
    Returns:
        Tupla (DataFrame limpio, dict con estadísticas)
    """
    logger = logging.getLogger(__name__)
    logger.info("\n" + "=" * 80)
    logger.info("ETAPA: LIMPIEZA DE PEDIDOS")
    logger.info("=" * 80)
    
    stats = {
        "tabla": "pedidos",
        "filas_iniciales": len(df),
        "duplicados_eliminados": 0,
        "nulos_eliminados": 0,
    }
    
    try:
        # 1. Deduplicación por id_pedido
        df, duplicados = limpiar_duplicados(df, "id_pedido", "pedidos")
        stats["duplicados_eliminados"] = duplicados
        
        # 2. Tratamiento de nulos
        # Nota: fecha_despacho puede ser NULL si el pedido está pendiente/cancelado
        columnas_criticas = ["id_pedido", "id_cliente", "id_producto", "cantidad", "monto_total_clp"]
        columnas_imputable = {}  # Sin imputación de nulos
        df, nulos = limpiar_nulos(df, columnas_criticas, columnas_imputable, "pedidos")
        stats["nulos_eliminados"] = nulos
        
        # 3. Normalización de textos (strip + espacios múltiples)
        columnas_texto = ["estado", "metodo_pago"]
        df = normalizar_textos(df, columnas_texto)
        logger.info(f"  ➤ Textos normalizados (strip + espacios múltiples)")
        
        # 4. Normalización de casing
        columnas_casing = {
            "estado": "lower",
            "metodo_pago": "lower"
        }
        df = normalizar_casing(df, columnas_casing)
        logger.info(f"  ➤ Casing estandarizado (estado=lower, metodo_pago=lower)")
        
        # 5. Normalización de fechas
        columnas_fecha = ["fecha_pedido", "fecha_despacho"]
        df = normalizar_fechas(df, columnas_fecha, "pedidos")
        
        stats["filas_finales"] = len(df)
        logger.info(f"\n✓ PEDIDOS LIMPIOS: {stats['filas_iniciales']} → {stats['filas_finales']}")
        
    except Exception as e:
        logger.error(f"ERROR en limpieza de PEDIDOS: {str(e)}", exc_info=True)
        raise
    
    return df, stats


def limpiar_productos(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
    """
    Aplica limpieza específica para la tabla PRODUCTOS.
    
    Reglas de negocio:
    - Columnas críticas (no permiten NULL): id_producto, nombre_producto, 
                                             precio_unitario_clp, stock
    - Columnas secundarias (se imputan): (ninguna)
    - Normalización: textos, casing
    
    Args:
        df: DataFrame de productos
        
    Returns:
        Tupla (DataFrame limpio, dict con estadísticas)
    """
    logger = logging.getLogger(__name__)
    logger.info("\n" + "=" * 80)
    logger.info("ETAPA: LIMPIEZA DE PRODUCTOS")
    logger.info("=" * 80)
    
    stats = {
        "tabla": "productos",
        "filas_iniciales": len(df),
        "duplicados_eliminados": 0,
        "nulos_eliminados": 0,
    }
    
    try:
        # 1. Deduplicación por id_producto
        df, duplicados = limpiar_duplicados(df, "id_producto", "productos")
        stats["duplicados_eliminados"] = duplicados
        
        # 2. Tratamiento de nulos
        columnas_criticas = ["id_producto", "nombre_producto", "precio_unitario_clp", "stock"]
        columnas_imputable = {}  # Sin imputación de nulos
        df, nulos = limpiar_nulos(df, columnas_criticas, columnas_imputable, "productos")
        stats["nulos_eliminados"] = nulos
        
        # 3. Normalización de textos (strip + espacios múltiples)
        columnas_texto = ["nombre_producto", "categoria"]
        df = normalizar_textos(df, columnas_texto)
        logger.info(f"  ➤ Textos normalizados (strip + espacios múltiples)")
        
        # 4. Normalización de casing
        columnas_casing = {
            "nombre_producto": "title",
            "categoria": "title"
        }
        df = normalizar_casing(df, columnas_casing)
        logger.info(f"  ➤ Casing estandarizado (nombre_producto=Title, categoria=Title)")
        
        stats["filas_finales"] = len(df)
        logger.info(f"\n✓ PRODUCTOS LIMPIOS: {stats['filas_iniciales']} → {stats['filas_finales']}")
        
    except Exception as e:
        logger.error(f"ERROR en limpieza de PRODUCTOS: {str(e)}", exc_info=True)
        raise
    
    return df, stats


# ============================================================================
# FUNCIÓN PRINCIPAL (ORQUESTADOR)
# ============================================================================

def main():
    """
    Función principal que orquesta el proceso completo de limpieza.
    
    Procesa los tres archivos CSV en secuencia:
    1. clientes.csv
    2. pedidos.csv
    3. productos.csv
    
    Registra un resumen consolidado de todas las operaciones al finalizar.
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Encabezado de inicio
        logger.info("\n" + "=" * 80)
        logger.info(f"INICIANDO PIPELINE DE LIMPIEZA - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 80)
        
        # Definir rutas
        raw_dir = Path("data/raw")
        processed_dir = Path("data/processed")
        processed_dir.mkdir(parents=True, exist_ok=True)
        
        # Almacenar estadísticas
        todas_las_stats = []
        
        # ========== PROCESAMIENTO: CLIENTES ==========
        df_clientes, _ = leer_datos(raw_dir / "clientes.csv")
        df_clientes, stats_clientes = limpiar_clientes(df_clientes)
        guardar_datos(df_clientes, processed_dir / "clientes.csv", "clientes")
        todas_las_stats.append(stats_clientes)
        
        # ========== PROCESAMIENTO: PEDIDOS ==========
        df_pedidos, _ = leer_datos(raw_dir / "pedidos.csv")
        df_pedidos, stats_pedidos = limpiar_pedidos(df_pedidos)
        guardar_datos(df_pedidos, processed_dir / "pedidos.csv", "pedidos")
        todas_las_stats.append(stats_pedidos)
        
        # ========== PROCESAMIENTO: PRODUCTOS ==========
        df_productos, _ = leer_datos(raw_dir / "productos.csv")
        df_productos, stats_productos = limpiar_productos(df_productos)
        guardar_datos(df_productos, processed_dir / "productos.csv", "productos")
        todas_las_stats.append(stats_productos)
        
        # ========== RESUMEN FINAL ==========
        logger.info("\n" + "=" * 80)
        logger.info("RESUMEN CONSOLIDADO DE LIMPIEZA")
        logger.info("=" * 80)
        
        for stats in todas_las_stats:
            tabla = stats["tabla"].upper()
            iniciales = stats["filas_iniciales"]
            duplicados = stats["duplicados_eliminados"]
            nulos = stats["nulos_eliminados"]
            finales = stats["filas_finales"]
            
            logger.info(f"\n{tabla}:")
            logger.info(f"  • Filas iniciales: {iniciales}")
            logger.info(f"  • Duplicados eliminados: {duplicados}")
            logger.info(f"  • Nulos eliminados: {nulos}")
            logger.info(f"  • Filas finales: {finales}")
            logger.info(f"  • % Retención: {(finales/iniciales*100):.2f}%")
        
        # Mensaje de éxito
        logger.info("\n" + "=" * 80)
        logger.info(f"✓ PIPELINE DE LIMPIEZA COMPLETADO EXITOSAMENTE")
        logger.info(f"  Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"  Directorio de salida: {processed_dir.absolute()}")
        logger.info("=" * 80 + "\n")
        
    except Exception as e:
        logger.error(
            f"\n✗ ERROR FATAL EN PIPELINE DE LIMPIEZA: {str(e)}",
            exc_info=True
        )
        raise


if __name__ == "__main__":
    configurar_logging()
    main()
