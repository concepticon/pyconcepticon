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
                print(check.__doc__)
            try:
                check(items, args)
            except Exception as e:
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
                    t.append([cid, cgloss, line] + id_number_gloss(item))


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
                t.append([cgloss, line] + id_number_gloss(item))


def provisional_concepticon_gloss(items, args):
    """
    If CONCEPTICON_GLOSS is prefixed with "!", it must not have a CONCEPTICON_ID.
    """
    with Result(
            args, 'CONCEPTICON_GLOSS', 'CONCEPTICON_ID', 'LINE_NO', 'ID', 'NUMBER', 'GLOSS') as t:
        for line, item in items:
            cid = item.get(CS_ID)
            cgloss = item.get(CS_GLOSS)
            if cid and cgloss and cgloss.startswith('!'):
                t.append([cgloss, cid, line] + id_number_gloss(item))


def _unique(items, args, *cols):
    col = None
    clashes = collections.defaultdict(list)
    for line, item in items:
        col = [c for c in cols if c in item]
        if not col:
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


CHECKS = [
    unique_concepticon_gloss,
    unique_id,
    unique_number,
    matching_concepticon_gloss_and_id,
    valid_concepticon_gloss,
]
