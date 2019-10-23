"""
Run a number of tests on all concept lists in Concepticon.

Notes
-----
Tests for issues with column names, file names, IDs, source
availability, etc. Best run after you went through the whole
procedure of adding a new list to Concepticon.
"""


def register(parser):
    parser.add_argument(
        'clids',
        metavar='CONCEPTLIST_ID',
        help='Conceptlist IDs to consider for the test. If none are given, **all** will be tested.',
        nargs='*')


def run(args):
    if args.repos.check(*args.clids):
        args.log.info("all integrity tests passed: OK")
    else:  # pragma: no cover
        args.log.error("inconsistent data in repository {0}".format(args.repos.repos))
