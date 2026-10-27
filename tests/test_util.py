import json

import pytest
from csvw.dsv import reader

from pyconcepticon.util import *



def test_UnicodeWriter(tmp_path):
    tst = tmp_path / 'tst'
    with UnicodeWriter(tst) as fp:
        with pytest.raises(AssertionError):
            fp.writeblock([['a', 'b'], ['c', 'd']])
        fp.writerow(['x', 'y'])
        fp.writeblock([['a', 'b'], ['c', 'd']])
    assert tst.read_text('utf8') == "x\ty\n#<<<\t\na\tb\nc\td\n#>>>\t\n"


def test_read_dicts(api):
    res = read_dicts(api.repos / 'concepticondata' / 'concepticon.tsv')
    assert res[0]['ID'] == '1'
    res = read_dicts(
        api.repos / 'concepticondata' / 'concepticon.tsv',
        schema=dict(columns=[dict(datatype='integer', name='ID')]))
    assert res[0]['ID'] == 1


def test_to_dict():
    with pytest.raises(ValueError):
        to_dict([None, None], id)


def test_natural_sort():
    source = ['Elm11', 'Elm12', 'Elm2', 'elm0', 'elm1', 'elm10', 'elm13', 'elm9']
    target = ['elm0', 'elm1', 'Elm2', 'elm9', 'elm10', 'Elm11', 'Elm12', 'elm13']
    assert natural_sort(source) == target


def test_ConceptlistWithNetworksWriter(tmp_path):
    with ConceptlistWithNetworksWriter(tmp_path / 'stuff') as cl:
        cl.append(dict(TEST_CONCEPTS={"1": 2}))
    res = list(reader(tmp_path / 'stuff.tsv', dicts=True, delimiter='\t'))
    assert res[0]['NUMBER'] == '1'
    assert json.loads(res[0]['TEST_CONCEPTS'])['1'] == 2
