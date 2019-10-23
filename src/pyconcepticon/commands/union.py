"""
Calculate the union of concepts for a number of concept lists.
"""
from pyconcepticon.cli_util import add_conceptlist, get_conceptlist, format_set_operation


def register(parser):
    add_conceptlist(parser, multiple=True)


def run(args):
    format_set_operation(args.repos.union(*get_conceptlist(args)))
