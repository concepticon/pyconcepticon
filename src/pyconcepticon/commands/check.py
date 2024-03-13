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
import collections

import termcolor
from clldutils.clilib import Table, add_format

from pyconcepticon.cli_util import add_conceptlist, get_conceptlist
from pyconcepticon.util import read_dicts, CS_ID, CS_GLOSS
from pyconcepticon.models import CONCEPT_NETWORK_COLUMNS

import json


def register(parser):
    add_conceptlist(parser, multiple=True)
    add_format(parser, default='simple')
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='print check descriptions',
        default=False)


def run(args):
    for cl in get_conceptlist(args, path_only=True):
        print(termcolor.colored(cl, attrs=['bold', 'underline']))
        items = list(enumerate(read_dicts(cl), start=2))
        for check in CHECKS:
            print(termcolor.colored('Check: {0}'.format(check.__name__), attrs=['bold']))
            if args.verbose and check.__doc__:
                print(check.__doc__)  # pragma: no cover
            try:
                check(items, args)
            except Exception as e:  # pragma: no cover
                print(termcolor.colored('{0}: {1}'.format(e.__class__.__name__, e), color='red'))
        print()


#
# helpers
#
class Result(Table):
    def __exit__(self, exc_type, *args):
        if self:
            super().__exit__(exc_type, *args)
        else:
            if not exc_type:
                print(termcolor.colored('OK', color='green'))


def id_number_gloss(item):
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


def valid_concepticon_id(items, args):
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
            print(termcolor.colored('no column {0}'.format(' or '.join(cols)), color='red'))
            return
        col = col[0]
        clashes[item[col]].append([line] + id_number_gloss(item))

    with Result(args, col, 'LINE_NO', 'ID', 'NUMBER', 'GLOSS') as t:
        for val in sorted(c for c in clashes if len(clashes[c]) > 1):
            for item in clashes[val]:
                t.append([val] + item)


def unique_concepticon_gloss(items, args):
    _unique(items, args, CS_ID, CS_GLOSS)


def unique_id(items, args):
    _unique(items, args, 'ID')


def unique_number(items, args):
    _unique(items, args, 'NUMBER')


def good_graph(items, args):
    cids = {
        "ID": {b["ID"] for a, b in items},
        "NAME": {b.get("ENGLISH", b.get("GLOSS")) for a, b in items}}
    # name suffixes for columns
    all_problems = collections.OrderedDict({
        "ID": {name: [] for name in CONCEPT_NETWORK_COLUMNS},
        "NAME": {name: [] for name in CONCEPT_NETWORK_COLUMNS}
    })

    for cid, concept in items:
        for name in CONCEPT_NETWORK_COLUMNS:
            nodes_ = concept.get(name)
            if nodes_:
                nodes = json.loads(nodes_)
                for node in nodes:
                    for itm in ["ID", "NAME"]:
                        if not node.get(itm) or not node.get(itm) in cids[itm]:
                            all_problems[itm][name].append([cid] + id_number_gloss(concept))

    graph_problems = []
    # assemble edges and make sure they make sense
    edges, id2num = collections.defaultdict(dict), {}
    for i, (cid, concept) in enumerate(items):
        # LINKED_CONCEPTS are considered undirected. They may be specified twice - i.e. in both
        # directions - but then they must carry the same exact attributes.
        nodes_ = concept.get("LINKED_CONCEPTS")
        id2num[concept["ID"]] = (concept["NUMBER"], i + 2)
        if nodes_:
            nodes = json.loads(nodes_)
            for node in nodes:
                for k, v in node.items():
                    if isinstance(v, (float, int)):
                        edges[concept["ID"], node["ID"]][k] = v
    for nA, nB in list(edges):
        if (nB, nA) in edges:  # Check attributes:
            for attr in edges[nA, nB]:
                if edges[nA, nB][attr] != edges[nB, nA].get(attr):
                    graph_problems.append([
                        "different values for {} / {} in {}".format(nA, nB, attr),
                        id2num[nA][1], nA, id2num[nA][0]])

    with Result(args, "good graph", 'LINE_NO', 'ID', 'NUMBER', 'GLOSS') as t:
        for item, problems in all_problems.items():
            for name in CONCEPT_NETWORK_COLUMNS:
                for problem in problems[name]:
                    problem.insert(
                        0,
                        "Attribute {} in column {}_CONCEPTS does not occur in concept list".format(
                            item, name))
                    t.append(problem)
        for problem in graph_problems:
            t.append(problem)


CHECKS = [
    unique_concepticon_gloss,
    unique_id,
    unique_number,
    matching_concepticon_gloss_and_id,
    valid_concepticon_gloss,
    valid_concepticon_id,
    good_graph
]
