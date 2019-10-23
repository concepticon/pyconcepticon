"""
Look up the specified glosses in Concepticon.
"""
from clldutils.clilib import Table, add_format

from pyconcepticon.cli_util import add_search


def register(parser):
    parser.add_argument('gloss', metavar='GLOSS', nargs='+')
    add_format(parser, default='simple')
    parser.add_argument(
        '--similarity',
        help="specify level of similarity for concept mapping",
        default=5,
        type=int)
    add_search(parser)


def run(args):
    found = args.repos.lookup(
        args.gloss,
        language=args.language,
        full_search=args.full_search,
        similarity_level=args.similarity,
    )
    with Table(args, "GLOSS", "CONCEPTICON_ID", "CONCEPTICON_GLOSS", "SIMILARITY") as t:
        for matches in found:
            t.extend(matches)
