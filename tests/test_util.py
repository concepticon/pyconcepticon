import json

import pytest
from cdstarcat.catalog import Object, Bitstream
from clldutils.jsonlib import load
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


def test_load_conceptlist(tmp_path):
    fname = tmp_path / 'cl.tsv'
    fname.write_text("""\
ID	NUMBER	ENGLISH	PROTOWORLD	CONCEPTICON_ID	CONCEPTICON_GLOSS
Bengtson-1994-27-1	1	mother, older femaile relative	AJA	1216	MOTHER
Bengtson-1994-27-1	2	knee, to bend	BU(N)KA	1371
""", encoding='utf8')

    res = load_conceptlist(fname)
    assert res['splits']
    out = tmp_path / 'clist'
    write_conceptlist(res, out)
    assert out.read_text('utf8')
    visit(lambda l, r: r, str(fname))


def test_SourcesCatalog(tmp_path):
    cat_path = tmp_path / 'test.json'
    with SourcesCatalog(cat_path) as cat:
        cat.add(
            'key', Object('id', [Bitstream('bsid', 5, 'text/plain', '', '', '')], {}))
        assert 'key' in cat
        assert 'url' in cat.get('key')

    assert 'key' in load(str(cat_path))


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
