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

from clldutils.clilib import ArgumentParserWithLogging

from pyconcepticon import commands
assert commands


def main():  # pragma: no cover
    parser = ArgumentParserWithLogging(__name__)
    parser.add_argument(
        '--repos',
        help="path to concepticon-data",
        default=Path('.'))
    parser.add_argument(
        '--skip_multimatch',
        help="",
        default=False,
        action='store_true')
    parser.add_argument(
        '--full_search',
        help="select between approximate search (default) and full search",
        default=False,
        action='store_true')
    parser.add_argument(
        '--output',
        help="specify output file",
        default=None)
    parser.add_argument(
        '--similarity',
        help="specify level of similarity for concept mapping",
        default=5,
        type=int)
    parser.add_argument(
        '--language',
        help="specify your desired language for mapping",
        default='en',
        type=str)
    sys.exit(parser.main())
