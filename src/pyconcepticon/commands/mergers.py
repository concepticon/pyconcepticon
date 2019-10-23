"""
Print Concepticon IDs of potential mergers in a given concept list.
"""
from pyconcepticon.cli_util import add_conceptlist, get_conceptlist


def register(parser):
    add_conceptlist(parser)


def run(args):
    # @todo: check output
    cl = get_conceptlist(args)
    mapped, mapped_ratio, mergers = cl.stats()
    for k, v in mergers:
        print(k, v)
