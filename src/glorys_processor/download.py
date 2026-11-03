"""Optional official Copernicus Marine API subsetting; no credentials stored in JSON."""
from pathlib import Path


def download(cfg, out_directory=None):
    try:
        import copernicusmarine
    except ImportError as exc:
        raise ImportError("Descarga opcional: instala 'pip install copernicusmarine'") from exc
    c = cfg["download"]
    dataset_id = str(c["dataset_id"]).strip()
    bbox = c["bbox"] if c["bbox"] is not None else cfg["region"]["bbox"]
    if not dataset_id or bbox is None or not c["start"] or not c["end"]:
        raise ValueError("download exige dataset_id, bbox, start y end. Consulta el catálogo oficial.")
    variables = c["variables"] or [v for v in cfg["variables"] if v != "current_speed"]
    if "auto" in variables:
        raise ValueError("download.variables: especifica variables concretas del dataset de Copernicus")
    if "current_speed" in cfg["variables"] and not {"uo", "vo"}.issubset(variables):
        variables = list(dict.fromkeys([*variables,"uo","vo"]))
    west, east, south, north = bbox
    output = Path(out_directory or cfg["input"]["directory"]).expanduser()
    output.mkdir(parents=True, exist_ok=True)
    kwargs = dict(dataset_id=dataset_id, variables=variables, minimum_longitude=west,
                  maximum_longitude=east, minimum_latitude=south, maximum_latitude=north,
                  start_datetime=c["start"], end_datetime=c["end"],
                  output_directory=str(output), output_filename=c["filename"],
                  file_format="netcdf", skip_existing=True)
    if c["minimum_depth"] is not None:
        kwargs["minimum_depth"] = float(c["minimum_depth"])
    if c["maximum_depth"] is not None:
        kwargs["maximum_depth"] = float(c["maximum_depth"])
    return copernicusmarine.subset(**kwargs)
