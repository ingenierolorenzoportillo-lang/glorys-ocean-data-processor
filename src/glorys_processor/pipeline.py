"""Single reproducible processing pipeline for all GLORYS variables."""
import json
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np

from .io import open_glorys, subset_glorys, prepare_variables
from .processing import (detect_frequency, monthly_fields, quarterly_fields,
                         climatology, anomalies, choose_points, summarize)
from .outputs import write_results
from .visualization import plot_series, plot_quarterly, plot_mean_map, plot_hovmoller, slug


def run(cfg, input_directory=None, output_directory=None):
    input_directory = input_directory or cfg["input"]["directory"]
    output_base = Path(output_directory or cfg["output"]["directory"]).expanduser()
    ds, handles, paths = open_glorys(input_directory, cfg["input"]["pattern"], cfg["input"]["dask_chunks"])
    try:
        ds = subset_glorys(ds, cfg)
        ds, available = prepare_variables(ds, cfg["variables"])
        frequency = detect_frequency(ds.time.values)
        points = choose_points(ds, cfg, available[0])
        selected_depth = ds.attrs.get("selected_model_depth_m")
        print("Procesando:", ", ".join(available), f"({frequency})")
        base = output_base / ("GLORYS_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
        monthly_rows=[];quarterly_rows=[];climates=[];stats=[]
        monthly_for_hovmoller={}
        cm={};cq={};aq={};nq={}
        available_years=sorted(set(pd.DatetimeIndex(ds.time.values).year))
        for variable in available:
            print("  Variable:",variable)
            a=ds[variable]
            monthly=monthly_fields(a,cfg,frequency)
            quarterly=quarterly_fields(monthly)
            if cfg["output"]["figures"] and cfg["output"]["hovmoller"] and "depth" in monthly.dims:
                monthly_for_hovmoller[variable]=monthly
            cmonth, nmonth = climatology(monthly,cfg,"month")
            cquarter, nquarter = climatology(quarterly,cfg,"quarter")
            qanom=anomalies(quarterly,cquarter,cfg,"quarter")
            cm[variable]=cmonth
            cq[variable]=cquarter
            aq[variable]=qanom
            nq[variable]=nquarter
            r,c,s = summarize(monthly,variable,points,cfg,"monthly",selected_depth)
            monthly_rows.extend(r);climates.extend(c);stats.extend(s)
            r,c,s = summarize(quarterly,variable,points,cfg,"quarterly",selected_depth)
            quarterly_rows.extend(r);climates.extend(c);stats.extend(s)
            if not bool(cquarter.notnull().any().compute().item()):
                print(f"  AVISO: {variable}: climatología trimestral sin celdas con n >= "
                      f"{cfg['time']['min_baseline_years']}; revisa periodo base y cobertura")
        for p in points:
            print(f"  Punto '{p['name']}': celda {p['grid_lat']:.4f}, {p['grid_lon']:.4f}; {p['distance_km']:.2f} km")
        base,tables=write_results(base,cfg,paths,points,monthly_rows,quarterly_rows,climates,stats,
                                  cm,cq,aq,nq,frequency,selected_depth)
        current_vectors=None
        if "current_speed" in available and cfg["output"]["figures"] and cfg["maps"]["enabled"]:
            # Physical velocity arrows: mean u and mean v, not gradient of scalar speed.
            v_clim={};v_anom={}
            for component in ("uo","vo"):
                component_m=monthly_fields(ds[component],cfg,frequency)
                component_q=quarterly_fields(component_m)
                c,_=climatology(component_q,cfg,"quarter")
                v_clim[component]=c
                v_anom[component]=anomalies(component_q,c,cfg,"quarter")
            current_vectors={"climatology":v_clim,"anomalies":v_anom}
        figures=[]
        if cfg["output"]["figures"]:
            folder=base/"Figuras"
            figure_count=plot_series(monthly_rows,folder,cfg["output"]["dpi"])
            if cfg["maps"]["enabled"]:
                figure_count+=plot_quarterly(cq,aq,cfg,folder,current_vectors)
                if cfg["maps"]["mean_maps"]:
                    for variable in available:
                        plot_mean_map(ds[variable],variable,cfg,folder/f"{slug(variable)}_mapa_media.png",
                                      u=ds.get("uo") if variable=="current_speed" else None,
                                      v=ds.get("vo") if variable=="current_speed" else None)
                        figure_count+=1
            for variable,monthly in monthly_for_hovmoller.items():
                figure_count+=plot_hovmoller(monthly,variable,points,cfg,folder)
            figures=sorted(folder.glob("*.png"))
            print(f"Figuras producidas: {figure_count}")
        print(f"Salida: {base}")
        return {"output":base, "files":paths,"variables":available,
                "frequency":frequency,"figures":figures,
                "points":points,"available_years":available_years,"tables":tables}
    finally:
        for handle in handles:
            handle.close()
