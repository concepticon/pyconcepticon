"""
Rename a conceptlist,
- propagating the name change to concept IDs,
- properly retiring old concept IDs,
- updating/renaming *-metadata.json and
- updating the conceptlist index.
"""
import collections

from clldutils.clilib import ParserError
from clldutils import jsonlib

from pyconcepticon.models import MD_SUFFIX, CONCEPTLIST_ID_PATTERN
from pyconcepticon.util import UnicodeWriter, reader, rewrite


def register(parser):  # pylint: disable=C0116
    parser.add_argument(
        'from_',
        metavar='FROM',
        help='old ID of conceptlist',
    )
    parser.add_argument(
        'to',
        metavar='TO',
        help='new ID of conceptlist',
    )


def run(args):  # pylint: disable=C0116
    if not CONCEPTLIST_ID_PATTERN.match(args.to):
        raise ParserError(f'Invalid conceptlist ID {args.to}')  # pragma: no cover
    if args.to in args.repos.conceptlists:
        raise ParserError(f'Target ID {args.to} exists!')  # pragma: no cover
    try:
        cl = args.repos.conceptlists[args.from_]
    except KeyError as e:  # pragma: no cover
        raise ParserError(f'Source conceptlist {args.from_} does not exist!') from e

    def retire(what, from_, to_):
        args.repos.add_retirement(what, {'id': from_, 'comment': 'renaming', 'replacement': to_})

    # write the adapted concept list to the new path:
    with UnicodeWriter(cl.path.parent / cl.path.name.replace(args.from_, args.to)) as writer:
        header: dict[str, int] = {}
        for i, row in enumerate(reader(cl.path)):
            if i == 0:
                header = {v: k for k, v in enumerate(row)}  # Map col name to row index
            else:
                oid = row[header['ID']]
                assert oid.startswith(args.from_)
                nid = oid.replace(args.from_, args.to)
                retire('Concept', oid, nid)
                row[header['ID']] = nid
            writer.writerow(row)

    # write adapted metadata to the new path:
    fname_md = cl.path.name.replace(args.from_, args.to) + MD_SUFFIX
    fname_url = cl.path.name.replace(args.from_, args.to)
    md = jsonlib.load(
        cl.path.parent / (cl.path.name + MD_SUFFIX),
        object_pairs_hook=collections.OrderedDict)
    md['tables'][0]['url'] = fname_url
    jsonlib.dump(md, cl.path.parent / fname_md, indent=4)

    # remove obsolete concept list and metadata:
    cl.path.unlink()
    cl.path.parent.joinpath(cl.path.name + MD_SUFFIX).unlink()

    # adapt conceptlists.tsv
    rewrite(
        args.repos.data_path('conceptlists.tsv'),
        lambda _, row: [col.replace(args.from_, args.to) if col else col for col in row])

    retire('Conceptlist', args.from_, args.to)
    print(f'Please run\n'
          f'grep -r "{args.from_}" concepticondata/ | grep -v retired.json'
          f'\n\nto confirm the renaming was complete!')
