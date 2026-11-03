"""CSV, Excel and CF-style NetCDF exports, with run provenance."""
import json
from pathlib import Path
import pandas as pd
import numpy as np
import xarray as xr


def _safe_cell(value):
    # Prevent CSV/Excel formula interpretation of externally supplied names.
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@", "\t")):
        return "'" + value
    return value


def dataframe(rows):
    df = pd.DataFrame(rows)
    for col in df.select_dtypes(include="object"):
        if col not in ("time",):
            df[col] = df[col].map(_safe_cell)
    return df


def _serialize(obj):
    if isinstance(obj, (np.integer, np.floating)):
        return obj.item()
    if isinstance(obj, (pd.Timestamp,)):
        return obj.isoformat()
    raise TypeError(type(obj).__name__)


def write_results(output_dir, cfg, files, points, monthly_rows, quarterly_rows, climates, stats, spatial_clim_month,
                  spatial_clim_quarter, spatial_anom_quarter, n_clim_quarter, frequency, selected_depth):
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=False)
    tables = {
        "series_mensuales": dataframe(monthly_rows),
        "series_trimestrales": dataframe(quarterly_rows),
        "climatologias_puntos": dataframe(climates),
        "estadisticos": dataframe(stats),
        "puntos_extraccion": dataframe(points),
    }
    metadata = {"config": cfg, "source_files": [str(f) for f in files],
                "input_frequency": frequency, "output_location": str(output.resolve()),
                "selected_model_depth_m": selected_depth,
                "monthly_climatology": "equal weight per valid year; min_baseline_years per cell",
                "quarterly_mean": "Jan-Mar/Apr-Jun/Jul-Sep/Oct-Dec: complete months, days-weighted",
                "anomaly": "period mean minus baseline climatology of SAME period",
                "current_speed": "hypot(uo,vo) BEFORE averaging; not magnitude of mean vector",
                "space": "cos(latitude)-weighted mean, rectilinear grid; not precise cell-area integration",
                "missing": "missing values stay NaN; no spatial/temporal interpolation or extrapolation",
                "selection": "nearest surface or specified model depth; no vertical interpolation",
                "software_validation": "Only synthetic tests completed; input datasets are user-provided and not presumed synthetic"}
    (output/"metodologia.json").write_text(json.dumps(metadata, ensure_ascii=False,indent=2,default=_serialize), encoding="utf-8")
    if cfg["output"]["csv"]:
        for name, df in tables.items():
            df.to_csv(output/f"{name}.csv",index=False,encoding="utf-8-sig")
    if cfg["output"]["excel"]:
        from openpyxl import Workbook
        from openpyxl.cell import WriteOnlyCell
        from openpyxl.styles import Font, PatternFill
        wb=Workbook(write_only=True)
        for name, df in tables.items():
            if df.empty:
                continue
            part=0; rowcount=0
            ws=None
            def create_sheet():
                nonlocal part, rowcount, ws
                part += 1;rowcount=0
                ws=wb.create_sheet((name[:24]+f"_{part:02d}")[:31])
                hdr=[]
                for col in df.columns:
                    cell=WriteOnlyCell(ws,value=str(col));cell.font=Font(color="FFFFFF",bold=True)
                    cell.fill=PatternFill(fill_type="solid",fgColor="153D53");hdr.append(cell)
                ws.append(hdr)
            create_sheet()
            for row in df.itertuples(index=False,name=None):
                if rowcount >= 1_048_575:
                    create_sheet()
                vals=[]
                for val in row:
                    if pd.isna(val): val=None
                    if isinstance(val, np.generic): val=val.item()
                    if isinstance(val,str):
                        c=WriteOnlyCell(ws,value=val[:32767]);c.data_type="s";vals.append(c)
                    else: vals.append(val)
                ws.append(vals);rowcount+=1
        ws=wb.create_sheet("Metodologia")
        ws.append(["Campo", "Valor"])
        ws.append(["Frecuencia",frequency])
        ws.append(["Referencias",f"{cfg['time']['baseline_start']} / {cfg['time']['baseline_end']}"])
        ws.append(["JSON completo", "Véase metodologia.json"])
        wb.save(output/"Oceanografia_GLORYS.xlsx")
    if cfg["output"]["netcdf"]:
        for name, contents in (("climatologia_mensual",spatial_clim_month),
                               ("climatologia_trimestral",spatial_clim_quarter),
                               ("anomalias_trimestrales",spatial_anom_quarter),
                               ("n_anios_climatologia_trimestral",n_clim_quarter)):
            if contents:
                dataset=xr.Dataset({k:v for k,v in contents.items()})
                dataset.attrs={"title":name,"source":"GLORYS via Copernicus Marine; derived from user NetCDF",
                               "baseline_period":f"{cfg['time']['baseline_start']} / {cfg['time']['baseline_end']}",
                               "missing_values":"NaN are not filled",
                               "selected_model_depth_m": selected_depth if selected_depth is not None else "all_or_not_applicable"}
                # NetCDF encoding is managed by xarray; compatible with netCDF4 or scipy backends.
                dataset.to_netcdf(output/f"{name}.nc")
    return output, tables
