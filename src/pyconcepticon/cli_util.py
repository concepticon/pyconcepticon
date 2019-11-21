import pathlib

from clldutils.clilib import ParserError

from pyconcepticon.models import Conceptlist


def format_set_operation(res):
    frmt = "{0:3} {1:1}{2:" + str(max(len(r[2]) for r in res)) + "} [{3:4}] {4}"
    for i, line in enumerate(res or []):
        print(frmt.format(i + 1, line[0], line[2], line[1], line[3]))


def readme(outdir, text):
    outdir.joinpath("README.md").write_text(
        "\n".join(text) if isinstance(text, list) else text, encoding="utf8")


def add_search(parser):
    parser.add_argument(
        '--full-search',
        help="select between approximate search (default) and full search",
        default=False,
        action='store_true')
    parser.add_argument(
        '--language',
        help="specify your desired language for mapping",
        default='en',
        type=str)


def add_conceptlist(parser, multiple=False):
    kw = dict(
        metavar='CONCEPTLIST',
        help='Path to (or ID of) concept list in TSV format',
        type=pathlib.Path)
    if multiple:
        kw['nargs'] = '+'
    parser.add_argument('conceptlist', **kw)


def get_conceptlist(args, path_only=False):
    if isinstance(args.conceptlist, list):
        return [_get_conceptlist(cl, args, path_only=path_only) for cl in args.conceptlist]
    return _get_conceptlist(args.conceptlist, args, path_only=path_only)


def _get_conceptlist(cl, args, path_only=False):
    cl = pathlib.Path(cl)
    if cl.exists() and cl.is_file():
        if path_only:
            return cl
        return Conceptlist.from_file(cl)  # pragma: no cover

    if cl.parent.name == '':
        if path_only:
            name = cl.name
            if not name.endswith('.tsv'):
                name += '.tsv'
            p = args.repos.data_path('conceptlists', name)
            if p.exists():
                return p
        else:
            if cl.name in args.repos.conceptlists:
                return args.repos.conceptlists[cl.name]

    raise ParserError("no conceptlist %s found" % cl)
