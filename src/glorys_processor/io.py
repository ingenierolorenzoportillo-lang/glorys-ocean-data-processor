"""Open compatible gridded GLORYS NetCDF files, without automatic regridding."""
from pathlib import Path
import importlib.util
import numpy as np
import pandas as pd
import xarray as xr

ALIASES = {"lat": "latitude", "nav_lat": "latitude", "lon": "longitude", "nav_lon": "longitude",
           "deptht": "depth", "depthu": "depth", "depthv": "depth", "valid_time": "time"}
META = {
    "thetao": ("Temperatura potencial", "degC"),
    "so": ("Salinidad práctica", "1"),
    "uo": ("Componente zonal de corriente", "m s-1"),
    "vo": ("Componente meridional de corriente", "m s-1"),
    "current_speed": ("Rapidez de corriente", "m s-1"),
    "zos": ("Altura de superficie del mar", "m"),
    "mlotst": ("Profundidad de capa mezclada del producto", "m"),
}


def normalize(ds):
    rename = {old: new for old, new in ALIASES.items() if old in ds.dims or old in ds.coords
              if new not in ds.dims and new not in ds.coords}
    ds = ds.rename(rename)
    for k in ("time", "latitude", "longitude"):
        if k not in ds.coords or ds[k].ndim != 1:
            raise ValueError(f"Se requiere coordenada 1D {k} (malla rectilínea)")
        if ds[k].to_index().has_duplicates:
            raise ValueError(f"Coordenadas duplicadas: {k}")
    if not np.issubdtype(ds.time.dtype, np.datetime64):
        raise ValueError("Fechas no estándar: se requieren fechas decodificables como datetime64")
    if np.any(pd.isnull(ds.time.values)):
        raise ValueError("Fechas NaT")
    if "depth" in ds.coords:
        if ds.depth.ndim != 1 or ds.depth.to_index().has_duplicates:
            raise ValueError("depth debe ser coordenada 1D única")
        if not np.all(np.isfinite(ds.depth.values)) or (ds.depth.values < 0).any():
            raise ValueError("La profundidad debe ser finita y positiva hacia abajo")
    # Convert 0..360 longitude to -180..180; reject duplicate seam.
    longitudes = ((np.asarray(ds.longitude.values, dtype=float) + 180) % 360) - 180
    ds = ds.assign_coords(longitude=longitudes)
    if ds.longitude.to_index().has_duplicates:
        raise ValueError("Longitudes duplicadas tras conversión -180..180")
    return ds.sortby("time").sortby("latitude").sortby("longitude").sortby("depth") if "depth" in ds.coords else ds.sortby("time").sortby("latitude").sortby("longitude")


def open_glorys(directory, pattern="*.nc*", chunks="auto"):
    directory = Path(directory).expanduser()
    if not directory.is_dir():
        raise FileNotFoundError(f"No existe directorio de datos: {directory}")
    paths = sorted(p for p in directory.glob(pattern) if p.is_file() and p.suffix.lower() in (".nc", ".nc4"))
    if not paths:
        raise FileNotFoundError(f"No hay archivos .nc/.nc4 que coincidan con {pattern} en {directory}")
    if chunks and importlib.util.find_spec("dask") is None:
        print("AVISO: Dask no disponible, se abrirá sin chunks; recomendable instalar dask[array]")
        chunks = None
    handles = []
    try:
        for path in paths:
            handles.append(normalize(xr.open_dataset(path, chunks=chunks)))
        if len(handles) == 1:
            ds = handles[0]
        else:
            ds = xr.combine_by_coords(handles, compat="no_conflicts", join="exact", combine_attrs="drop_conflicts")
            ds = normalize(ds)
        if ds.time.to_index().has_duplicates:
            raise ValueError("Fechas repetidas al combinar NetCDF; archivos solapados")
        return ds, handles, paths
    except Exception:
        for handle in handles:
            handle.close()
        raise


def subset_glorys(ds, cfg):
    time = cfg["time"]
    if time["start"] is not None:
        ds = ds.sel(time=slice(str(time["start"]), None))
    if time["end"] is not None:
        ds = ds.sel(time=slice(None, str(time["end"])))
    bbox = cfg["region"]["bbox"]
    if bbox:
        w, e, s, n = bbox
        ds = ds.sel(latitude=slice(s, n), longitude=slice(w, e))
    if any(ds.sizes[k] == 0 for k in ("time", "latitude", "longitude")):
        raise ValueError("El periodo o la región seleccionados no contienen datos")
    depth = cfg["depth"]
    if "depth" in ds.coords and depth["mode"] != "all":
        if depth["mode"] == "surface":
            selected = float(ds.depth.values[0])
            ds = ds.isel(depth=0, drop=True)
        else:
            selected = float(ds.sel(depth=float(depth["meters"]), method="nearest").depth.values)
            ds = ds.sel(depth=float(depth["meters"]), method="nearest", drop=True)
        ds.attrs = {**ds.attrs, "selected_model_depth_m": selected}
    return ds


def _units(value):
    return str(value).strip().lower().replace(" ", "").replace("−", "-").replace("**", "^")


def _convert(array, name):
    units = _units(array.attrs.get("units", ""))
    if name == "thetao":
        if units in ("k", "kelvin"):
            out = array - 273.15
        elif units in ("degc", "°c", "c", "celsius", "degree_celsius", "degrees_celsius", "degree_c", "degrees_c", "degreecelsius", "degreescelsius"):
            out = array
        else:
            raise ValueError(f"{name}: unidades desconocidas: {units!r}")
    elif name == "so":
        if units in ("1e-3", "1e-03", "0.001", "psu", "ppt", "1", "10^-3"):
            out = array
        else:
            raise ValueError(f"{name}: salinidad con unidad no reconocida: {units!r}")
    elif name in ("uo", "vo"):
        if units in ("m/s", "ms-1", "ms^-1", "m.s-1", "m.s^-1"):
            out = array
        elif units in ("cm/s", "cms-1", "cms^-1"):
            out = array / 100
        else:
            raise ValueError(f"{name}: unidades desconocidas: {units!r}")
    elif name in ("zos", "mlotst"):
        if units in ("m", "meter", "meters", "metre", "metres"):
            out = array
        elif units == "cm":
            out = array / 100
        else:
            raise ValueError(f"{name}: unidades desconocidas: {units!r}")
    else:
        raise ValueError("Variable no soportada: " + name)
    out = out.copy()
    out.attrs = {**array.attrs, "original_units": array.attrs.get("units", ""), "units": META[name][1]}
    return out


def prepare_variables(ds, requested):
    ds = ds.copy()
    if requested == ["auto"]:
        requested = [v for v in ("thetao", "so", "zos", "mlotst") if v in ds.data_vars]
        if "uo" in ds and "vo" in ds:
            requested.append("current_speed")
        else:
            requested.extend(v for v in ("uo", "vo") if v in ds.data_vars)
    available = [v for v in requested if v in ds.data_vars or v == "current_speed"]
    missing = [v for v in requested if v not in ds.data_vars and v != "current_speed"]
    if missing:
        raise ValueError(f"Variables solicitadas ausentes: {missing}; usa [\"auto\"] para autodetección")
    if "current_speed" in requested:
        if "uo" not in ds or "vo" not in ds:
            raise ValueError("current_speed exige ambas componentes uo y vo")
        available = [v for v in requested if v == "current_speed" or v in ds.data_vars]
    if not available:
        raise ValueError("Ninguna variable solicitada está disponible en el archivo")
    need = set(v for v in available if v != "current_speed")
    if "current_speed" in available:
        need.update(("uo", "vo"))
    for v in need:
        if v not in ds:
            raise ValueError(f"Falta variable requerida {v}")
        dims = set(ds[v].dims)
        if not {"time", "latitude", "longitude"}.issubset(dims) or dims - {"time", "latitude", "longitude", "depth"}:
            raise ValueError(f"Dimensiones no soportadas para {v}: {ds[v].dims}")
        ds[v] = _convert(ds[v], v)
    if "current_speed" in available:
        u, v = xr.align(ds.uo, ds.vo, join="exact")
        if set(u.dims) != set(v.dims):
            raise ValueError("uo y vo deben tener las mismas dimensiones")
        ds["current_speed"] = np.hypot(u, v).where(np.isfinite(u) & np.isfinite(v))
        ds["current_speed"].attrs = {"units": "m s-1", "formula": "hypot(uo,vo) antes de cualquier promedio"}
    return ds, available
