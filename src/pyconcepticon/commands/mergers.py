"""
Print Concepticon IDs of potential mergers in a given concept list.
"""
from pyconcepticon.cli_util import add_conceptlist, get_conceptlist


def register(parser):
    add_conceptlist(parser)


def run(args):
    # @todo: check output
    for k, v in get_conceptlist(args).stats().mergers:
        print(k, v)
