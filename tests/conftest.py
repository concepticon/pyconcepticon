import shutil

import pytest
from pathlib import Path

from pyconcepticon.api import Concepticon


@pytest.fixture
def fixturedir():
    return Path(__file__).parent / 'fixtures'


@pytest.fixture(scope='session')
def api():
    return Concepticon(Path(__file__).parent / 'fixtures')


@pytest.fixture
def tmprepos(tmpdir):
    shutil.copytree(str(Path(__file__).parent / 'fixtures'), str(tmpdir.join('repos')))
    tmpdir.join('repos', 'app').mkdir()
    return Path(str(tmpdir.join('repos')))
