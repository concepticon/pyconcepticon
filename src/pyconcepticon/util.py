"""
Utilities.
"""
import re
import json
import pathlib
import operator
import functools
import collections
from collections.abc import Sequence, Iterable
from typing import Any, Optional, Union, TypeVar, Callable

from pycdstar.resource import Object
from clldutils import jsonlib
from csvw import dsv

__all__ = [
    'natural_sort', 'to_dict', 'SourcesCatalog', 'UnicodeWriter', 'reader', 'read_dicts',
    'ConceptlistWithNetworksWriter']

T = TypeVar('T')
PathType = Union[str, pathlib.Path]

REPOS_PATH = pathlib.Path(__file__).parent.parent
PKG_PATH = pathlib.Path(__file__).parent
ID_SEP_PATTERN = re.compile(r'[.,;]')
PREFIX = 'CONCEPTICON'
CS_GLOSS = PREFIX + '_GLOSS'
CS_ID = PREFIX + '_ID'
BIB_PATTERN = re.compile(':bib:(?P<id>[a-zA-Z0-9]+)')

rewrite = functools.partial(dsv.rewrite, delimiter='\t')


def to_dict(
        iterobjects: Iterable[T],
        key: Callable[[T], str] = operator.attrgetter('id'),
) -> collections.OrderedDict[str, T]:
    """
    Turns an iterable into an `OrderedDict` mapping unique keys to items.

    :param iterobjects: an iterable to be turned into the values of the dictionary.
    :param key: a callable which creates a key from an item.
    :returns: `OrderedDict`
    """
    res, keys = collections.OrderedDict(), collections.Counter()
    for obj in iterobjects:
        k = key(obj)
        res[k] = obj
        keys.update([k])
    if keys:
        k, n = keys.most_common(1)[0]
        if n > 1:
            raise ValueError(f'non-unique key: {k}')
    return res


def read_all(fname: PathType, **kw) -> list[dict[str, str]]:
    """Read all rows in a TSV file."""
    kw['dicts'] = True
    kw.setdefault('delimiter', '\t')
    return list(dsv.reader(fname, **kw))


def read_dicts(fname: PathType, schema=None, **kw) -> list[dict[str, Union[str, int, float]]]:
    """Read TSV rows a lightly typed dicts."""
    res = read_all(fname, **kw)
    if schema:
        def identity(x):
            return x
        colspec = {}
        for col in schema['columns']:
            conv = {'integer': int, 'float': float}.get(col['datatype'])
            colspec[col['name']] = conv or identity
        res = [{k: colspec.get(k, identity)(v) for k, v in d.items()} for d in res]
    return res


def reader(p, **kw):
    """Convenience wrapper prepping dsv.reader for tab-separated values."""
    kw.setdefault('delimiter', '\t')
    return dsv.reader(p, **kw)


class UnicodeWriter(dsv.UnicodeWriter):
    """A tab-separated values writer with a custom method."""
    def __init__(self, *args, **kw):
        kw.setdefault('delimiter', '\t')
        self._rownum = None
        super().__init__(*args, **kw)

    def writerow(self, row):
        if self._rownum is None:
            self._rownum = len(row)
        dsv.UnicodeWriter.writerow(self, row)

    def writeblock(self, rows, start='#<<<', end='#>>>'):
        """
        Write "commented" rows, i.e. rows enclosed in a start and an end row of a particular format.
        """
        assert self._rownum
        self.writerow([start] + (self._rownum - 1) * [''])
        for row in rows:
            self.writerow(row)
        self.writerow([end] + (self._rownum - 1) * [''])


def lowercase(d: dict[str, Any]) -> dict[str, Any]:
    """Lowercases first-level dict keys."""
    return {k.lower(): v for k, v in d.items()}


def unique(iterable: Iterable[T]) -> list[T]:
    """List of unique items in iterable."""
    return list(sorted(set(i for i in iterable if i)))


def split(s: str, sep: str = ',') -> list[str]:
    """Unique items separated by sep in s."""
    return unique(ss.strip() for ss in s.split(sep) if ss.strip())


def split_ids(s: str) -> list[str]:
    """Unique IDs in s."""
    return unique(id_.strip() for id_ in ID_SEP_PATTERN.split(s) if id_.strip())


def natural_sort(string: Sequence[str]) -> list[str]:
    """
    >>> natural_sort(['b123', 'a234'])
    ['a234', 'b123']
    """
    def alphanum_key(key):
        return [int(c) if c.isdigit() else c.lower() for c in re.split('([0-9]+)', key)]

    return sorted(string, key=alphanum_key)


class ConceptlistWithNetworksWriter(list):
    """
    Support for writing conceptlists which contain concept networks.
    """
    def __init__(self, name):
        self.name = name
        list.__init__(self)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        assert self, 'empty list'
        header = list(self[0].keys())
        if 'NUMBER' not in header:
            header.insert(0, 'NUMBER')
        header.insert(0, 'ID')
        with UnicodeWriter(f'{self.name}.tsv', delimiter="\t") as writer:
            writer.writerow(header)
            for i, row in enumerate(self, start=1):
                if 'NUMBER' not in row:
                    row['NUMBER'] = str(i)
                row['ID'] = f"{self.name}-{row['NUMBER']}"
                writer.writerow([
                    json.dumps(row[key]) if key.endswith('_CONCEPTS') else row[key]
                    for key in header])


class SourcesCatalog:
    """A catalog for the metadata of conceptlist sources."""
    def __init__(self, path):
        self.path = pathlib.Path(path)
        self.items: dict[str, dict[str, Any]] = {}
        if self.path.exists():
            self.items = jsonlib.load(self.path)

    def __contains__(self, item):
        return item in self.items

    def get(self, item) -> Optional[dict[str, Any]]:  # pylint: disable=C0116
        return self.items.get(item)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        jsonlib.dump(
            collections.OrderedDict(
                [(k, collections.OrderedDict(sorted(v.items())))
                 for k, v in sorted(self.items.items())]),
            self.path,
            indent=4)

    def add(self, key: str, obj: Object) -> dict[str, Any]:
        """Add the metadata of a pycdstar Object to the catalog."""
        bsid = obj.bitstreams[0].id
        self.items[key] = collections.OrderedDict([
            ('url', f'https://cdstar.eva.mpg.de/bitstreams/{obj.id}/{bsid}'),
            ('objid', obj.id),
            ('original', bsid),
            ('size', obj.bitstreams[0].size),
            ('mimetype', obj.bitstreams[0].mimetype),
        ])
        return self.items[key]
