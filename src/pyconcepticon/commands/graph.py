"""
Identifies problems with concept lists.

Notes
-----
Expects well-formed concept lists as input, i.e. TSV files, with columns
- ID
- CONCEPTICON_ID
- NUMBER
- CONCEPTICON_GLOSS
"""
import collections

import termcolor
from clldutils.clilib import Table, add_format

from pyconcepticon.cli_util import add_conceptlist, get_conceptlist
from pyconcepticon.util import read_dicts, CS_ID, CS_GLOSS

import json


def register(parser):
    add_conceptlist(parser, multiple=True)
    add_format(parser, default='simple')
    parser.add_argument(
            "--graph-column",
            action="store",
            default="LINKED_CONCEPTS",
            help="specify the column containing linked concepts")
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='print check descriptions',
        default=False)
    parser.add_argument(
        "--threshold",
        action='store',
        type=int,
        help='set the threshold for the inclusion of an edge',
        default=0)
    parser.add_argument(
        '--threshold-property',
        action='store',
        type=str,
        default='',
        help='specify weight column for computing thresholds.')


def run(args):
    cl = get_conceptlist(args, path_only=True)[0]        
    items = list(enumerate(read_dicts(cl), start=2))
    
    edges = []
    header = []

    if args.graph_column == "LINKED_CONCEPTS":
        directed = False
    for idx, item in items:
        links = json.loads(item[args.graph_column])
        source_id, source_name = (
                item["ID"],
                item.get("ENGLISH", item.get("GLOSS", "?")),
                )
        for link in links:
            link_id, link_name = link["ID"], link["NAME"]
            valid_row = True
            if args.threshold and args.threshold_property:
                if link[args.threshold_property] < args.threshold:
                    valid_row = False
            if valid_row:
                if not header:
                    for key in link:
                        if key not in ['ID', 'NAME']:
                            header += [key]
                row = [source_id, source_name, link_id, link_name]
                for h in header:
                    row += [link[h]]
                edges += [row]
    with Table(
            args, 
            *[
                "SOURCE_ID", "SOURCE_NAME", "TARGET_ID", 
                "TARGET_NAME"] + header) as t:
        for row in edges:
            t.append(row)













