"""Command-line entrypoint: init, validate, run, download, demo."""
from __future__ import annotations
import argparse
from pathlib import Path
import json
import sys
from .config import load_config, write_template


def make_parser():
    parser=argparse.ArgumentParser(prog="glorys-process",description="Análisis universal configurable de datos GLORYS NetCDF")
    sub=parser.add_subparsers(dest="command",required=True)
    p=sub.add_parser("init",help="Generar configuración genérica")
    p.add_argument("--output",default="config.json")
    for cmd in ("validate","run","download"):
        p=sub.add_parser(cmd)
        p.add_argument("--config",default="config.json")
        if cmd in ("validate","run"):
            p.add_argument("--input",help="Sobrescribir input.directory")
        if cmd in ("run","download"):
            p.add_argument("--output",help="Sobrescribir output.directory para run o destino de descarga")
    p=sub.add_parser("demo",help="Crear NetCDF sintético y configuración ejecutable")
    p.add_argument("--output",default="demo")
    return parser


def main(argv=None):
    parser=make_parser()
    args=parser.parse_args(argv)
    try:
        if args.command == "init":
            print("Configuración creada:",write_template(args.output));return 0
        if args.command == "demo":
            from .demo import make_demo
            out=make_demo(args.output)
            print("Demo creado:",out)
            print(f"Ejecuta: glorys-process run --config {out/'config.json'} --input {out/'data'} --output {out/'results'}")
            return 0
        cfg=load_config(args.config)
        if args.command == "validate":
            from .io import open_glorys,subset_glorys,prepare_variables
            from .processing import detect_frequency
            ds,handles,paths=open_glorys(args.input or cfg["input"]["directory"],cfg["input"]["pattern"],cfg["input"]["dask_chunks"])
            try:
                ds=subset_glorys(ds,cfg)
                ds, selected=prepare_variables(ds,cfg["variables"])
                print("Archivos:",len(paths))
                print("Variables:",", ".join(selected))
                print("Frecuencia:",detect_frequency(ds.time.values))
                print("Periodo:",str(ds.time.values[0]),"a",str(ds.time.values[-1]))
                print("Malla:",ds.sizes["latitude"],"x",ds.sizes["longitude"])
                print("Profundidades:",ds.sizes.get("depth",1))
                print("Validación básica exitosa. No sustituye pruebas científicas.")
                return 0
            finally:
                for h in handles:h.close()
        if args.command == "run":
            from .pipeline import run
            run(cfg,args.input,args.output)
            return 0
        if args.command == "download":
            from .download import download
            response=download(cfg,args.output)
            print("Respuesta Copernicus:",response)
            return 0
    except (ValueError,FileNotFoundError,ImportError,FileExistsError,KeyError,OSError) as exc:
        print("ERROR:",exc,file=sys.stderr)
        return 2
    return 1
