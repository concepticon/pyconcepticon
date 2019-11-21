"""
Main command line interface of the pyconcepticon package.

Like programs such as git, this cli splits its functionality into sub-commands
(see e.g. https://docs.python.org/2/library/argparse.html#sub-commands).
The rationale behind this is that while a lot of different tasks may be triggered using
this cli, most of them require common configuration.

The basic invocation looks like

    concepticon [OPTIONS] <command> [args]

"""
import sys
from pathlib import Path
import contextlib
from clldutils.clilib import register_subcommands, get_parser_and_subparsers, ParserError
from clldutils.loglib import Logging
try:
    import cldfcatalog
    NO_CAT = None
except ImportError as e:
    NO_CAT = e

from pyconcepticon import Concepticon
import pyconcepticon.commands


def main(args=None, catch_all=False, parsed_args=None, log=None):
    repos = None
    if not NO_CAT:
        try:
            repos = cldfcatalog.Config.from_file().get_clone('concepticon')
        except KeyError:  # pragma: no cover
            pass
    repos = repos or Path('.')
    parser, subparsers = get_parser_and_subparsers('concepticon')
    parser.add_argument(
        '--repos',
        help="clone of concepticon/concepticon-data",
        default=repos,
        type=Path)
    parser.add_argument(
        '--repos-version',
        help="version of repository data. Requires a git clone!",
        default=None)
    register_subcommands(subparsers, pyconcepticon.commands)

    args = parsed_args or parser.parse_args(args=args)

    if not hasattr(args, "main"):
        parser.print_help()
        return 1

    with contextlib.ExitStack() as stack:
        if not log:  # pragma: no cover
            stack.enter_context(Logging(args.log, level=args.log_level))
        else:
            args.log = log
        if args.repos_version:  # pragma: no cover
            # If a specific version of the data is to be used, we make
            # use of a Catalog as context manager:
            if NO_CAT:
                print(NO_CAT)
                return 1
            stack.enter_context(cldfcatalog.Catalog(args.repos, tag=args.repos_version))
        args.repos = Concepticon(args.repos)
        args.log.info('concepticon/concepticon-data at {0}'.format(args.repos.repos))
        try:
            return args.main(args) or 0
        except KeyboardInterrupt:  # pragma: no cover
            return 0
        except ParserError as e:
            print(e)
            return main([args._command, '-h'])
        except Exception as e:  # pragma: no cover
            if catch_all:
                print(e)
                return 1
            raise


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main() or 0)
