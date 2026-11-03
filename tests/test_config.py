import copy
import pytest
from glorys_processor.config import DEFAULT,validate,write_template,load_config


def test_default_validates():
    assert validate(copy.deepcopy(DEFAULT))["depth"]["mode"] == "surface"


def test_template_and_load(tmp_path):
    path=tmp_path/"config.json"
    write_template(path)
    assert load_config(path)["time"]["min_baseline_years"] == 5
    with pytest.raises(FileExistsError):write_template(path)


@pytest.mark.parametrize("key,value",[("depth",{"mode":"nearest","meters":None}),
                                    ("time",{"min_baseline_years":0}),
                                    ("region",{"bbox":[179,-179,-3,3]}),
                                    ("variables",["non_existent"])])
def test_invalid_config(key,value):
    c=copy.deepcopy(DEFAULT)
    if isinstance(value,dict):c[key].update(value)
    else:c[key]=value
    with pytest.raises(ValueError):validate(c)
