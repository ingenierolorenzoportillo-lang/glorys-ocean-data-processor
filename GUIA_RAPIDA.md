# Guía rápida para comenzar

1. Descomprime el ZIP y abre una terminal dentro de su carpeta.
2. Instala Python 3.10+ y ejecuta: `python -m pip install -r requirements.txt` seguido de `python -m pip install -e .`.
3. Para verificar la instalación sin archivos propios: `glorys-process demo --output demo` y `glorys-process run --config demo/config.json`.
4. Para analizar GLORYS real: copia `.nc/.nc4` a `data`, copia `config.example.json` a `config.json` y modifica los parámetros. Ejecuta `glorys-process validate --config config.json` y luego `glorys-process run --config config.json`.
5. Resultados en `outputs/GLORYS_<fecha>/`, con CSV, Excel, NetCDF, figuras y `metodologia.json`.

**Configuraciones ilustrativas:** `examples/config_guapi_gorgona.json` y `examples/config_uraba.json`. La primera puede requerir datos históricos con referencia 1993–2022, y la segunda un recorte de Urabá. Si no dispones de ese periodo, ajusta el periodo base y el mínimo de años de forma científicamente justificable.

**Uso en Spyder:** consulta `examples/ejecutar_desde_spyder.py`.
