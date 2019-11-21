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
    print(
        "{0} (eds.) {1.year}. {2.title} {1.version}. {2.description}. "
        "{2.publisher.place}: {2.publisher.name}. Available online at {2.url}".format(
            editors, args, args.repos.dataset_metadata,
        ))
