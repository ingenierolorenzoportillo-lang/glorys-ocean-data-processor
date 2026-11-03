import copy
import numpy as np
import pandas as pd
import pytest
import xarray as xr
from glorys_processor.io import open_glorys,subset_glorys,prepare_variables
from glorys_processor.config import DEFAULT


def mini(times,variable="thetao",depth=None):
    axes={"time":times,"latitude":[2,3],"longitude":[282,283]}
    if depth is not None:
        axes["depth"]=depth
        dims=("time","depth","latitude","longitude")
        shape=(len(times),len(depth),2,2)
    else:
        dims=("time","latitude","longitude")
        shape=(len(times),2,2)
    units="degC" if variable=="thetao" else "psu"
    return xr.Dataset({variable:(dims,np.ones(shape),{"units":units})},coords=axes)


def test_multiple_nc_time_segments(tmp_path):
    ts=pd.date_range("2019-01-01",periods=12,freq="MS")
    mini(ts[:6]).to_netcdf(tmp_path/"a.nc")
    mini(ts[6:]).to_netcdf(tmp_path/"b.nc")
    ds,handles,_=open_glorys(tmp_path,chunks=None)
    try:
        assert len(ds.time)==12
        assert set(ds.longitude.values)=={-78.,-77.}
    finally:
        for h in handles:h.close()


def test_multiple_nc_variable_segments(tmp_path):
    ts=pd.date_range("2019-01-01",periods=4,freq="MS")
    mini(ts).to_netcdf(tmp_path/"a.nc")
    mini(ts,"so").to_netcdf(tmp_path/"b.nc")
    ds,handles,_=open_glorys(tmp_path,chunks=None)
    try:
        ds,available=prepare_variables(ds,["auto"])
        assert available==["thetao","so"]
        with pytest.raises(ValueError):prepare_variables(ds,["thetao","zos"])
    finally:
        for h in handles:h.close()


def test_nearest_depth_and_bbox():
    ds=mini(pd.date_range("2020-01-01",periods=3,freq="MS"),depth=[.5,20,50])
    cfg=copy.deepcopy(DEFAULT)
    cfg["region"]["bbox"]=[-78.2,-77.8,1.8,3.2]
    cfg["depth"]={"mode":"nearest","meters":18}
    result=subset_glorys(ds.assign_coords(longitude=[-78.,-77.]),cfg)
    assert "depth" not in result.dims
    assert result.attrs["selected_model_depth_m"]==20.
    assert result.sizes["longitude"]==1
