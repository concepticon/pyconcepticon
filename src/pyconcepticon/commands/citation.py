"""
Print a full bibliographic citation for a Concepticon version
"""
from datetime import date

from clldutils.path import git_describe
from nameparser import HumanName


def register(parser):
    parser.add_argument('--version', default=None)
    parser.add_argument('--year', default=date.today().year, type=int)


def run(args):
    if not args.version:  # pragma: no cover
        args.version = git_describe(args.repos.repos)
        if args.version.startswith('v'):
            args.version = args.version[1:]
    editors = []
    for e in args.repos.editors:
        if ((not e.end) or (int(e.end) >= args.year)) and int(e.start) <= args.year:
            name = HumanName(e.name)
            editors.append('{0.last}, {0.first} {0.middle}'.format(name).strip())
    editors = ' & '.join(editors)
    print("{0} (eds.) {1.year}. Concepticon {1.version}. "
          "A Resource for the Linking of Concept Lists. "
          "Jena: Max Planck Institute for the Science of Human History. "
          "Available online at https://concepticon.clld.org".format(editors, args))
