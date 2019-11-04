import shutil
import shlex
import logging
import collections

import pytest
from clldutils.path import copy
from clldutils.misc import nfilter

from pyconcepticon.util import read_all
from pyconcepticon.__main__ import main


@pytest.fixture
def _main(tmprepos):
    def f(*args):
        if len(args) == 1:
            args = shlex.split(args[0])
        main(args=['--repos', str(tmprepos)] + list(args), log=logging.getLogger('test'))
    return f


def test_help(_main, capsys):
    _main()
    out, err = capsys.readouterr()
    assert 'make_app' in out


def test_validate(capsys, _main):
    _main('validate')
    out, err = capsys.readouterr()
    assert 'unspecified column' in out


def test_make_app(_main):
    _main('make_linkdata')
    _main('make_app')
    _main('make_app')


def test_rename(capsys, _main, tmprepos):
    _main('create_metadata')
    _main('rename', 'Sun-1991-1004', 'Moon-2011-234')
    assert tmprepos.joinpath('concepticondata/conceptlists/Moon-2011-234.tsv').exists()


def test_upload_sources(_main, mocker, tmprepos):
    tmprepos.joinpath('c').write_text('{}', encoding='utf8')
    mocker.patch(
        'pyconcepticon.commands.upload_sources.os',
        mocker.Mock(environ=collections.defaultdict(lambda: 'x')))
    _main('upload_sources', '--cdstar-catalog', str(tmprepos / 'c'))


def test_notlinked(_main, capsys):
    _main('notlinked')
    out, _ = capsys.readouterr()
    assert 'Sun-1991-1004-275' in out


def test_test(_main):
    _main('test')


def test_make_linkdata(tmprepos, _main, caplog):
    shutil.rmtree(str(tmprepos / 'mappings'))
    with caplog.at_level(logging.INFO):
        _main('make_linkdata')
    assert caplog.records
    assert 'checking' in caplog.records[-1].message
    assert tmprepos.joinpath('mappings').exists()


def test_create_metadata(tmprepos, _main):
    mdpath = tmprepos / 'concepticondata' / 'conceptlists' / 'Perrin-2010-110.tsv-metadata.json'
    assert not mdpath.exists()
    _main('create_metadata')
    assert mdpath.exists()


def test_check(fixturedir, capsys, mocker, tmpdir, _main):
    test = tmpdir.join('Sun-1991-1004.tsv')
    copy(fixturedir.joinpath('concepticondata/conceptlists/Sun-1991-1004.tsv'), str(test))
    _main('check', str(test))
    out, err = capsys.readouterr()
    assert 'Sun-1991-1004-2 ' not in out
    assert 'fast (adv.)' in out

    t = test.read_text(encoding='utf8')
    test.write_text(t.replace('Sun-1991-1004-1', 'Sun-1991-1004-2'), encoding='utf8')
    _main('check', str(test))
    out, err = capsys.readouterr()
    print(out)
    assert 'Sun-1991-1004-2 ' in out


def test_shring(_main, capsys):
    _main('shrink', 'Sun-1991-1004', 'CONCEPTICON_GLOSS')
    out, _ = capsys.readouterr()
    assert 500 < len(out.split('\n')) < 1000


def test_mergers(_main):
    _main('mergers', 'Sun-1991-1004')


def test_map_concepts(_main):
    _main('map_concepts', 'Sun-1991-1004')


def test_link(fixturedir, tmpdir, capsys, _main):
    with pytest.raises(SystemExit):
        _main('link', '.')

    def nattr(p, attr):
        return len(nfilter([getattr(i, attr, None) for i in read_all(str(p))]))

    test = tmpdir.join('test.tsv')
    copy(fixturedir.joinpath('conceptlist.tsv'), str(test))
    assert nattr(test, 'CONCEPTICON_GLOSS') == 0
    _main('link', str(test))
    assert nattr(test, 'CONCEPTICON_GLOSS') == 1

    copy(fixturedir.joinpath('conceptlist2.tsv'), str(test))
    _main('link', str(test))
    out, err = capsys.readouterr()
    assert 'unknown CONCEPTICON_GLOSS' in out
    assert 'mismatch' in out


def test_stats(_main, tmprepos):
    assert not tmprepos.joinpath('concepticondata', 'README.md').exists()
    _main('stats')
    assert tmprepos.joinpath('concepticondata', 'README.md').exists()


def test_attributes(_main, capsys):
    _main('attributes')
    out, err = capsys.readouterr()
    assert 'Occurrences' in out


def test_union(capsys, _main):
    _main('union','Perrin-2010-110', 'Sun-1991-1004' )
    out, err = capsys.readouterr()
    assert 920 == len(out.split('\n'))


def test_intersection(capsys, _main):
    _main('intersection','Perrin-2010-110', 'Sun-1991-1004' )
    out, err = capsys.readouterr()
    assert 69 == len(out.split('\n'))


def test_lookup(capsys, _main):
    _main('lookup', '--full-search', '--language', 'en', 'sky')
    out, err = capsys.readouterr()
    assert '1732' in out

    _main('lookup', '--language', 'en', 'sky')
    out, err = capsys.readouterr()
    assert '1732' in out
