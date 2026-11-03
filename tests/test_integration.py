import copy
from pathlib import Path
import pandas as pd
import xarray as xr
from glorys_processor.demo import make_demo
from glorys_processor.config import load_config
from glorys_processor.pipeline import run


def test_demo_end_to_end(tmp_path):
    root=make_demo(tmp_path/"demo")
    cfg=load_config(root/"config.json")
    cfg["output"]["figures"]=False
    output=run(cfg,root/"data",root/"results")["output"]
    assert (output/"metodologia.json").is_file()
    assert (output/"Oceanografia_GLORYS.xlsx").is_file()
    assert (output/"series_mensuales.csv").is_file()
    assert (output/"climatologia_trimestral.nc").is_file()
    df=pd.read_csv(output/"series_trimestrales.csv")
    assert df["calendar_period"].nunique()==4
    assert df["n_baseline_years"].min()>=5
    with xr.open_dataset(output/"anomalias_trimestrales.nc") as ds:
        assert ds.sizes["time"]==8
        assert "current_speed" in ds
    assert not any(x.name.endswith(".png") for x in output.rglob("*"))
