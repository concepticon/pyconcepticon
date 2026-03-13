"""
Checks for the availability of metadata for all concept lists.

Notes
-----
Concept lists have to be included in concepticondata/conceptlists in order
to be considered.
"""


def run(args):  # pylint: disable=C0116
    for cl in args.repos.conceptlists.values():
        items = list(cl.metadata)
        if set(items[0].keys()) != set(c.name for c in cl.metadata.tableSchema.columns):
            print(f"unspecified column in concept list {cl.id}")
