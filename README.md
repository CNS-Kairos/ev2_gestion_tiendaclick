# Pipeline de Gestión de Datos - TiendaClick

Sistema integral de procesamiento, validación y almacenamiento de datos para una plataforma e-commerce, diseñado para garantizar la integridad referencial y el cumplimiento de transacciones ACID. El objetivo principal es automatizar el flujo de datos desde su ingesta hasta su persistencia en base de datos, con validaciones estructurales y semánticas rigurosas en cada etapa.

---

## Componentes del Sistema

- **Scripts de procesamiento**: Cuatro etapas de pipeline (ingesta, limpieza, validación y carga) basadas en Pandas y Pandera.
- **Almacenamiento de datos**: Capas de procesamiento (raw, clean, validated, errors) con auditoría completa.
- **Validación de datos**: Esquemas Pandera para validación estructural + reglas de negocio para validación semántica.
- **Base de datos**: SQLite con transacciones ACID, integridad referencial y versionado de cambios.
- **Logging centralizado**: Trazabilidad completa de todas las operaciones con timestamps.
- **Documentación**: Diseño técnico de la arquitectura y guía de implementación.

---

## Tecnologías Utilizadas

- Python 3.8+
- Pandas (manipulación de DataFrames)
- Pandera (validación de esquemas)
- SQLite 3 (base de datos)
- Pathlib (gestión de rutas)
- Logging (auditoría y trazabilidad)
- Git / GitHub

---

## Pipeline Implementado

| Etapa | Descripción | Responsabilidades |
|-------|-------------|-------------------|
| 1. Ingesta | Carga de archivos CSV desde fuente | Lectura de datos raw, estadísticas iniciales, logging |
| 2. Limpieza | Normalización y transformación de datos | Deduplicación, imputación, normalización de tipos |
| 3. Validación | Validación estructural y semántica | Pandera (tipos, rangos, regex), reglas de negocio (integridad referencial) |
| 4. Carga | Persistencia en base de datos | Inserción en orden (padres → hijos), transacciones ACID |

---

## Estructura del Repositorio

```
ev2_gestion_tiendaclick/
├── README.md
├── Pipeline/
│   ├── main.py                      # Orquestador central
│   ├── ingesta.py                   # Etapa 1: lectura de datos raw
│   ├── limpieza.py                  # Etapa 2: normalización y transformación
│   ├── validacion.py                # Etapa 3: validación estructural + semántica
│   ├── carga.py                     # Etapa 4: inserción en BD con ACID
│   ├── data/
│   │   ├── raw/                     # Archivos CSV originales (intactos)
│   │   │   ├── clientes.csv
│   │   │   ├── productos.csv
│   │   │   └── pedidos.csv
│   │   ├── clean/                   # Datos limpios y transformados
│   │   │   ├── clientes.csv
│   │   │   ├── productos.csv
│   │   │   └── pedidos.csv
│   │   ├── validated/               # Registros que pasaron validación
│   │   │   ├── clientes.csv
│   │   │   ├── productos.csv
│   │   │   └── pedidos.csv
│   │   ├── errors/                  # Registros rechazados (con motivo)
│   │   │   ├── clientes_errores.csv
│   │   │   ├── productos_errores.csv
│   │   │   └── pedidos_errores.csv
│   │   ├── database/                # Base de datos SQLite
│   │   │   └── tiendaclick.db
│   └── logs/                        # Logs específicos por etapa
│       └── pipeline.log             # Log centralizado de ejecución
└── .git/
```

---

## Estructura de Datos

### Tabla: clientes
```
id_cliente, nombre, rut, email, telefono, comuna, fecha_registro, edad, rango_etario
```

### Tabla: productos
```
id_producto, nombre_producto, categoria, precio_unitario_clp, stock
```

### Tabla: pedidos
```
id_pedido, id_cliente, id_producto, cantidad, monto_total_clp, fecha_pedido, 
fecha_despacho, estado, metodo_pago, dias_despacho, monto_normalizado, 
pago_debito, pago_credito, pago_transferencia, pago_webpay
```

---

## Cómo Ejecutar el Sistema

### Prerequisitos

1. **Python 3.8 o superior**
   ```bash
   python --version
   ```

2. **Dependencias instaladas**
   ```bash
   pip install pandas pandera
   ```

3. **Archivos CSV en `/data/raw/`**
   - `clientes.csv`
   - `productos.csv`
   - `pedidos.csv`

### Ejecución del Pipeline Completo

1. **Clonar el repositorio**
   ```bash
   git clone https://github.com/CNS-Kairos/ev2_gestion_tiendaclick.git
   cd ev2_gestion_tiendaclick/Pipeline
   ```

2. **Ejecutar el pipeline de extremo a extremo**
   ```bash
   python main.py
   ```
   
   Esto ejecutará automáticamente en orden:
   - ✅ Etapa 1: Ingesta
   - ✅ Etapa 2: Limpieza y transformación
   - ✅ Etapa 3: Validación estructural y semántica
   - ✅ Etapa 4: Carga a base de datos

3. **Ejecutar etapas individuales (opcional)**
   ```bash
   python ingesta.py       # Solo ingesta
   python limpieza.py      # Solo limpieza (requiere ingesta previa)
   python validacion.py    # Solo validación (requiere limpieza previa)
   python carga.py         # Solo carga (requiere validación previa)
   ```

### Verificar Ejecución

1. **Revisar el log centralizado**
   ```bash
   cat data/pipeline.log
   ```
   
   O en Windows:
   ```bash
   type data\pipeline.log
   ```

2. **Verificar archivos de salida**
   - Datos válidos: `data/validated/`
   - Datos rechazados: `data/errors/`
   - Base de datos: `data/database/tiendaclick.db`

3. **Consultar la base de datos (SQLite)**
   ```bash
   sqlite3 Pipeline/data/database/tiendaclick.db
   > SELECT COUNT(*) FROM clientes;
   > SELECT COUNT(*) FROM pedidos;
   ```

---

## Validaciones Implementadas

### Validación Estructural (Pandera)

**Clientes:**
- Edad: rango 18-110 años
- RUT: formato válido + dígito verificador (módulo 11)
- Email: formato válido (regex)
- Teléfono: formato +569XXXXXXXX

**Productos:**
- Precio: mayor a 0 CLP
- Stock: mayor o igual a 0 unidades

**Pedidos:**
- Cantidad: mayor o igual a 1 unidad
- Monto: mayor a 0 CLP

### Validación Semántica (Reglas de Negocio)

- Estado "entregado" → fecha_despacho NO puede ser nula
- Fecha de despacho ≥ fecha de pedido
- Estado "cancelado" → fecha_despacho debe ser nula
- Monto debe coincidir con precio × cantidad
- Integridad referencial: id_cliente y id_producto deben existir

---

## Características ACID Implementadas

| Propiedad | Implementación |
|-----------|-----------------|
| **Atomicidad** | Transacción única: todo o nada con `conn.commit()` final |
| **Consistencia** | `PRAGMA foreign_keys = ON` valida integridad referencial |
| **Aislamiento** | Conexión SQLite aislada por ejecución |
| **Durabilidad** | Cambios persistentes en disco solo si exitosos |

---

## Gestión de Errores

### Registros Rechazados

Todos los registros que fallan validación se guardan en `data/errors/` con una columna adicional `motivo_rechazo` que indica la razón específica del rechazo.

Ejemplo:
```
id_cliente,nombre,rut,email,telefono,comuna,fecha_registro,edad,rango_etario,motivo_rechazo
20,Invalid User,XXXX-X,notanemail,123456789,Santiago,2025-01-01,25,18-30,"email con formato inválido; edad fuera de rango 18-110"
```

### Logs de Auditoría

Cada etapa genera un log detallado con timestamps:
```
2026-06-11 14:25:30 | INFO | INICIO — Pipeline TiendaClick
2026-06-11 14:25:30 | INFO | Datos leídos | clientes=480 | productos=150 | pedidos=911
2026-06-11 14:25:31 | INFO | ✅ Etapa '1 — Ingesta' finalizada con éxito
2026-06-11 14:25:32 | INFO | CARGA OK | tabla=clientes | filas_insertadas=480
2026-06-11 14:25:34 | INFO | ✅ PIPELINE COMPLETADO CON ÉXITO
```

---

## Documentación Técnica

Para detalles profundos sobre la arquitectura, validaciones y decisiones de diseño, consulta:
- [Encabezado de ingesta.py](Pipeline/ingesta.py) — Responsabilidades de la Etapa 1
- [Encabezado de limpieza.py](Pipeline/limpieza.py) — Transformaciones aplicadas en la Etapa 2
- [Encabezado de validacion.py](Pipeline/validacion.py) — Esquemas Pandera y reglas de negocio
- [Encabezado de carga.py](Pipeline/carga.py) — Implementación ACID y gestión de transacciones

---

## Equipo de Desarrollo

- **Gestión de Datos**: Greg Astete - Responsable del pipeline y validaciones
- **QA / Auditoría**: Alexander Lambie - Verificación de integridad ACID
- **DevOps / Deployment**: Alan Rodriguez - Orquestación y logging centralizado

---


