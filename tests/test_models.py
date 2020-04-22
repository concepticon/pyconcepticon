import copy

import pytest

from pyconcepticon.models import *


@pytest.fixture
def sun1991(tmprepos):
    return tmprepos / 'concepticondata' / 'conceptlists' / 'Sun-1991-1004.tsv'


def test_Conceptlist(sun1991, api):
    kw = dict(
        api=sun1991,
        id='Abc-1234-12',
        author='Some One',
        year='1234',
        list_suffix='a',
        items='12',
        tags='key1,key2',
        source_language='eng',
        target_language='other',
        url=None,
        refs='a,b',
        pdf='',
        note=None,
        pages=None,
        alias='',
        local=True,
    )
    assert Conceptlist(**kw).tg

    _kw = copy.deepcopy(kw)
    _kw['api'] = api
    assert Conceptlist(**kw).tg

    with pytest.raises(ValueError):
        _kw = copy.deepcopy(kw)
        _kw['year'] = 'xy'
        Conceptlist(**_kw)


@pytest.mark.filterwarnings("ignore:Unspecified column")
def test_compare_conceptlists(api, sun1991):
    list(compare_conceptlists(api, sun1991))
    list(compare_conceptlists(api, sun1991.stem))
