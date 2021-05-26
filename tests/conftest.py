import shutil

import pytest
from pathlib import Path

from pyconcepticon.api import Concepticon
from pyconcepticon.test_util import TEST_REPOS, get_test_api


@pytest.fixture
def fixturedir():
    return Path(__file__).parent / 'fixtures'


@pytest.fixture(scope='session')
def api():
    return get_test_api()


@pytest.fixture
def tmprepos(tmp_path):
    shutil.copytree(TEST_REPOS, tmp_path / 'repos')
    tmp_path.joinpath('repos', 'app').mkdir()
    return tmp_path / 'repos'
