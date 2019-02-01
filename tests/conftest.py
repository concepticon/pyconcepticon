import pytest
from pathlib import Path

from pyconcepticon.api import Concepticon


@pytest.fixture
def fixturedir():
    return Path(__file__).parent / 'fixtures'


@pytest.fixture(scope='session')
def api():
    return Concepticon(Path(__file__).parent / 'fixtures')
