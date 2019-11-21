"""
Compile sources and upload the result to GWDG CDSTAR instance.

CDSTAR authorisation information should be supplied in the form of
environment variables
- CDSTAR_URL,
- CDSTAR_USER and
- CDSTAR_PWD
"""
import os
import pathlib

from cdstarcat.catalog import Catalog
from clldutils.misc import format_size

from pyconcepticon.util import SourcesCatalog
from pyconcepticon.cli_util import readme


def register(parser):
    parser.add_argument(
        '--cdstar-catalog',
        default=os.environ.get("CDSTAR_CATALOG"),
        help='Path to global CDSTAR catalog')


def run(args):
    toc = ["# Sources\n"]
    with SourcesCatalog(args.repos.data_path("sources", "cdstar.json")) as lcat:
        with Catalog(
            pathlib.Path(args.cdstar_catalog),
            cdstar_url=os.environ["CDSTAR_URL"],
            cdstar_user=os.environ["CDSTAR_USER"],
            cdstar_pwd=os.environ["CDSTAR_PWD"],
        ) as cat:  # pragma: no cover
            for fname in sorted(
                    args.repos.data_path("sources").glob("*.pdf"), key=lambda f: f.stem):
                clid = fname.stem
                spec = lcat.get(clid)
                if not spec:
                    _, _, obj = list(cat.create(fname, {"collection": "concepticon"}))[0]
                    lcat.add(clid, obj)

        for key in sorted(lcat.items):
            spec = lcat.get(key)
            toc.append("- [{0} [PDF {1}]]({2})".format(key, format_size(spec["size"]), spec["url"]))

    readme(args.repos.data_path("sources"), toc)
