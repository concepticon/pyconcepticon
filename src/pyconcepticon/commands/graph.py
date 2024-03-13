"""
Converts a concept list into a graph.

Notes
-----
Expects well-formed concept lists as input, i.e. TSV files, with columns
- ID
- CONCEPTICON_ID
- NUMBER
- CONCEPTICON_GLOSS
"""
from clldutils.clilib import Table, add_format

from pyconcepticon.cli_util import add_conceptlist, get_conceptlist
from pyconcepticon.util import read_dicts

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
    parser.add_argument(
        '--weights',
        action='store',
        type=lambda x: x.split(","),
        default=[],
        help='specify weights to be listed in the graph, separated by comma.'
    )


def run(args):
    header = args.weights

    with Table(args, *["SOURCE_ID", "SOURCE_NAME", "TARGET_ID", "TARGET_NAME"] + header) as t:
        for idx, item in enumerate(read_dicts(get_conceptlist(args, path_only=True)[0]), start=2):
            links = json.loads(item[args.graph_column])
            source_id, source_name = (item["ID"], item.get("ENGLISH", item.get("GLOSS", "?")))
            for link in links:
                link_id, link_name = link["ID"], link["NAME"]
                if args.threshold and args.threshold_property:
                    if link[args.threshold_property] < args.threshold:
                        continue
                if not header:
                    header = [key for key in link if key not in ["ID", "NAME"]]
                t.append([source_id, source_name, link_id, link_name] + [link[h] for h in header])
