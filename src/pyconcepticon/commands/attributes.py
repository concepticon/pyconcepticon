"""
Print all columns in concept lists that contain surplus information.

Notes
-----
Surplus information are columns not immediately required by Concepticon.
"""
import collections

from clldutils.clilib import Table, add_format


def register(parser):
    add_format(parser, default='simple')
    parser.add_argument(
        '--min-occurs',
        type=int,
        help='minimal number of conceptlists an attribute occurs in',
        default=1,
    )


def run(args):
    attrs = collections.Counter()
    for cl in args.repos.conceptlists.values():
        attrs.update(cl.attributes)

    with Table(
            args,
            'Attribute', 'Occurrences',
            rows=[(k, v) for k, v in attrs.most_common() if v >= args.min_occurs]):
        pass
