"""
Recreate the concept lists containing network data.
"""
import json
import shutil
import subprocess
import dataclasses
from typing import Any, Union
import collections
from collections.abc import Sequence

from pyconcepticon.models import CONCEPT_NETWORK_COLUMNS
from pyconcepticon.util import reader


def register(parser):  # pylint: disable=C0116
    parser.add_argument(
        '--download',
        action='store_true',
        default=False,
        help="Also run download script if available")
    parser.add_argument(
        '--diff',
        action='store_true',
        default=False,
        help="Do not overwrite lists, but compute diff")


# A dict represented as sequence of key-value pairs.
HashableDictType = Sequence[tuple[str, Union[str, int, float, Sequence[Union[str, int, float]]]]]
ComparableJsonType = set[HashableDictType]
RowIdColNameType = tuple[str, str]


@dataclasses.dataclass
class NetworkDiffer:
    """
    >>> d = NetworkDiffer()
    >>> d.add_pair('row', 'col', '[{"ID": 5},{"ID": 3}]', '[{"ID": 3},{"ID": 7}]')
    >>> for r, c, old, new in d.iter_diff():
    ...     print(old - new)
    ...     print(new - old)
    ...
    {(('ID', 5),)}
    {(('ID', 7),)}
    """
    pairs: collections.OrderedDict[
        RowIdColNameType, tuple[ComparableJsonType, ComparableJsonType]
    ] = dataclasses.field(default_factory=collections.OrderedDict)

    @staticmethod
    def _hashable_dicts(jsonval) -> set[HashableDictType]:
        return set(
            tuple(sorted([(k, tuple(v) if isinstance(v, list) else v) for k, v in d.items()]))
            for d in json.loads(jsonval or '[]'))

    def add_pair(self, rowid, col, jsonval1, jsonval2):
        self.pairs[rowid, col] = (self._hashable_dicts(jsonval1), self._hashable_dicts(jsonval2))

    def iter_diff(self):
        for (rowid, col), (old, new) in self.pairs.items():
            if old != new:
                yield (
                    rowid,
                    col,
                    [collections.OrderedDict(i) for i in old - new],
                    [collections.OrderedDict(i) for i in new - old])


def diff(new, old):
    differ = NetworkDiffer()
    new = {r['ID']: r for r in reader(new, dicts=True)}
    for oldrow in reader(old, dicts=True):
        for col in CONCEPT_NETWORK_COLUMNS:
            if col in oldrow:
                differ.add_pair(oldrow['ID'], col, oldrow[col], new[oldrow['ID']][col])

    def idname(d: collections.OrderedDict[str, Any]) -> str:
        """Format"""
        rem = '\t'.join(f'{k}: {v}' for k, v in d.items() if k not in ['ID', 'NAME'])
        return f'{d.get("ID", "")}\t{d.get("NAME", "")}\t{rem}'

    for rowid, col, minus, plus in differ.iter_diff():
        print(f'== {rowid}\t{col}')
        for ii in minus:
            print(f'-- {idname(ii)}')
        for ii in plus:
            print(f'++ {idname(ii)}')


def run(args):  # pylint: disable=C0116
    for cl in args.repos.conceptlists.values():
        d = cl.path.parent / cl.path.stem
        if d.exists() and d.is_dir():
            print(d)
            if d.joinpath('download.py').exists() and args.download:  # pragma: no cover
                subprocess.check_call(['python', 'download.py'], cwd=d)
            subprocess.check_call(['python', 'convert.py'], cwd=d)
            if args.diff and cl.path.exists():
                diff(d / cl.path.name, cl.path)
            else:
                shutil.move(d / cl.path.name, cl.path)
