import copy
import numpy as np
import pandas as pd
import pytest
import xarray as xr
from glorys_processor.config import DEFAULT
from glorys_processor.processing import detect_frequency,monthly_fields,quarterly_fields,climatology,anomalies,choose_points
from glorys_processor.io import prepare_variables,normalize


def fixture_cfg():
    cfg=copy.deepcopy(DEFAULT)
    cfg["time"].update(baseline_start="2020-01-01", baseline_end="2021-12-31",target_years=[2022],min_baseline_years=2)
    return cfg


def field(time,values):
    a=xr.DataArray(np.asarray(values,dtype=float)[:,None,None],dims=("time","latitude","longitude"),
                   coords={"time":pd.to_datetime(time),"latitude":[3.0],"longitude":[-78.0]},name="thetao")
    return a


def test_weighted_quarter_and_baseline_anomaly():
    times=pd.date_range("2020-01-01","2022-12-01",freq="MS")
    vals=np.full(len(times),10.,dtype=float)
    vals[(times.year==2022)&(times.month==2)]=40.
    a=field(times,vals)
    cfg=fixture_cfg()
    m=monthly_fields(a,cfg,"monthly");q=quarterly_fields(m)
    climate,n=climatology(q,cfg,"quarter")
    assert float(climate.sel(quarter=1).values.item())==pytest.approx(10.)
    janmar=q.sel(time="2022-01-01")
    expected=(31*10+28*40+31*10)/(31+28+31)
    assert float(janmar.values.item())==pytest.approx(expected)
    difference=anomalies(q,climate,cfg,"quarter")
    assert float(difference.sel(time="2022-01-01").values.item())==pytest.approx(expected-10.)
    assert len(difference.time)==4
    assert int(n.sel(quarter=1).values.item())==2


def test_require_three_months_and_missing_cell():
    cfg=fixture_cfg()
    a=field(["2020-01-01","2020-03-01","2020-04-01"],[1,3,4])
    q=quarterly_fields(monthly_fields(a,cfg,"monthly"))
    assert np.isnan(float(q.sel(time="2020-01-01").values.item()))
    assert np.isnan(float(q.sel(time="2020-04-01").values.item()))


def test_daily_coverage_controls():
    idx=pd.date_range("2020-02-01","2020-02-29",freq="D")
    idx=idx.delete(-1)
    cfg=fixture_cfg()
    cfg["time"]["min_daily_coverage"] = .9
    m=monthly_fields(field(idx, np.ones(len(idx))),cfg,"daily")
    assert np.isnan(float(m.sel(time="2020-02-01").values.item()))
    cfg["time"]["require_complete_month"] = False
    m2=monthly_fields(field(idx,np.ones(len(idx))),cfg,"daily")
    assert float(m2.sel(time="2020-02-01").values.item())==1.0


def test_baseline_no_silent_fallback():
    cfg=fixture_cfg()
    cfg["time"]["baseline_start"]="2010-01-01"
    cfg["time"]["baseline_end"]="2011-12-31"
    a=field(pd.date_range("2020-01-01","2022-12-01",freq="MS"),[1]*36)
    clim,_=climatology(monthly_fields(a,cfg,"monthly"),cfg,"month")
    assert np.isnan(clim.values).all()


def test_speed_magnitude_before_averaging():
    coords={"time":pd.date_range("2020-01-01",periods=2,freq="D"),"latitude":[3],"longitude":[-78]}
    u=xr.DataArray(np.array([1.,-1.])[:,None,None],coords=coords,dims=("time","latitude","longitude"),attrs={"units":"m/s"})
    v=xr.zeros_like(u);v.attrs["units"]="m/s"
    ds=xr.Dataset({"uo":u,"vo":v})
    output,vars=prepare_variables(ds,["current_speed"])
    assert vars==["current_speed"]
    assert float(output.current_speed.mean())==pytest.approx(1)
    assert float(output.uo.mean())==0


def test_longitude_normalization_and_wet_point():
    times=pd.date_range("2020-01-01",periods=2,freq="MS")
    a=xr.DataArray(np.array([[[np.nan,1.]],[[np.nan,1.]]]),dims=("time","latitude","longitude"),
                   coords={"time":times,"latitude":[3.],"longitude":[282.,283.]})
    ds=normalize(xr.Dataset({"thetao":a}))
    ds.thetao.attrs["units"]="degC"
    cfg=fixture_cfg()
    cfg["points"]=[{"name":"Ejemplo", "latitude":3,"longitude":-78,"max_distance_km":200}]
    p=choose_points(ds,cfg,"thetao")
    assert len(p)==1
    assert p[0]["grid_lon"]==-77
    assert p[0]["distance_km"]>100
    cfg["points"][0]["max_distance_km"]=5
    with pytest.raises(ValueError):choose_points(ds,cfg,"thetao")


def test_frequency_detection():
    assert detect_frequency(pd.date_range("2021-01-01",periods=12,freq="MS"))=="monthly"
    assert detect_frequency(pd.date_range("2021-01-01",periods=15,freq="D"))=="daily"
