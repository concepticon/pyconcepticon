"""
Attempt an automatic mapping for a new concept list.

Notes
-----
In order for the automatic mapping to work, the new list has to be
well-formed, i.e. in line with the requirments of Concepticon
(GLOSS/ENGLISH column, see also CONTRIBUTING.md).
"""
from pyconcepticon.cli_util import add_conceptlist, get_conceptlist, _get_conceptlist, add_search


def register(parser):
    add_conceptlist(parser)
    parser.add_argument(
        '--reference-list',
        metavar='REFLIST',
        help='Another concept list to be used as reference for the gloss mapping',
        default=None)
    add_search(parser)
    parser.add_argument(
        '--skip_multimatch',
        help="",
        default=False,
        action='store_true')
    parser.add_argument(
        '--output',
        help="specify output file",
        default=None)


def run(args):
    args.repos.map(
        get_conceptlist(args, path_only=True),
        otherlist=_get_conceptlist(
            args.reference_list, args, path_only=True) if args.reference_list else None,
        out=args.output,
        full_search=args.full_search,
        language=args.language,
        skip_multiple=args.skip_multimatch,
    )
