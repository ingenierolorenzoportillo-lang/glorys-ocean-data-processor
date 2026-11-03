"""Create small demonstrative *synthetic* datasets (no external downloads)."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr
from .config import DEFAULT


def make_demo(root):
    root=Path(root).expanduser().resolve()
    data=root/"data"
    data.mkdir(parents=True,exist_ok=True)
    t=pd.date_range("2017-01-01", "2025-12-01", freq="MS")
    lat=np.linspace(2.5,3.3,6);lon=np.linspace(-78.5,-77.8,7)
    depth=np.array([0.5,10.0,40.0])
    rng=np.random.default_rng(42)
    seasonal=np.sin(2*np.pi*(t.month.to_numpy()-1)/12)[:,None,None,None]
    z=depth[None,:,None,None]
    y=lat[None,None,:,None]
    x=lon[None,None,None,:]
    shape=(len(t),len(depth),len(lat),len(lon))
    theta=27-0.025*z+0.4*seasonal+0.15*(y-2.8)+np.zeros(shape)+rng.normal(0,0.05,size=shape)
    so=33+0.018*z+0.2*seasonal+np.zeros(shape)+rng.normal(0,0.03,size=shape)
    u=0.12+0.03*seasonal+np.zeros(shape)
    v=0.06-0.02*seasonal+np.zeros(shape)
    ocean_mask=np.ones((len(lat),len(lon)),bool);ocean_mask[0,0]=False
    theta[:,:,~ocean_mask]=np.nan;so[:,:,~ocean_mask]=np.nan
    u[:,:,~ocean_mask]=np.nan;v[:,:,~ocean_mask]=np.nan
    ds=xr.Dataset({"thetao":(("time","depth","latitude","longitude"),theta,{"units":"degrees_celsius"}),
                   "so":(("time","depth","latitude","longitude"),so,{"units":"1e-3"}),
                   "uo":(("time","depth","latitude","longitude"),u,{"units":"m/s"}),
                   "vo":(("time","depth","latitude","longitude"),v,{"units":"m/s"})},
                  coords={"time":t,"depth":depth,"latitude":lat,"longitude":lon},
                  attrs={"origin":"SYNTHETIC test data; NOT GLORYS / NOT scientific observations"})
    ds.to_netcdf(data/"demo_sintetico.nc")
    cfg=json.loads(json.dumps(DEFAULT))
    cfg["input"]["directory"]=str(data)
    cfg["output"]["directory"]=str(root/"results")
    cfg["region"]["name"]="Guapi-Gorgona (EJEMPLO SINTÉTICO)"
    cfg["region"]["bbox"]=[-78.5,-77.8,2.5,3.3]
    cfg["time"].update({"baseline_start":"2017-01-01","baseline_end":"2023-12-31",
                        "target_years":[2024,2025],"min_baseline_years":5})
    cfg["depth"]["mode"]="surface"
    cfg["points"]=[{"name":"Ejemplo marino", "latitude":2.9, "longitude":-78.1, "max_distance_km":30}]
    cfg["variables"]=["thetao","so","current_speed"]
    (root/"config.json").write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return root
