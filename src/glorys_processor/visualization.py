"""Publication-style diagnostics; optional user-supplied high-resolution coastline."""
from pathlib import Path
import re
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm, Normalize

COLORMAPS = {"thetao": "inferno", "so": "viridis", "current_speed": "magma",
             "uo": "coolwarm", "vo": "coolwarm", "zos": "cividis", "mlotst": "viridis"}
UNITS = {"thetao": "°C (potential)", "so": "Practical salinity (1)", "current_speed": "m s⁻¹",
         "uo": "m s⁻¹", "vo": "m s⁻¹", "zos": "m", "mlotst": "m"}


def slug(s):
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", str(s))[:65]


def _save(fig, path, dpi):
    fig.savefig(path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_series(rows, output, dpi):
    df = pd.DataFrame(rows)
    if df.empty:
        return 0
    output = Path(output)
    output.mkdir(exist_ok=True, parents=True)
    count = 0
    for keys, g in df[df.period.eq("monthly")].groupby(["variable", "scope", "depth_m"], dropna=False):
        var, scope, z = keys
        dates = pd.to_datetime(g.time)
        fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True, layout="constrained")
        axes[0].plot(dates, g.value, color="#1D4057", lw=1.2, label="Media mensual")
        axes[0].plot(dates, g.climatology, color="#C37A27", lw=1, alpha=.85, label="Climatología mensual")
        axes[0].legend(loc="best", frameon=False, fontsize=9)
        axes[1].plot(dates, g.anomaly, color="#1D4057", lw=1)
        axes[1].axhline(0, color="black", lw=.6)
        for ax in axes:
            ax.grid(alpha=.18)
            ax.set_ylabel(UNITS.get(var, var))
        axes[1].set_xlabel("Fecha")
        fig.suptitle(f"{var} · {scope}" + (f" · {z:g} m" if pd.notna(z) else ""))
        dest = output / f"serie_{slug(var)}_{slug(scope)}_{slug(z)}.png"
        _save(fig, dest, dpi)
        count += 1
    return count


def _coast(ax, shapefile):
    if not shapefile:
        return
    # No automatic dataset download or low-resolution substitution.
    try:
        from cartopy.io import shapereader
        from shapely.geometry import box
        from matplotlib.patches import Polygon
    except ImportError as exc:
        raise ImportError("Cartopy/Shapely necesarios para coastline_shapefile; instala extras [coast]") from exc
    path = Path(shapefile).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"No existe shapefile de costa: {path}")
    xmin, xmax = ax.get_xlim(); ymin, ymax = ax.get_ylim()
    mask = box(xmin, ymin, xmax, ymax)
    reader = shapereader.BasicReader(str(path), bbox=mask.bounds)
    try:
        for geom in reader.geometries():
            if not geom.intersects(mask):
                continue
            g = geom.intersection(mask)
            polys = [g] if g.geom_type == "Polygon" else list(g.geoms) if g.geom_type == "MultiPolygon" else []
            for poly in polys:
                ax.add_patch(Polygon(np.asarray(poly.exterior.coords), facecolor="#E5E7EB",
                                     edgecolor="#444444", linewidth=.4, zorder=5))
    finally:
        reader.close()


def _plot_panels(field, variable, label, path, cfg, anomaly=False, arrows=None):
    field = field.isel(time=slice(0,cfg["maps"]["max_panels"]))
    if arrows is not None:
        arrows = arrows.isel(time=slice(0,cfg["maps"]["max_panels"]))
    n = field.sizes["time"]
    if not n:
        return
    ncol = 2 if n > 1 else 1
    nrow = int(np.ceil(n/ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(6.5*ncol, 5*nrow), squeeze=False,
                             constrained_layout=True)
    # Plot only the surface if depth=all; depth in filename/metadata notes.
    maps = field.isel(depth=0, drop=True) if "depth" in field.dims else field
    values = np.asarray(maps.values)
    finite = values[np.isfinite(values)]
    if len(finite):
        if anomaly:
            limit = float(np.nanmax(np.abs(finite)))
            norm = TwoSlopeNorm(vcenter=0, vmin=-max(limit,1e-12), vmax=max(limit,1e-12))
            cmap = "RdBu_r"
        else:
            lo, hi = np.nanpercentile(finite, [2,98])
            if lo == hi:
                lo,hi = lo-1e-6, hi+1e-6
            norm = Normalize(vmin=float(lo), vmax=float(hi))
            cmap = COLORMAPS.get(variable, "viridis")
    else:
        norm=Normalize(vmin=0,vmax=1); cmap = COLORMAPS.get(variable,"viridis")
    cmap_obj=plt.get_cmap(cmap).copy(); cmap_obj.set_bad("white")
    mappable = None
    for i in range(nrow*ncol):
        ax = axes.flat[i]
        if i >= n:
            ax.axis("off"); continue
        frame = maps.isel(time=i)
        mappable = ax.pcolormesh(maps.longitude, maps.latitude, frame.values,
                                  cmap=cmap_obj, norm=norm, shading="auto")
        ax.set_xlim(float(maps.longitude.min()),float(maps.longitude.max()))
        ax.set_ylim(float(maps.latitude.min()),float(maps.latitude.max()))
        ax.set_aspect(1 / max(.05, np.cos(np.deg2rad(float(maps.latitude.mean())))))
        ax.set(xlabel="Longitud (°)", ylabel="Latitud (°)")
        date = pd.Timestamp(maps.time.values[i])
        if "climatología" in label:
            ax.set_title(f"Trimestre {date.quarter}")
        else:
            ax.set_title(f"{date.year} · trimestre {date.quarter}")
        if arrows is not None and "time" in arrows.dims:
            au = arrows["uo"].isel(time=i)
            av = arrows["vo"].isel(time=i)
            if "depth" in au.dims:
                au=au.isel(depth=0);av=av.isel(depth=0)
            step = max(1, int(np.ceil(max(au.sizes["longitude"], au.sizes["latitude"])/17)))
            uv_abs = np.hypot(au.values, av.values)
            if np.isfinite(uv_abs).any() and np.nanmax(uv_abs) > 1e-5:
                ax.quiver(au.longitude.values[::step], au.latitude.values[::step],
                          au.values[::step,::step],av.values[::step,::step],
                          color="#303030",scale=5,zorder=4)
        _coast(ax, cfg["maps"]["coastline_shapefile"])
    if mappable is not None:
        fig.colorbar(mappable, ax=list(axes.flat[:n]), label=UNITS.get(variable,variable), shrink=.82)
    fig.suptitle(f"{cfg['region']['name']} · {variable} · {label}", fontsize=14)
    _save(fig, path, cfg["output"]["dpi"])


def plot_quarterly(clim, anomaly, cfg, output, current_uv=None):
    output = Path(output)
    output.mkdir(exist_ok=True, parents=True)
    n = 0
    import xarray as xr
    for var, c in clim.items():
        q = c.rename(quarter="time").assign_coords(time=pd.to_datetime([f"2000-{(x-1)*3+1:02d}-01" for x in c.quarter.values]))
        arrows_clim=None
        if var == "current_speed" and current_uv:
            arrows_clim=xr.Dataset({v:d.rename(quarter="time").assign_coords(time=q.time.values) for v,d in current_uv["climatology"].items()})
        _plot_panels(q, var, "climatología trimestral", output/f"{slug(var)}_climatologia_trimestral.png", cfg,arrows=arrows_clim)
        n += 1
        aa=anomaly[var]
        years = sorted(set(pd.DatetimeIndex(aa.time.values).year))
        for year in years:
            a = aa.sel(time=str(year))
            if not a.sizes["time"]:
                continue
            arrows_anom=None
            if var == "current_speed" and current_uv:
                arrows_anom=xr.Dataset({v:d.sel(time=str(year)) for v,d in current_uv["anomalies"].items()})
            _plot_panels(a, var, f"anomalía {year}",output/f"{slug(var)}_anomalia_{year}.png",cfg,anomaly=True,arrows=arrows_anom)
            n += 1
    return n


def plot_mean_map(field, variable, cfg, output, u=None, v=None):
    """Period mean map at the shallowest selected layer; arrows of mean vector."""
    if "depth" in field.dims:
        field=field.isel(depth=0,drop=True)
    z=field.mean("time",skipna=True).compute()
    cmap=plt.get_cmap(COLORMAPS.get(variable,"viridis")).copy()
    cmap.set_bad("white")
    fig,ax=plt.subplots(figsize=(9,6.5),layout="constrained")
    plot=ax.pcolormesh(z.longitude,z.latitude,z.values,cmap=cmap,shading="auto")
    ax.set(xlabel="Longitud (°)",ylabel="Latitud (°)",title=f"Media temporal · {variable} · {cfg['region']['name']}")
    ax.set_aspect(1/max(.05,np.cos(np.deg2rad(float(z.latitude.mean())))))
    fig.colorbar(plot,ax=ax,label=UNITS.get(variable,variable),shrink=.8)
    if u is not None and v is not None:
        um=u.isel(depth=0,drop=True) if "depth" in u.dims else u
        vm=v.isel(depth=0,drop=True) if "depth" in v.dims else v
        um=um.mean("time",skipna=True).compute();vm=vm.mean("time",skipna=True).compute()
        step=max(1,int(np.ceil(max(um.sizes["longitude"],um.sizes["latitude"])/17)))
        ax.quiver(um.longitude.values[::step],um.latitude.values[::step],
                  um.values[::step,::step],vm.values[::step,::step],color="#303030",scale=5)
    _coast(ax,cfg["maps"]["coastline_shapefile"])
    _save(fig,output,cfg["output"]["dpi"])


def plot_hovmoller(monthly, variable, points, cfg, output):
    """Monthly time/depth slice at fixed wet cells; no interpolation or artificial bottom."""
    if "depth" not in monthly.dims or not points:
        return 0
    import matplotlib.dates as mdates
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    n=0
    for p in points:
        a=monthly.isel(latitude=p["i"],longitude=p["j"],drop=True)
        a=a.transpose("depth","time").compute()
        fig,ax=plt.subplots(figsize=(12,5.8),layout="constrained")
        cmap=plt.get_cmap(COLORMAPS.get(variable,"viridis")).copy();cmap.set_bad("white")
        image=ax.pcolormesh(pd.to_datetime(a.time.values),a.depth.values,a.values,
                            shading="nearest",cmap=cmap)
        ax.set(title=f"Hovmöller mensual · {variable} · {p['name']}",
               xlabel="Fecha",ylabel="Profundidad disponible (m)")
        ax.set_ylim(max(float(a.depth.max()),1),0)
        locator=mdates.AutoDateLocator(minticks=5,maxticks=12)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
        fig.colorbar(image,ax=ax,label=UNITS.get(variable,variable))
        _save(fig,output/f"hovmoller_{slug(variable)}_{slug(p['name'])}.png",cfg["output"]["dpi"])
        n+=1
    return n
