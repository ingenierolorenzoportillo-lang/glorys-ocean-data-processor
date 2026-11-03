"""Monthly / calendar-quarterly climatologies and anomalies with explicit QC."""
from __future__ import annotations
import numpy as np
import pandas as pd
import xarray as xr


def detect_frequency(times):
    idx = pd.DatetimeIndex(times)
    if idx.has_duplicates:
        raise ValueError("Fechas duplicadas en la serie")
    if idx.normalize().has_duplicates:
        raise ValueError("Más de un registro por día: solo se admiten medias diarias o mensuales")
    if idx.to_period("M").duplicated().any():
        return "daily"
    return "monthly"


def monthly_fields(a, cfg, frequency):
    """Calendar month means, per-cell daily coverage threshold; NaN never filled."""
    a = a.where(np.isfinite(a))
    m = a.resample(time="MS").mean(skipna=True)
    counts = a.resample(time="MS").count()
    monthly_dates = pd.DatetimeIndex(m.time.values)
    if frequency == "monthly":
        # Each record is one monthly mean; no within-month sampling QC is possible.
        m = m.where(counts >= 1)
    else:
        idx = pd.DatetimeIndex(a.time.values)
        seen = pd.Series(1, index=idx.normalize()).resample("MS").count().reindex(monthly_dates, fill_value=0)
        expected = monthly_dates.days_in_month.to_numpy()
        threshold = np.ceil(expected * float(cfg["time"]["min_daily_coverage"]))
        threshold_da = xr.DataArray(threshold, dims="time", coords={"time": m.time})
        mask = counts >= threshold_da
        if cfg["time"]["require_complete_month"]:
            complete = xr.DataArray(seen.to_numpy() == expected, dims="time", coords={"time": m.time})
            mask = mask & complete
        m = m.where(mask)
    m.attrs = dict(a.attrs)
    m.attrs["cell_qc"] = ("media mensual completa" if frequency == "monthly" else
                           f"cobertura diaria >= {cfg['time']['min_daily_coverage']}; "
                           f"mes calendario completo={cfg['time']['require_complete_month']}")
    return m


def quarterly_fields(monthly):
    """Jan–Mar, Apr–Jun, Jul–Sep, Oct–Dec, weighted by month days, no partial quarters."""
    indices = pd.DatetimeIndex(monthly.time.values)
    if len(indices) == 0:
        raise ValueError("No hay meses")
    periods = pd.period_range(indices[0], indices[-1], freq="Q-DEC")
    fields = []
    for period in periods:
        start = period.start_time
        months = pd.date_range(start, periods=3, freq="MS")
        selected = monthly.reindex(time=months)
        weights = xr.DataArray(months.days_in_month.astype(float), coords={"time": selected.time}, dims="time")
        quarter = ((selected * weights).sum("time", skipna=False) / weights.sum()).rename(monthly.name)
        # sum(skipna=False) makes any missing month in a cell invalid.
        quarter = quarter.expand_dims(time=[start])
        fields.append(quarter)
    result = xr.concat(fields, dim="time")
    result.attrs = {**monthly.attrs, "time_aggregation": "3 full calendar months; day-weighted"}
    return result


def _baseline_mask(time, cfg):
    dates = pd.DatetimeIndex(time.values)
    t = cfg["time"]
    chosen = (dates >= pd.Timestamp(t["baseline_start"])) & (dates <= pd.Timestamp(t["baseline_end"]))
    if t["exclude_target_years_from_baseline"] and t["target_years"]:
        chosen &= ~np.isin(dates.year, t["target_years"])
    return chosen


def climatology(fields, cfg, kind):
    """Equal weight per complete year for each month/quarter; enforce per-cell n years."""
    if kind not in ("month", "quarter"):
        raise ValueError("kind must be month or quarter")
    period_count = 12 if kind == "month" else 4
    index_name = "month" if kind == "month" else "quarter"
    dates = pd.DatetimeIndex(fields.time.values)
    basemask = _baseline_mask(fields.time, cfg)
    values = []
    counts = []
    template = fields.isel(time=0, drop=True)
    for period in range(1, period_count+1):
        pos = np.flatnonzero(basemask & ((dates.month == period) if kind == "month" else (dates.quarter == period)))
        if not len(pos):
            avg = xr.full_like(template, np.nan, dtype=float)
            n = xr.zeros_like(template, dtype="int32")
        else:
            subset = fields.isel(time=pos)
            n = subset.count("time").astype("int32")
            avg = subset.mean("time", skipna=True).where(n >= cfg["time"]["min_baseline_years"])
        values.append(avg.expand_dims({index_name: [period]}))
        counts.append(n.expand_dims({index_name: [period]}))
    climate = xr.concat(values, dim=index_name)
    num = xr.concat(counts, dim=index_name)
    climate.attrs = {**fields.attrs, "baseline_start": cfg["time"]["baseline_start"],
                     "baseline_end": cfg["time"]["baseline_end"],
                     "min_baseline_years": cfg["time"]["min_baseline_years"],
                     "exclude_target_years": cfg["time"]["exclude_target_years_from_baseline"]}
    return climate, num


def anomalies(fields, climate, cfg, kind):
    dates = pd.DatetimeIndex(fields.time.values)
    target = cfg["time"]["target_years"]
    positions = [i for i, d in enumerate(dates) if not target or d.year in target]
    if not positions:
        return fields.isel(time=slice(0, 0))
    dim = "month" if kind == "month" else "quarter"
    out = []
    for i in positions:
        date = dates[i]
        period = date.month if kind == "month" else date.quarter
        field = fields.isel(time=i, drop=True) - climate.sel({dim: period}, drop=True)
        out.append(field.expand_dims(time=[date]))
    result = xr.concat(out, dim="time")
    result.attrs = {**fields.attrs, "description": "anomaly = period mean - same calendar-period baseline climatology"}
    return result


def haversine_km(lat, lon, latgrid, longrid):
    lat1 = np.deg2rad(lat)
    lat2 = np.deg2rad(latgrid)
    da = (lat2-lat1) / 2
    db = np.deg2rad(longrid-lon) / 2
    h = np.sin(da)**2 + np.cos(lat1)*np.cos(lat2)*np.sin(db)**2
    return 6371.0088*2*np.arcsin(np.sqrt(np.clip(h, 0, 1)))


def choose_points(ds, cfg, reference):
    if not cfg["points"]:
        return []
    ref = ds[reference]
    if "depth" in ref.dims:
        ref = ref.isel(depth=0, drop=True)
    wet = ref.notnull().any("time").compute().transpose("latitude", "longitude").values
    latgrid, longrid = np.meshgrid(ds.latitude.values, ds.longitude.values, indexing="ij")
    result = []
    for p in cfg["points"]:
        lat, lon = float(p["latitude"]), float(p["longitude"])
        distances = haversine_km(lat, lon, latgrid, longrid)
        distances[~wet] = np.inf
        i, j = np.unravel_index(np.argmin(distances), distances.shape)
        km = float(distances[i, j])
        maximum = float(p.get("max_distance_km", 25))
        if not np.isfinite(km) or km > maximum:
            raise ValueError(f"Punto {p['name']}: celda húmeda más próxima a {km:.2f} km; límite {maximum} km")
        result.append({"name": p["name"], "requested_lat": lat, "requested_lon": lon,
                       "grid_lat": float(ds.latitude.values[i]), "grid_lon": float(ds.longitude.values[j]),
                       "distance_km": km, "i": int(i), "j": int(j)})
    return result


def _array_1d(a):
    return np.asarray(a.compute().values, dtype=float)


def _tabular_one(field, variable, depth, scope, cfg, kind):
    dates = pd.DatetimeIndex(field.time.values)
    values = _array_1d(field)
    baseline = _baseline_mask(field.time, cfg)
    period_ids = dates.month if kind == "monthly" else dates.quarter
    count_periods = 12 if kind == "monthly" else 4
    clims = np.full(count_periods+1, np.nan)
    ns = np.zeros(count_periods+1, dtype=int)
    for p in range(1, count_periods+1):
        sub = values[baseline & (period_ids == p)]
        sub = sub[np.isfinite(sub)]
        ns[p] = len(sub)
        if ns[p] >= cfg["time"]["min_baseline_years"]:
            clims[p] = sub.mean()
    rows = []
    for date, val, p in zip(dates, values, period_ids):
        cv = clims[p]
        rows.append({"variable": variable, "scope": scope, "depth_m": depth, "period": kind,
                     "time": date.isoformat(), "value": val, "climatology": cv,
                     "anomaly": val-cv, "n_baseline_years": ns[p], "calendar_period": int(p)})
    climrows = [{"variable": variable, "scope": scope, "depth_m": depth, "period": kind,
                 "calendar_period": p, "climatology": clims[p], "n_baseline_years": ns[p]}
                for p in range(1, count_periods+1)]
    clean = values[np.isfinite(values)]
    stats = {"variable": variable, "scope": scope, "depth_m": depth, "period": kind,
             "n_valid": len(clean), "mean": float(np.mean(clean)) if len(clean) else np.nan,
             "median": float(np.median(clean)) if len(clean) else np.nan,
             "std": float(np.std(clean, ddof=1)) if len(clean)>1 else np.nan,
             "min": float(np.min(clean)) if len(clean) else np.nan,
             "p05": float(np.percentile(clean,5)) if len(clean) else np.nan,
             "p95": float(np.percentile(clean,95)) if len(clean) else np.nan,
             "max": float(np.max(clean)) if len(clean) else np.nan}
    return rows, climrows, stats


def summarize(field, variable, points, cfg, kind, selected_depth=None):
    """Area-weighted regional mean, fixed wet-cell point extraction, per depth."""
    weights = xr.DataArray(np.cos(np.deg2rad(field.latitude)), dims="latitude", coords={"latitude":field.latitude})
    regional = field.weighted(weights).mean(("latitude", "longitude"), skipna=True)
    scopes = [("Regional", regional)]
    scopes.extend((p["name"], field.isel(latitude=p["i"], longitude=p["j"], drop=True)) for p in points)
    rows, climates, stats = [], [], []
    for scope, arr in scopes:
        if "depth" in arr.dims:
            parts = [(float(v), arr.isel(depth=i, drop=True)) for i, v in enumerate(arr.depth.values)]
        else:
            # An explicit nearest/surface selection has no depth dimension; retain requested actual depth elsewhere in provenance.
            parts = [(selected_depth, arr)]
        for z, part in parts:
            r, c, s = _tabular_one(part, variable, z, scope, cfg, kind)
            rows.extend(r); climates.extend(c); stats.append(s)
    return rows, climates, stats
