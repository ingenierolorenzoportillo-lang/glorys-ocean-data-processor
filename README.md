# GLORYS Ocean Data Processor

**Versión 1.0.0b1 — beta funcional, verificable con datos sintéticos.**

Herramienta Python para automatizar el posprocesamiento de archivos **NetCDF (.nc/.nc4) de GLORYS / Copernicus Marine**: análisis espacial y puntual, climatologías mensuales y trimestrales, anomalías, series temporales, diagramas Hovmöller, mapas de campos medios, exportaciones y trazabilidad científica. Su diseño permite usar **diferentes áreas, periodos, puntos, profundidades y variables sin modificar el código fuente**.

Proyecto derivado de dos rutinas originales de investigación para Guapi–Gorgona: `analisis_guapi_gorgona.py` y `mapas_trimestrales_guapi_gorgona.py`. El núcleo se reconstruyó en módulos reutilizables y con una configuración central. Los originales no están incluidos en este paquete.

> **Alcance:** grillas **rectilíneas de latitud/longitud 1D**, calendario estándar, variables físicas GLORYS con unidades reconocidas y medias diarias o mensuales. No es un lector universal de cualquier NetCDF, modelo o malla curvilínea. El procesamiento local no necesita Internet; la descarga opcional sí.

## Características

- Identificación automática (`variables: ["auto"]`) o selección explícita de `thetao`, `so`, `uo`, `vo`, `zos`, `mlotst` y `current_speed` (rapidez derivada de `uo`/`vo`).
- Apertura y combinación de NetCDF por fragmentos temporales o partición de variables; rechaza duplicados, mallas incompatibles y unidades no reconocidas, sin interpolación de grillas.
- Recorte espacial `[oeste, este, sur, norte]`, periodo de estudio, periodo climatológico independiente, años objetivo y control de cobertura de muestras.
- Selección de profundidad: `surface` (nivel más somero disponible), `nearest` (nivel numéricamente más cercano) o `all` (todos los niveles).
- Extracción de puntos por **celda marina válida más cercana** con distancia máxima configurable, calculada en kilómetros.
- Promedios espaciales ponderados por `cos(latitud)` en grillas rectilíneas; series por estación; estadísticas y anomalías.
- Trimestres **enero–marzo, abril–junio, julio–septiembre, octubre–diciembre**, ponderados por días de cada mes; nunca se extrapolan trimestres incompletos.
- Climatologías con número mínimo configurable de años válidos por celda y periodo, sin recurrir silenciosamente a otro periodo base.
- Salidas **CSV, Excel, NetCDF y PNG** con `metodologia.json`, años/cobertura, coordenadas de extracción y configuración registrada.
- Mapas de campos medios, climatologías y anomalías. Los mapas de rapidez de corrientes incluyen flechas de la **anomalía de componentes** de la velocidad; las climatologías utilizan flechas del vector medio.
- Diagramas **Hovmöller mensual tiempo–profundidad** en puntos seleccionados cuando se trabaja con `depth.mode="all"` y `output.hovmoller=true`.
- Descarga opcional, separada del procesamiento, con la librería oficial `copernicusmarine`.
- Ejemplo sintético reproducible y batería de pruebas (`pytest`).

## 1. Instalación en Windows / Linux / macOS

Necesitas **Python 3.10 o superior**.

```powershell
# Terminal en la carpeta descomprimida del proyecto
python -m venv .venv
# Activar en PowerShell de Windows:
.venv\Scripts\Activate.ps1
# En Linux/macOS: source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
```

Para instalar la herramienta y todas las dependencias opcionales, en un entorno con bibliotecas geoespaciales compatibles:

```bash
python -m pip install -e '.[all]'
```

En Windows, si Cartopy falla, utilizar [Miniforge](https://github.com/conda-forge/miniforge):

```bash
conda create -n glorys-universal -c conda-forge python=3.11 numpy pandas xarray scipy matplotlib openpyxl dask netcdf4 cartopy shapely pyshp pip
conda activate glorys-universal
python -m pip install -e .
# Para descarga oficial adicional:
python -m pip install copernicusmarine
```

## 2. Primera ejecución sin datos reales

```bash
python -m glorys_processor demo --output demo
python -m glorys_processor validate --config demo/config.json --input demo/data
python -m glorys_processor run --config demo/config.json --input demo/data --output demo/results
```

Estos NetCDF **son sintéticos** y no deben citarse como resultados oceanográficos. La demostración usa Guapi–Gorgona solo como localización ilustrativa.

## 3. Procesar tus archivos GLORYS

1. Coloca uno o más archivos **.nc/.nc4 compatibles** dentro de `data/`. Pueden ser partes temporales o archivos con variables distintas que compartan exactamente la misma malla y coordenadas compatibles. No mezclar resoluciones ni productos incompatibles.
2. Crea `config.json` desde `config.example.json` o ejecuta `python -m glorys_processor init --output config.json`.
3. Cambia los parámetros en `config.json`. Hay ejemplos en `examples/`.
4. Ejecuta:

```bash
# Prevalidación de archivos, unidades, malla y selección
python -m glorys_processor validate --config config.json --input data

# Procesamiento completo
python -m glorys_processor run --config config.json --input data --output outputs

# Alternativa, después de pip install -e .:
glorys-process run --config config.json --input data --output outputs
```

Para ejecutar de forma independiente, con las rutas ya definidas en `config.json`:

```bash
glorys-process run --config config.json
```

**Nota:** los paths relativos de configuración se interpretan desde la carpeta actual de la terminal. `--input` y `--output` tienen prioridad sobre los directorios configurados.

## 4. Parámetros editables

Archivo completo en [`config.example.json`](config.example.json), documentación detallada en [`docs/CONFIGURACION.md`](docs/CONFIGURACION.md).

| Parámetro | Ejemplo | Función |
|---|---|---|
| `region.name` | `"Golfo de Urabá"` | Nombre usado en las figuras |
| `region.bbox` | `[-77.5,-76.1,7.5,9.0]` | Extensión oeste, este, sur, norte; `null` usa el NC completo |
| `time.start`, `time.end` | `"2000-01-01"`, `"2025-12-31"` | Periodo de procesamiento |
| `time.baseline_start`, `time.baseline_end` | `"1993-01-01"`, `"2022-12-31"` | Climatología de referencia común |
| `time.target_years` | `[2024,2025]` | Años a exportar en anomalías espaciales; `[]` todos los años presentes |
| `time.exclude_target_years_from_baseline` | `false` | Permite excluir años objetivo del periodo base |
| `time.min_baseline_years` | `5` | Mínimo de años completos por mes/trimestre y celda |
| `time.min_daily_coverage` | `0.9` | Cobertura de días válidos por mes y celda |
| `time.require_complete_month` | `true` | Exige que el NC tenga cada día calendario para datos diarios |
| `variables` | `["thetao","so","current_speed"]` | Variables a procesar o `["auto"]` |
| `depth.mode` | `"nearest"` | `surface`, `nearest` o `all` |
| `depth.meters` | `20` | Profundidad objetivo con `nearest` |
| `points` | `[{'name':...}]` | Coordenadas para extracción; JSON usa comillas dobles |
| `maps.enabled` | `true` | Generar mapas trimestrales si `output.figures=true` |
| `maps.mean_maps` | `true` | Generar campos medios para el periodo completo |
| `output.hovmoller` | `true` | Diagramas tiempo–profundidad al seleccionar `depth.mode="all"` |
| `maps.coastline_shapefile` | `null` | Shapefile **local** de GSHHG opcional; no se descarga automáticamente |
| `output.csv`, `.excel`, `.netcdf`, `.figures` | `true` | Activar o desactivar entregables |
| `output.dpi` | `220` | Resolución de las figuras |

Si `depth.mode="all"`, las estadísticas y series se exportan por cada nivel de la columna, mientras que **los mapas muestran el nivel más somero**. Selección de profundidad `nearest` sin interpolación vertical.

## 5. Archivos de salida

Cada corrida crea una carpeta independiente `outputs/GLORYS_YYYYMMDD_HHMMSS_micros/`:

```text
GLORYS_2026.../
├── metodologia.json
├── series_mensuales.csv
├── series_trimestrales.csv
├── climatologias_puntos.csv
├── estadisticos.csv
├── puntos_extraccion.csv
├── Oceanografia_GLORYS.xlsx
├── climatologia_mensual.nc
├── climatologia_trimestral.nc
├── anomalias_trimestrales.nc
├── n_anios_climatologia_trimestral.nc
└── Figuras/
    ├── serie_*.png
    ├── hovmoller_*.png
    ├── *_mapa_media.png
    ├── *_climatologia_trimestral.png
    └── *_anomalia_YYYY.png
```

Si `time.target_years=[]`, se producirán mapas para **todos los años disponibles**: para históricos extensos es recomendable especificar los años de interés y reducir así la cantidad de figuras.

La carpeta `Figuras` se crea únicamente si se solicita salida gráfica. Otros entregables pueden desactivarse para economizar almacenamiento.

## 6. Descarga opcional desde Copernicus Marine

No se incluyen contraseñas ni claves. Instalar la dependencia y autenticar con los mecanismos oficiales de Copernicus:

```bash
python -m pip install copernicusmarine
copernicusmarine login
```

Definir `download.dataset_id`, `download.variables`, `download.bbox`, `download.start`, `download.end`, y opcionalmente rango de profundidad y nombre de archivo en `config.json`. **Verificar que el dataset ID elegido contenga las variables pedidas**: las series de GLORYS pueden estar divididas por producto y variable. Entonces:

```bash
glorys-process download --config config.json --output data
```

Esta función utiliza la API oficial `copernicusmarine.subset`; requiere Internet y una cuenta autorizada. No ejecutamos descargas reales en las pruebas sintéticas.

Referencia oficial: https://help.marine.copernicus.eu/en/articles/8283072-copernicus-marine-toolbox-api-subset

## 7. Uso desde Spyder (sin consola)

Después de instalar el paquete en el entorno Python de Spyder:

```python
from glorys_processor.config import load_config
from glorys_processor.pipeline import run

config = load_config(r"D:\Proyectos\GLORYS\config.json")
run(config,
    input_directory=r"D:\Proyectos\GLORYS\data",
    output_directory=r"D:\Proyectos\GLORYS\resultados")
```

También puedes partir de [`examples/ejecutar_desde_spyder.py`](examples/ejecutar_desde_spyder.py).

## 8. Reproducibilidad y límites científicos

Consulta [`docs/METODOLOGIA.md`](docs/METODOLOGIA.md) para ecuaciones y control de cobertura. **Temperatura potencial** (`thetao`) no es temperatura in situ; **salinidad práctica** (`so`) es adimensional; `zos` es altura de superficie del modelo, no amplitud de marea. Los datos y su máscara no se rellenan, reinterpolan ni extrapolan.

Las coordenadas deben estar en latitud/longitud 1D; longitudes 0–360 se normalizan automáticamente a −180–180. Los recortes que cruzan el antimeridiano, mallas curvilíneas, calendarios no estándar, entradas horarias/subdiarias y mezcla de grillas **todavía no están admitidos**. La media espacial por `cos(latitud)` es una aproximación para grillas rectilíneas, no un cálculo de área exacta de celda. Un archivo mensual representa el mes completo aunque su timestamp esté situado en una fecha interna del mes.

**Validación:** 18 pruebas automatizadas sobre entradas sintéticas y una ejecución de extremo a extremo; pendiente contrastar científicamente contra series/figuras de GLORYS reales e inspeccionar metadatos de todas las versiones de producto utilizadas.

## 9. Contribuciones y publicación

Se incorpora `tests/` y un flujo de pruebas de GitHub Actions. Antes de publicar: verificar derechos de reutilización del código original y de los datos institucionales, definir licencia de software y agregar un conjunto pequeño de validación con datos GLORYS autorizados. **No publicar datos GLORYS completos, credenciales, información institucional restringida ni mapas sin su referencia de producto**.

Cita en investigaciones el producto/dataset ID, versión y fecha de consulta de Copernicus Marine, no solamente esta herramienta. Producto relacionado: https://doi.org/10.48670/moi-00021
