from glorys_processor.download import download
from glorys_processor.config import DEFAULT
import copy,pytest


def test_missing_copernicus_optional_dependency_or_required_params():
    cfg=copy.deepcopy(DEFAULT)
    with pytest.raises((ImportError,ValueError)):
        download(cfg)
