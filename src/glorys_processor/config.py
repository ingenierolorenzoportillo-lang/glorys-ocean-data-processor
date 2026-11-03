"""Strict, documented JSON configuration for GLORYS Ocean Data Processor."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import pandas as pd

DEFAULT = {
    "input": {"directory": "data", "pattern": "*.nc*", "dask_chunks": "auto"},
    "output": {"directory": "outputs", "csv": True, "excel": True, "netcdf": True, "figures": True, "hovmoller": True, "dpi": 220},
    "region": {"name": "Ocean study region", "bbox": None},
    "time": {"start": None, "end": None, "baseline_start": "1993-01-01", "baseline_end": "2022-12-31",
             "target_years": [], "exclude_target_years_from_baseline": False,
             "min_baseline_years": 5, "min_daily_coverage": 0.9, "require_complete_month": True},
    "variables": ["auto"],
    "depth": {"mode": "surface", "meters": None},
    "points": [],
    "maps": {"enabled": True, "mean_maps": True, "coastline_shapefile": None, "max_panels": 4},
    "download": {"dataset_id": "", "variables": [], "bbox": None, "start": None, "end": None,
                 "minimum_depth": None, "maximum_depth": None, "filename": "copernicus_subset.nc"},
}
KNOWN = {"thetao", "so", "uo", "vo", "zos", "mlotst", "current_speed", "auto"}


def _merge(default, user, path=""):
    if not isinstance(user, dict):
        raise ValueError(f"{path or 'config'} debe ser un objeto JSON")
    result = copy.deepcopy(default)
    for k, v in user.items():
        if k not in default:
            raise ValueError(f"Clave de configuración desconocida: {path}{k}")
        if isinstance(default[k], dict) and isinstance(v, dict):
            result[k] = _merge(default[k], v, f"{path}{k}.")
        else:
            result[k] = v
    return result


def _date(value, key):
    if value is None:
        return None
    try:
        result = pd.Timestamp(value)
        if pd.isna(result) or result.tz is not None:
            raise ValueError
        return result
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f"{key}: fecha ISO inválida: {value!r}") from None


def _bbox(value, key):
    if value is None:
        return
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError(f"{key}: requiere [oeste, este, sur, norte]")
    try:
        west, east, south, north = map(float, value)
    except (ValueError, TypeError):
        raise ValueError(f"{key}: coordenadas numéricas requeridas") from None
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError(f"{key}: intervalos inválidos; cruce del antimeridiano no admitido")


def validate(cfg):
    if not isinstance(cfg["region"]["name"], str):
        raise ValueError("region.name debe ser texto")
    _bbox(cfg["region"]["bbox"], "region.bbox")
    _bbox(cfg["download"]["bbox"], "download.bbox")
    if not isinstance(cfg["variables"], list) or not cfg["variables"] or len(cfg["variables"]) != len(set(map(str, cfg["variables"]))):
        raise ValueError("variables debe ser lista no vacía sin duplicados")
    if "auto" in cfg["variables"] and cfg["variables"] != ["auto"]:
        raise ValueError("variables: auto debe usarse solo, o enumerar variables concretas")
    if set(cfg["variables"]) - KNOWN:
        raise ValueError(f"Variables no admitidas: {sorted(set(cfg['variables']) - KNOWN)}")
    for key in ["start", "end", "baseline_start", "baseline_end"]:
        _date(cfg["time"][key], "time." + key)
    if not cfg["time"]["baseline_start"] or not cfg["time"]["baseline_end"]:
        raise ValueError("Se exige time.baseline_start y time.baseline_end")
    for prefix, fields in [("time", ("start", "end")), ("time", ("baseline_start", "baseline_end")), ("download", ("start", "end"))]:
        a = _date(cfg[prefix][fields[0]], f"{prefix}.{fields[0]}")
        b = _date(cfg[prefix][fields[1]], f"{prefix}.{fields[1]}")
        if a is not None and b is not None and a > b:
            raise ValueError(f"{prefix}.{fields[0]} debe ser anterior a {fields[1]}")
    years = cfg["time"]["target_years"]
    if not isinstance(years, list) or any(type(y) is not int or not (1000 <= y <= 9999) for y in years) or len(set(years)) != len(years):
        raise ValueError("time.target_years: lista de años enteros únicos; [] significa todos los disponibles")
    for k in ("require_complete_month", "exclude_target_years_from_baseline"):
        if type(cfg["time"][k]) is not bool:
            raise ValueError(f"time.{k} debe ser booleano")
    if type(cfg["time"]["min_baseline_years"]) is not int or cfg["time"]["min_baseline_years"] < 1:
        raise ValueError("time.min_baseline_years debe ser entero positivo")
    if not 0 < float(cfg["time"]["min_daily_coverage"]) <= 1:
        raise ValueError("time.min_daily_coverage debe pertenecer a (0,1]")
    depth = cfg["depth"]
    if depth["mode"] not in ("surface", "nearest", "all"):
        raise ValueError("depth.mode: surface, nearest o all")
    if depth["mode"] == "nearest" and (depth["meters"] is None or float(depth["meters"]) < 0):
        raise ValueError("depth.meters debe ser positivo cuando depth.mode=nearest")
    if not isinstance(cfg["points"], list):
        raise ValueError("points debe ser lista")
    names = set()
    for point in cfg["points"]:
        if not isinstance(point, dict) or not {"name", "latitude", "longitude"}.issubset(point):
            raise ValueError("Cada punto requiere name, latitude, longitude")
        if set(point) - {"name", "latitude", "longitude", "max_distance_km"}:
            raise ValueError(f"Claves extra en punto: {point['name']}")
        if not str(point["name"]).strip() or point["name"] in names:
            raise ValueError("Nombres de puntos vacíos/duplicados")
        names.add(point["name"])
        if not -90 <= float(point["latitude"]) <= 90 or not -180 <= float(point["longitude"]) <= 180:
            raise ValueError(f"Coordenadas inválidas: {point['name']}")
        if float(point.get("max_distance_km", 25)) <= 0:
            raise ValueError("max_distance_km debe ser >0")
    if type(cfg["maps"]["max_panels"]) is not int or not 1 <= cfg["maps"]["max_panels"] <= 4:
        raise ValueError("maps.max_panels debe estar entre 1 y 4")
    for k in ("csv", "excel", "netcdf", "figures", "hovmoller"):
        if type(cfg["output"][k]) is not bool:
            raise ValueError(f"output.{k} debe ser booleano")
    if type(cfg["maps"]["enabled"]) is not bool or type(cfg["maps"]["mean_maps"]) is not bool:
        raise ValueError("maps.enabled y maps.mean_maps deben ser booleanos")
    if not isinstance(cfg["output"]["dpi"], int) or not 72 <= cfg["output"]["dpi"] <= 600:
        raise ValueError("output.dpi debe estar entre 72 y 600")
    if cfg["input"]["dask_chunks"] != "auto" and cfg["input"]["dask_chunks"] is not None:
        if not isinstance(cfg["input"]["dask_chunks"], dict) or any(type(v) is not int or v < 1 for v in cfg["input"]["dask_chunks"].values()):
            raise ValueError("input.dask_chunks: auto, null o diccionario de tamaños enteros")
    for key in ("start", "end"):
        _date(cfg["download"][key], f"download.{key}")
    dmin,dmax=cfg["download"]["minimum_depth"],cfg["download"]["maximum_depth"]
    if dmin is not None and float(dmin)<0 or dmax is not None and float(dmax)<0:
        raise ValueError("download: profundidades no pueden ser negativas")
    if dmin is not None and dmax is not None and float(dmin)>float(dmax):
        raise ValueError("download: minimum_depth > maximum_depth")
    if not isinstance(cfg["download"]["variables"],list) or any(not isinstance(v,str) for v in cfg["download"]["variables"]):
        raise ValueError("download.variables debe ser una lista de nombres")
    return cfg


def load_config(path):
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return validate(_merge(DEFAULT, raw))


def write_template(path):
    path = Path(path)
    if path.exists():
        raise FileExistsError(f"Ya existe: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(DEFAULT, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
