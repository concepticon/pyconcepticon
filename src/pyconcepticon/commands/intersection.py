"""
Compute the intersection of concepts for a number of concept lists.

Notes
-----
This takes concept relations into account by searching for each concept
set for broader concept sets in the depth of two edges on the network. If
one concept A in one list is broader than concept B in another list, the
concept A will be retained, and this will be marked in output. If two lists
share the same broader concept, they will also be retained, but only, if
none of the narrower concepts match. As a default we use a depth of 2 for
the search.
"""
from pyconcepticon.cli_util import add_conceptlist, get_conceptlist, format_set_operation


def register(parser):
    add_conceptlist(parser, multiple=True)


def run(args):
    format_set_operation(args.repos.intersection(*get_conceptlist(args)))
