"""
Shrink a list using a provided column header as unique label.
This will essentially return the last matching row in the list for each unique value
for the given column.
"""
import collections

from csvw import dsv

from pyconcepticon.cli_util import add_conceptlist, get_conceptlist


def register(parser):
    add_conceptlist(parser)
    parser.add_argument('column', metavar='COLUMN')
    parser.add_argument(
        '--output',
        help="specify output file. If none is given, output will be printed to screen.",
        default=None)


def run(args):
    dicts = list(dsv.reader(get_conceptlist(args, path_only=True), delimiter="\t", dicts=True))
    out_dict = collections.OrderedDict()

    for d in dicts:
        out_dict[d[args.column]] = list(d.values())

    with dsv.UnicodeWriter(args.output, delimiter='\t') as w:
        w.writerow(dicts[0].keys())
        w.writerows(out_dict.values())
    if not args.output:
        print(w.read().decode('utf8'))
