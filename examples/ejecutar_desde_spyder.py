"""Ejemplo de ejecución desde Spyder. Ajusta rutas a tus directorios en Windows."""
from pathlib import Path
from glorys_processor.config import load_config
from glorys_processor.pipeline import run

# Opciones: usar rutas absolutas, o ejecutar desde la raíz del repositorio.
RUTA_CONFIG = Path('config.json')
RUTA_NETCDF = Path('data')
RUTA_SALIDAS = Path('outputs')

if __name__ == '__main__':
    cfg = load_config(RUTA_CONFIG)
    resultado = run(cfg, input_directory=RUTA_NETCDF, output_directory=RUTA_SALIDAS)
    print('Archivos guardados en:', resultado['output'])
