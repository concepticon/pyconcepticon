"""
Identifies problems with concept lists.

Notes
-----
Expects well-formed concept lists as input, i.e. TSV files, with columns
- ID
- CONCEPTICON_ID
- NUMBER
- CONCEPTICON_GLOSS
"""
import json
import argparse
import collections
from collections.abc import Generator
import dataclasses
from typing import Optional, Any

import termcolor
from clldutils.clilib import Table, add_format

from pyconcepticon.cli_util import add_conceptlist, get_conceptlist
from pyconcepticon.util import read_dicts, CS_ID, CS_GLOSS
from pyconcepticon.models import CONCEPT_NETWORK_COLUMNS

ItemListType = list[tuple[int, dict[str, str]]]


def register(parser):  # pylint: disable=C0116
    add_conceptlist(parser, multiple=True)
    add_format(parser, default='simple')
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='print check descriptions',
        default=False)


def run(args):  # pylint: disable=C0116
    for cl in get_conceptlist(args, path_only=True):
        print(termcolor.colored(cl, attrs=['bold', 'underline']))
        items: ItemListType = list(enumerate(read_dicts(cl), start=2))
        for check in CHECKS:
            print(termcolor.colored(f'Check: {check.__name__}', attrs=['bold']))
            if args.verbose and check.__doc__:
                print(check.__doc__)  # pragma: no cover
            try:
                check(items, args)
            except Exception as e:  # pragma: no cover  # pylint: disable=W0718
                print(termcolor.colored(f'{e.__class__.__name__}: {e}', color='red'))
        print()


#
# helpers
#
class Result(Table):
    """Results, i.e. error reporter."""
    def __exit__(self, exc_type, *args):
        if self:  # There are table rows, so render them.
            super().__exit__(exc_type, *args)
        else:
            if not exc_type:
                print(termcolor.colored('OK', color='green'))


def id_number_gloss(item):  # pylint: disable=C0116
    return [item.get('ID', ''), item.get('NUMBER', ''), item.get('GLOSS', item.get('ENGLISH', ''))]


#
# check implementations
#
def matching_concepticon_gloss_and_id(items, args):
    """
    CONCEPTICON_ID and CONCEPTICON_GLOSS must match the corresponding values of **one**
    Concepticon Conceptset.
    """
    with Result(
            args, 'CONCEPTICON_ID', 'CONCEPTICON_GLOSS', 'LINE_NO', 'ID', 'NUMBER', 'GLOSS') as t:
        for line, item in items:
            cid = item.get(CS_ID)
            cgloss = item.get(CS_GLOSS)
            if cid and cgloss:
                cs = args.repos.conceptsets[cid]
                if cs.gloss != cgloss:
                    t.append([cid, cgloss, line] + id_number_gloss(item))  # pragma: no cover


def valid_concepticon_gloss(items, args):
    """
    CONCEPTICON_GLOSS - if given - must match corresponding value of a Concepticon Conceptset.
    """
    valid = set(cs.gloss for cs in args.repos.conceptsets.values())
    with Result(
            args, 'CONCEPTICON_GLOSS', 'LINE_NO', 'ID', 'NUMBER', 'GLOSS') as t:
        for line, item in items:
            cgloss = item.get(CS_GLOSS)
            if cgloss and cgloss not in valid:
                t.append([cgloss, line] + id_number_gloss(item))  # pragma: no cover


def valid_concepticon_id(items, args):  # pylint: disable=C0116
    valid = set(cs.id for cs in args.repos.conceptsets.values() if not cs.replacement_id)
    with Result(
            args, 'CONCEPTICON_ID', 'LINE_NO', 'ID', 'NUMBER', 'GLOSS') as t:
        for line, item in items:
            cid = item.get(CS_ID)
            if cid and cid not in valid:
                t.append([cid, line] + id_number_gloss(item))  # pragma: no cover


def _unique(items, args, *cols):
    col = None
    clashes = collections.defaultdict(list)
    for line, item in items:
        col = [c for c in cols if c in item]
        if not col:  # pragma: no cover
            print(termcolor.colored(f'no column {" or ".join(cols)}', color='red'))
            return
        col = col[0]
        clashes[item[col]].append([line] + id_number_gloss(item))

    with Result(args, col, 'LINE_NO', 'ID', 'NUMBER', 'GLOSS') as t:
        for val in sorted(c for c in clashes if len(clashes[c]) > 1):
            for item in clashes[val]:
                t.append([val] + item)


def unique_concepticon_gloss(items, args):  # pylint: disable=C0116
    _unique(items, args, CS_ID, CS_GLOSS)


def unique_id(items, args):  # pylint: disable=C0116
    _unique(items, args, 'ID')


def unique_number(items, args):  # pylint: disable=C0116
    _unique(items, args, 'NUMBER')


@dataclasses.dataclass(frozen=True)
class NetworkValue:
    """The value of a network column in a conceptlist with metadata."""
    line_no: int
    row: dict[str, Any]
    network_col: str
    nodes: list[dict[str, Any]]


def _iter_nodelists(items, cols=CONCEPT_NETWORK_COLUMNS) -> Generator[NetworkValue, None, None]:
    for cid, concept in items:
        for name in cols:
            nodes = concept.get(name)
            if nodes:
                yield NetworkValue(cid, concept, name, json.loads(nodes))


def _iter_duplicate_edges(
        items
) -> Generator[tuple[tuple[str, str], dict[str, Any], dict[str, Any]], None, None]:
    edges = collections.defaultdict(dict)
    for nv in _iter_nodelists(items, cols=['LINKED_CONCEPTS']):
        # LINKED_CONCEPTS are considered undirected. They may be specified twice - i.e. in both
        # directions - but then they must carry the same exact attributes.
        for node in nv.nodes:
            for k, v in node.items():
                if isinstance(v, (float, int)):
                    edges[nv.row["ID"], node["ID"]][k] = v

    keys = list(edges)
    for a, b in keys:
        if (a, b) in edges and (b, a) in edges:
            yield (a, b), edges.pop((a, b)), edges.pop((b, a))


@dataclasses.dataclass(frozen=True)
class Problem:
    """Error reporting for the concept network check."""
    comment: str
    line_no: int
    id: str
    number: str
    gloss: Optional[str] = None


def good_graph(items: ItemListType, args: argparse.Namespace):
    """Check node dicts of a concept networks."""
    cids = {
        "ID": {b["ID"] for _, b in items},
        "NAME": {b.get("ENGLISH", b.get("GLOSS")) for _, b in items}}
    id2num = {concept['ID']: (concept['NUMBER'], lid) for lid, concept in items}
    problems: list[Problem] = []

    for nv in _iter_nodelists(items):
        for node in nv.nodes:
            for itm in ["ID", "NAME"]:
                if not node.get(itm) or not node.get(itm) in cids[itm]:
                    problems.append(
                        Problem(
                            f"Attribute {itm} in column {nv.network_col} not in concept list",
                            nv.line_no,
                            *id_number_gloss(nv.row)))

    for (n_a, n_b), props_a, props_b in _iter_duplicate_edges(items):
        for attr in props_a:
            if props_a[attr] != props_b.get(attr):
                problems.append(
                    Problem(
                        f"different values for {n_a} / {n_b} in {attr}",
                        id2num[n_a][1],
                        n_a,
                        id2num[n_a][0]))

    with Result(args, "good graph", 'LINE_NO', 'ID', 'NUMBER', 'GLOSS') as t:
        for problem in problems:
            t.append(dataclasses.astuple(problem))


CHECKS = [
    unique_concepticon_gloss,
    unique_id,
    unique_number,
    matching_concepticon_gloss_and_id,
    valid_concepticon_gloss,
    valid_concepticon_id,
    good_graph
]
