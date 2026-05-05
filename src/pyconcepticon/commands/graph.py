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
import json
import dataclasses
from typing import Any

from clldutils.clilib import Table, add_format

from pyconcepticon.cli_util import add_conceptlist, get_conceptlist
from pyconcepticon.util import read_dicts


def register(parser):  # pylint: disable=C0116
    add_conceptlist(parser, multiple=True)
    add_format(parser, default='simple')
    parser.add_argument(
        "--graph-column",
        action="store",
        default="LINKED_CONCEPTS",
        help="specify the column containing linked concepts")
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


@dataclasses.dataclass(frozen=True)
class Link:
    """A Link is a JSON object in a graph-valued column, linking to a conceptset."""
    id: str
    name: str
    properties: dict[str, Any]

    @classmethod
    def from_json_object(cls, obj: dict[str, Any]):
        """Turn JSON object into a Link."""
        return cls(id=obj.pop('ID'), name=obj.pop('NAME'), properties=obj)


@dataclasses.dataclass(frozen=True)
class GraphItem:
    """A list of graph nodes specified in a column in c conceptlist."""
    links: list[Link]
    id: str
    gloss: str


def run(args):  # pylint: disable=C0116
    header, rows = args.weights, []

    for item in read_dicts(get_conceptlist(args, path_only=True)[0]):
        item: GraphItem = GraphItem(
            links=[Link.from_json_object(obj) for obj in json.loads(item[args.graph_column])],
            id=item["ID"],
            gloss=item.get("ENGLISH", item.get("GLOSS", "?")))

        for link in item.links:
            if args.threshold and args.threshold_property:
                if link.properties[args.threshold_property] < args.threshold:
                    continue
            if not header:
                header = list(link.properties.keys())
            rows.append(
                [item.id, item.gloss, link.id, link.name] + [link.properties[h] for h in header])

    with Table(args, "SOURCE_ID", "SOURCE_NAME", "TARGET_ID", "TARGET_NAME", *header) as t:
        for row in rows:
            t.append(row)
