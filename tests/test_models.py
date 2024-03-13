import pytest

from pyconcepticon.models import *


@pytest.fixture
def sun1991(tmprepos):
    return tmprepos / 'concepticondata' / 'conceptlists' / 'Sun-1991-1004.tsv'


def test_Conceptlist(sun1991, api):
    def kw(**kwargs):
        res = dict(
            api=api,
            id='Abc-1234-12',
            author='Some One',
            year='1234',
            list_suffix='a',
            items='12',
            tags='areal,basic',
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
        res.update(kwargs)
        return res
    assert Conceptlist(**kw()).tg

    _kw = kw()
    _kw['api'] = api
    #assert Conceptlist(**kw).tg

    with pytest.raises(ValueError):
        Conceptlist(**kw(year='xy'))

    with pytest.raises(ValueError):
        Conceptlist(**kw(author='a b, c d, e f'))

    with pytest.raises(ValueError):
        Conceptlist(**kw(author=205 * 'x'))
