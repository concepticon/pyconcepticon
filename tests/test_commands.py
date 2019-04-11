from collections import namedtuple
from pathlib import Path
import shutil

import pytest
from clldutils.path import copy
from clldutils.misc import nfilter
from clldutils.clilib import ParserError

from pyconcepticon.util import read_all
from pyconcepticon import __main__


def test_validate(fixturedir, mocker, capsys):
    from pyconcepticon.commands import validate
    validate(mocker.MagicMock(repos=fixturedir))
    out, err = capsys.readouterr()
    assert 'unspecified column' in out


def test_relink_data(tmprepos, mocker, capsys):
    from pyconcepticon.commands import recreate_linking_data

    shutil.rmtree(str(tmprepos / 'mappings'))
    recreate_linking_data(mocker.Mock(repos=tmprepos, log=mocker.Mock(info=print)))
    out, _ = capsys.readouterr()
    assert 'checking' in out
    assert tmprepos.joinpath('mappings').exists()


def test_create_metadata(tmprepos, mocker):
    from pyconcepticon.commands import create_metadata

    mdpath = tmprepos / 'concepticondata' / 'conceptlists' / 'Perrin-2010-110.tsv-metadata.json'
    assert not mdpath.exists()
    create_metadata(mocker.Mock(repos=tmprepos))
    assert mdpath.exists()


def test_check(fixturedir, capsys, mocker, tmpdir):
    from pyconcepticon.commands import check

    test = tmpdir.join('Sun-1991-1004.tsv')
    copy(fixturedir.joinpath('concepticondata/conceptlists/Sun-1991-1004.tsv'), str(test))
    check(mocker.Mock(args=str(test), repos=fixturedir))
    out, err = capsys.readouterr()
    assert '#1 FAST = "fast"' in out

    t = test.read_text(encoding='utf8')
    test.write_text(t.replace('1631', '111111'), encoding='utf8')
    check(mocker.Mock(args=str(test), repos=fixturedir))
    out, err = capsys.readouterr()
    assert '#1 FAST = "fast' in out


def test_link(mocker, fixturedir, tmpdir, capsys):
    from pyconcepticon.commands import link

    with pytest.raises(ParserError):
        link(mocker.Mock(args=['.'], repos=fixturedir))

    def nattr(p, attr):
        return len(nfilter([getattr(i, attr, None) for i in read_all(str(p))]))

    test = tmpdir.join('test.tsv')
    copy(fixturedir.joinpath('conceptlist.tsv'), str(test))
    assert nattr(test, 'CONCEPTICON_GLOSS') == 0
    link(mocker.Mock(args=[str(test)], repos=fixturedir))
    assert nattr(test, 'CONCEPTICON_GLOSS') == 1

    copy(fixturedir.joinpath('conceptlist2.tsv'), str(test))
    link(mocker.Mock(args=[str(test)], repos=fixturedir))
    out, err = capsys.readouterr()
    assert 'unknown CONCEPTICON_GLOSS' in out
    assert 'mismatch' in out


def test_readme(tmpdir):
    from pyconcepticon.commands import readme

    readme(Path(str(tmpdir)), ['a', 'b'])
    assert tmpdir.join('README.md').ensure()


def test_stats(mocker, fixturedir):
    from pyconcepticon.commands import stats

    readme = mocker.Mock()
    mocker.patch('pyconcepticon.commands.readme', readme)
    stats(mocker.MagicMock(repos=fixturedir))
    assert readme.call_count == 3


def test_attributes(mocker, capsys, fixturedir):
    from pyconcepticon.commands import attributes

    attributes(mocker.MagicMock(repos=fixturedir))
    out, err = capsys.readouterr()
    assert 'Occurrences' in out


def test_union(capsys, fixturedir):
    from pyconcepticon.commands import union
    Args = namedtuple('Args', ['repos', 'args'])

    union(Args(repos=fixturedir, args=['Perrin-2010-110', 'Sun-1991-1004']))
    out, err = capsys.readouterr()
    assert 920 == len(out.split('\n'))


def test_intersection(capsys, fixturedir):
    from pyconcepticon.commands import intersection
    Args = namedtuple('Args', ['repos', 'args'])

    intersection(Args(repos=fixturedir, args=['Perrin-2010-110', 'Sun-1991-1004']))
    out, err = capsys.readouterr()
    assert 69 == len(out.split('\n'))


def test_lookup(capsys, mocker, fixturedir):
    from pyconcepticon.commands import lookup

    lookup(mocker.MagicMock(repos=fixturedir, full_search=True, args=['sky'], language='en'))
    out, err = capsys.readouterr()
    assert '1732' in out

    lookup(mocker.MagicMock(repos=fixturedir, args=['sky'], language='en'))
    out, err = capsys.readouterr()
    assert '1732' in out
