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
def tmprepos(tmpdir):
    shutil.copytree(str(TEST_REPOS), str(tmpdir.join('repos')))
    tmpdir.join('repos', 'app').mkdir()
    return Path(str(tmpdir.join('repos')))
