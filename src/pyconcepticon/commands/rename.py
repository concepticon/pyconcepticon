"""
Rename a conceptlist,
- propagating the name change to concept IDs,
- properly retiring old concept IDs,
- updating/renaming *-metadata.json and
- updating the conceptlist index.
"""
import collections

from csvw.dsv import UnicodeWriter, reader
from clldutils.clilib import ParserError
from clldutils import jsonlib

from pyconcepticon.models import MD_SUFFIX, CONCEPTLIST_ID_PATTERN


def register(parser):
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


def run(args):
    if not CONCEPTLIST_ID_PATTERN.match(args.to):
        raise ParserError('Invalid conceptlist ID {0}'.format(args.to))
    if args.to in args.repos.conceptlists:
        raise ParserError('Target ID {0} exists!'.format(args.to))
    try:
        cl = args.repos.conceptlists[args.from_]
    except KeyError:
        raise ParserError('Source conceptlist {0} does not exist!'.format(args.from_))

    # write the adapted concept list to the new path:
    with UnicodeWriter(
            cl.path.parent / cl.path.name.replace(args.from_, args.to), delimiter='\t') as writer:
        header = []
        for i, row in enumerate(reader(cl.path, delimiter='\t')):
            if i == 0:
                header = row
                writer.writerow(row)
                header = {v: k for k, v in enumerate(header)}  # Map col name to row index
            else:
                oid = row[header['ID']]
                assert oid.startswith(args.from_)
                nid = oid.replace(args.from_, args.to)
                args.repos.add_retirement(
                    'Concept', dict(id=oid, comment='renaming', replacement=nid))
                row[header['ID']] = nid
                writer.writerow(row)

    # write adapted metadata to the new path:
    fname = cl.path.name.replace(args.from_, args.to) + MD_SUFFIX
    md = jsonlib.load(
        cl.path.parent / (cl.path.name + MD_SUFFIX),
        object_pairs_hook=collections.OrderedDict)
    md['tables'][0]['url'] = fname
    jsonlib.dump(md, cl.path.parent / fname, indent=4)

    # remove obsolete concept list and metadata:
    cl.path.unlink()
    cl.path.parent.joinpath(cl.path.name + MD_SUFFIX).unlink()

    # adapt conceptlists.tsv
    rows = []
    for row in reader(args.repos.data_path('conceptlists.tsv'), delimiter='\t'):
        rows.append([col.replace(args.from_, args.to) if col else col for col in row])

    with UnicodeWriter(args.repos.data_path('conceptlists.tsv'), delimiter='\t') as writer:
        writer.writerows(rows)

    args.repos.add_retirement(
        'Conceptlist', dict(id=args.from_, comment='renaming', replacement=args.to))

    print("""Please run
grep -r "{0}" concepticondata/ | grep -v retired.json

to confirm the renaming was complete!""".format(args.from_))
