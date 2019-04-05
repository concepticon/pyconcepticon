import csv
import json
import operator
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

from cdstarcat.catalog import Catalog
from clldutils.clilib import ParserError, command
from clldutils.markup import Table
from clldutils.misc import format_size
from clldutils.path import as_unicode, write_text
from tabulate import tabulate
from csvw import Column

from pyconcepticon.api import Concepticon, Conceptlist
from pyconcepticon.util import rewrite, CS_ID, CS_GLOSS, SourcesCatalog, UnicodeWriter, read_dicts


class Linker(object):
    def __init__(self, clid, conceptsets):
        self.clid = clid
        self.concepts = {
            CS_ID: {cs.id: cs.gloss for cs in conceptsets},
            # maps ID to GLOSS
            CS_GLOSS: {cs.gloss: cs.id for cs in conceptsets},
            # maps GLOSS to ID
        }

        self._cid_index = None
        self._cgloss_index = None
        self._link_col = (None, None)
        self._number_index = None

    def __call__(self, i, row):
        if i == 0:
            assert (CS_ID in row) or (CS_GLOSS in row)
            assert "NUMBER" in row
            if (CS_ID in row) and (CS_GLOSS in row):
                self._cid_index = row.index(CS_ID)
                self._cgloss_index = row.index(CS_GLOSS)
            else:
                # either CONCEPTICON_ID or CONCEPTICON_GLOSS is given, and the
                # other is missing.
                add = {CS_ID: CS_GLOSS, CS_GLOSS: CS_ID}
                for j, col in enumerate(row):
                    if col in add:
                        row = [add[col]] + row
                        self._link_col = (j, col)
                        break
            if "ID" not in row:
                self._number_index = row.index("NUMBER")
                row = ["ID"] + row
            return row

        if self._link_col[1]:
            val = self.concepts[self._link_col[1]].get(row[self._link_col[0]], "")
            if not val:
                print("unknown %s: %s" % (self._link_col[1], row[self._link_col[0]]))
            row = [val] + row
        else:
            cid = self.concepts[CS_GLOSS].get(row[self._cgloss_index], "")
            if not cid:
                print("unknown CONCEPTICON_GLOSS: {0}".format(row[self._cgloss_index]))
            elif cid != row[self._cid_index]:
                if not row[self._cid_index]:
                    row[self._cid_index] = cid
                else:
                    print(
                        "unknown CONCEPTICON_ID/GLOSS mismatch: %s %s"
                        % (row[self._cid_index], row[self._cgloss_index])
                    )

        if self._number_index is not None:
            row = ["%s-%s" % (self.clid, row[self._number_index])] + row
        return row


@command()
def link(args):
    """
    Link concepts to concept sets for a given concept list.

    Notes
    -----
    If either CONCEPTICON_GLOSS or CONCEPTICON_ID is given, the other is added.

    Examples
    --------
    $ concepticon link path_to_conceptlist.tsv
    """
    api = Concepticon(args.repos)
    conceptlist = Path(args.args[0])
    if not conceptlist.exists() or not conceptlist.is_file():
        conceptlist = api.data_path("conceptlists", args.args[0])
        if not conceptlist.exists() or not conceptlist.is_file():
            raise ParserError("no file %s found" % args.args[0])

    rewrite(conceptlist, Linker(conceptlist.stem, api.conceptsets.values()))


@command()
def notlinked(args):
    api = Concepticon(args.repos)
    i = 0
    for _, cl in sorted(api.conceptlists.items(), key=lambda p: p[0]):
        for concept in sorted(
                cl.concepts.values(),
                key=lambda p: int(re.match('([0-9]+)', p.number).groups()[0])):
            if not concept.concepticon_id:
                candidates = [c for c in list(api.lookup([concept.label]))[0] if c[3] < 3]
                if candidates:
                    candidate = sorted(candidates, key=lambda c: c[3])[0]
                    candidate = "{0} [{1}]".format(candidate[2], candidate[1])
                    i += 1
                    print("{0} {1.id}: {1.label}: {2}".format(i, concept, candidate))


@command()
def mergers(args):
    """
    Print Concepticon IDs of potential mergers in a given concept list.

    Examples
    --------
    $ concepticon mergers path_to_conceptlist.tsv
    """
    # @todo: check output
    cl = Conceptlist.from_file(args.args[0])
    mapped, mapped_ratio, mergers = cl_stats(cl)
    for k, v in mergers:
        print(k, v)


@command()
def validate(args):
    """
    Checks for the availability of metadata for all concept lists.

    Notes
    -----
    Concept lists have to be included in concepticondata/conceptlists in order
    to be considered.

    Examples
    --------
    $ concepticon validate
    """
    api = Concepticon(args.repos)
    for cl in api.conceptlists.values():
        items = list(cl.metadata)
        if set(items[0].keys()) != set(c.name for c in cl.metadata.tableSchema.columns):
            print("unspecified column in concept list {0}".format(cl.id))


@command()
@Concepticon.app_wrapper
def app(args):  # pragma: no cover
    """
    Dumps Concepticon's contents for English, German, Chinese, and French.

    Notes
    -----
    Data are by default dumped into a structured JSON file in html/data.js.

    Examples
    --------
    $ concepticon html
    """
    data = defaultdict(list)

    def key(g, l):
        return "{0}---{1}".format(g, l)

    for lang in ["en", "de", "zh", "fr", "ru", "es", "pt"]:
        for cidx, gloss in args.api._get_map_for_language(lang):
            g0, _, g1 = gloss.partition("///")
            csspec = (
                cidx,
                args.api.conceptsets[cidx].gloss,
                args.api.conceptsets[cidx].definition,
                args.api.conceptsets[cidx].ontological_category,
            )
            data[key(g1, lang)].append(csspec)
            if lang == "en":
                data[key(g0, lang)].append(csspec)
                data[key(g0.lower(), lang)].append(csspec)
    data["language"] = "en"
    write_text(
        args.api.appdatadir.joinpath("data.js"),
        "var Concepticon = {0};\n".format(json.dumps(data, indent=2)),
    )
    args.log.info("app data recreated")


@command()
def create_metadata(args):
    api = Concepticon(args.repos)
    for cl in api.conceptlists.values():
        mdpath = cl.path.parent.joinpath(cl.path.name + '-metadata.json')
        if not mdpath.exists():
            cols_in_md = []
            for col in cl.metadata.tableSchema.columns:
                cnames = []  # all names or aliases csvw will recognize for this column
                cnames.append(col.name)
                if col.titles:
                    c = col.titles.getfirst()
                    cnames.append(c)
                cols_in_md.extend(cnames)

            for col in cl.cols_in_list:
                if col not in cols_in_md:
                    cl.metadata.tableSchema.columns.append(
                        Column.fromvalue(dict(name=col, datatype='string')))

            cl.tg.to_file(mdpath)


@command()
def attributes(args):
    """
    Print all columns in concept lists that contain surplus information.

    Notes
    -----
    Surplus information are columns not immediately required by Concepticon.

    Examples
    --------
    $ concepticon attributes
    """
    api = Concepticon(args.repos)
    attrs = Counter()
    for cl in api.conceptlists.values():
        attrs.update(cl.attributes)

    print(tabulate(list(attrs.most_common()), headers=("Attribute", "Occurrences")))


def _set_operation(args, type_):
    res = list(Concepticon(args.repos)._set_operation(type_, *args.args))
    if res:
        frmt = "{0:3} {1:1}{2:" + str(max(len(r[2]) for r in res)) + "} [{3:4}] {4}"
        for i, line in enumerate(res):
            print(frmt.format(i + 1, line[0], line[2], line[1], line[3]))
    return res


@command()
def intersection(args):
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

    Examples
    --------
    $ concepticon intersection id-first-list id-second-list id-third-list ...
    """
    return _set_operation(args, "intersection")


@command()
def union(args):
    """
    Calculate the union of concepts for a number of concept lists.

    Examples
    --------
    $ concepticon union id-first-list id-second-list id-third-list ...
    """
    return _set_operation(args, "union")


@command()
def map_concepts(args):
    """
    Attempt an automatic mapping for a new concept list.

    Notes
    -----
    In order for the automatic mapping to work, the new list has to be
    well-formed, i.e. in line with the requirments of Concepticon
    (GLOSS/ENGLISH column, see also CONTRIBUTING.md).

    Examples
    --------
    $ concepticon map_concepts path_to_conceptlist.tsv
    """
    api = Concepticon(args.repos)
    api.map(
        Path(args.args[0]),
        otherlist=args.args[1] if len(args.args) > 1 else None,
        out=args.output,
        full_search=args.full_search,
        language=args.language,
        skip_multiple=args.skip_multimatch,
    )


def readme(outdir, text):
    with outdir.joinpath("README.md").open("w", encoding="utf8") as fp:
        if isinstance(text, list):
            text = "\n".join(text)
        fp.write(text)


@command()
def stats(args):
    """
    Generate new statistics for concepticondata/README.md.

    Examples
    --------
    $ concepticon stats
    """
    api = Concepticon(args.repos)
    cls = api.conceptlists.values()
    readme_conceptlists(api, cls, args)
    readme_concept_list_meta(api)
    readme_concepticondata(api, cls)


def cl_stats(cl):
    """Return simple statistics for a given concept list"""
    # @todo: refine for custom-concept lists
    concepts = cl.concepts.values()
    mapped = [c for c in concepts if c.concepticon_id]
    mapped_ratio = 0
    if concepts:
        mapped_ratio = int((len(mapped) / len(concepts)) * 100)
    concepticon_ids = Counter([c.concepticon_id for c in concepts if c.concepticon_id])
    mergers = [(k, v) for k, v in concepticon_ids.items() if v > 1]

    return mapped, mapped_ratio, mergers


def readme_conceptlists(api, cls, args):
    table = Table("name", "# mapped", "% mapped", "mergers")
    for cl in cls:
        args.log.info("processing <" + cl.path.name + ">")
        mapped, mapped_ratio, mergers = cl_stats(cl)
        table.append(["[%s](%s) " % (cl.id, cl.path.name), len(mapped), mapped_ratio, len(mergers)])
    readme(
        api.data_path("conceptlists"),
        "# Concept Lists\n\n{0}".format(table.render(verbose=True, sortkey=operator.itemgetter(0))),
    )


def readme_concept_list_meta(api):
    """Writes statistics on metadata to readme."""
    txt = "# Basic Statistics on Metadata\n\n{0}"
    cnc = len(api.conceptsets)
    table = Table("provider", "ID", "# concept sets", "% coverage")
    for meta in api.metadata.values():
        n = len(meta.values)
        table.append([meta.meta.get("dc:title"), meta.id, n, (n / cnc) * 100])
    readme(
        api.data_path("concept_set_meta"),
        txt.format(table.render(sortkey=operator.itemgetter(1), reverse=True, condensed=False)),
    )


def readme_concepticondata(api, cls):
    """
    Returns a dictionary with concept set label as value and tuples of concept
    list identifier and concept label as values.
    """
    D, G = defaultdict(list), defaultdict(list)
    labels = Counter()

    for cl in cls:
        for concept in [c for c in cl.concepts.values() if c.concepticon_id]:
            D[concept.concepticon_gloss].append((cl.id, concept.label))
            G[concept.label].append((concept.concepticon_id, concept.concepticon_gloss, cl.id))
            labels.update([concept.label])

    txt = [
        """
# Concepticon Statistics
* concept sets (used): {0}
* concept lists: {1}
* concept labels: {2}
* concept labels (unique): {3}
* Ø concepts per list: {4:.2f}
* Ø concepts per concept set: {5:.2f}
* Ø unique concept labels per concept set: {6:.2f}

""".format(
            len(D),
            len(cls),
            sum(list(labels.values())),
            len(labels),
            sum(list(labels.values())) / len(cls),
            sum([len(v) for k, v in D.items()]) / len(D),
            sum([len(set([label for _, label in v])) for k, v in D.items()]) / len(D),
        )
    ]

    for attr, key in [
        ("Diverse", lambda x: (len(set([label for _, label in x[1]])), x[0] or "")),
        ("Frequent", lambda x: (len(set([clist for clist, _ in x[1]])), x[0] or "18G18G")),
    ]:
        table = Table("No.", "concept set", "distinct labels", "concept lists", "examples")
        for i, (k, v) in enumerate(sorted(D.items(), key=key, reverse=True)[:20]):
            table.append(
                [
                    i + 1,
                    k,
                    len(set([label for _, label in v])),
                    len(set([clist for clist, _ in v])),
                    ", ".join(
                        sorted(set(["«{0}»".format(label.replace("*", "`*`")) for _, label in v]))
                    ),
                ]
            )
        txt.append("## Twenty Most {0} Concept Sets\n\n{1}\n".format(attr, table.render()))

    readme(api.data_path(), txt)
    return D, G


@command()
def upload_sources(args):
    """
    Compile sources and upload the result to GWDG CDSTAR instance.

    Notes
    -----
    CDSTAR authorisation information should be supplied in the form of
    environment variables:
        - CDSTAR_URL
        - CDSTAR_USER
        - CDSTAR_PWD

    Examples
    --------
    $ concepticon upload_sources path/to/cdstar/catalog
    """
    catalog_path = args.args[0] if args.args else os.environ["CDSTAR_CATALOG"]
    toc = ["# Sources\n"]
    api = Concepticon(args.repos)
    with SourcesCatalog(api.data_path("sources", "cdstar.json")) as lcat:
        with Catalog(
            catalog_path,
            cdstar_url=os.environ["CDSTAR_URL"],
            cdstar_user=os.environ["CDSTAR_USER"],
            cdstar_pwd=os.environ["CDSTAR_PWD"],
        ) as cat:
            for fname in sorted(api.data_path("sources").glob("*.pdf"), key=lambda f: f.stem):
                clid = as_unicode(fname.stem)
                spec = lcat.get(clid)
                if not spec:
                    _, _, obj = list(cat.create(fname, {"collection": "concepticon"}))[0]
                    lcat.add(clid, obj)

        for key in sorted(lcat.items):
            spec = lcat.get(key)
            toc.append("- [{0} [PDF {1}]]({2})".format(key, format_size(spec["size"]), spec["url"]))

    readme(api.data_path("sources"), toc)
    print(catalog_path)


@command()
def lookup(args):
    """
    Look up the specified glosses in Concepticon.

    Examples
    --------
    $ concepticon lookup gloss1 gloss2 gloss3 ...
    """
    api = Concepticon(args.repos)
    found = api.lookup(
        args.args,
        language=args.language,
        full_search=args.full_search,
        similarity_level=args.similarity,
    )

    with UnicodeWriter(None) as writer:
        writer.writerow(["GLOSS", "CONCEPTICON_ID", "CONCEPTICON_GLOSS", "SIMILARITY"])
        for matches in found:
            for m in matches:
                writer.writerow(m)
        print(writer.read().decode("utf-8"))


@command()
def check(args):
    """
<<<<<<< HEAD
=======
    Identifies some issues with concept lists.
    -- i.e. multiple words with the same CONCEPTICON_ID or missing definitions

    concepticon check [CONCEPTLIST_ID]+
    """

    def _pprint(clist, error, _id, message):
        print("\t".join([clist.ljust(30), error.ljust(10), "%5s" % _id, message]))

    def _get_mergers(o, api):
        clashes = defaultdict(list)
        for cid, c in o.concepts.items():
            if c.concepticon_id:
                clashes[c.concepticon_id].append(cid)

        for c in sorted([c for c in clashes if len(clashes[c]) > 1]):
            matches = [m for m in o.concepts if o.concepts[m].concepticon_id == c]
            for i, m in enumerate(matches, 1):
                message = '#%d %s = "%s"' % (
                    i,
                    api.conceptsets[c].gloss,
                    getattr(o.concepts[m], "english", ""),
                )
                _pprint(o.id, "MERGE", c, message)

    def _get_missing(o, _):
        for m in o.concepts:
            if o.concepts[m].concepticon_id == "":
                _pprint(o.id, "MISSING", o.concepts[m].number, '"%s"' % o.concepts[m].english)

    api = Concepticon(args.repos)
    for clist in api.conceptlists:
        if (len(args.args) and clist in args.args) or not args.args:
            clist = api.conceptlists[clist]
            _get_missing(clist, api)
            _get_mergers(clist, api)


@command()
def check_new(args):
    """
>>>>>>> 7c8849e71fba5ed827cee356399b123b8097e727
    Perform a number of sanity checks for a new concept list.

    Notes
    -----
    Expects a well-formed concept list as input (i.e. tsv, 'ID',
    'CONCEPTICON_ID', 'NUMBER', 'CONCEPTICON_GLOSS' columns, etc.) and tests
    for a number of potential issues:
        - mismatch between glosses and Concepticon IDs
        - availability of glosses in Concepticon
        - if proposed glosses (starting with !) don't have IDs (they shouldn't!)
        - if glosses are mapped more than once
        - if 'NUMBER' and 'ID' are unique for the respective concept list.

    Examples
    --------
    $ concepticon check path/to/conceptlist.tsv
    """
    list_to_check = read_dicts(args.args[0])
    api = Concepticon(args.repos)
    con_glosses = {c.id: c.gloss for c in api.conceptsets.values()}

    def _get_duplicates(to_check):
        known_items = set()
        return [
            (i, key) for i, key in enumerate(to_check) if key in known_items or known_items.add(key)
        ]

    for index, entry_to_check in enumerate(list_to_check, start=1):
        # Test if gloss matches Concepticon ID:
        msg = "Gloss {0} in line {1} doesn't match ID {2}.".format(
            entry_to_check["CONCEPTICON_GLOSS"], str(index), entry_to_check["CONCEPTICON_ID"]
        )
        try:
            if con_glosses[entry_to_check["CONCEPTICON_ID"]] != entry_to_check["CONCEPTICON_GLOSS"]:
                print(msg)
        except KeyError:
            print(msg)

        # Test if gloss exists in Concepticon:
        msg = "Gloss {0} in line {1} doesn't exist in Concepticon.".format(
            entry_to_check["CONCEPTICON_GLOSS"], str(index)
        )
        try:
            if entry_to_check["CONCEPTICON_GLOSS"] not in con_glosses.values():
                print(msg)
        except KeyError:  # pragma: no cover
            print(msg)

        # Test if proposed glosses (!GLOSS) have NULL ID:
        msg = "Proposed gloss {0} in line {1} shouldn't have a CONCEPTICON_ID.".format(
            entry_to_check["CONCEPTICON_GLOSS"], str(index)
        )
        try:
            if (
                entry_to_check["CONCEPTICON_GLOSS"].startswith("!")
                and entry_to_check["CONCEPTICON_ID"]
            ):
                print(msg)
        except KeyError:  # pragma: no cover
            print(msg)

    print("\nChecking for uniquness of glosses:")
    try:
        for double in _get_duplicates([dict(d)["CONCEPTICON_GLOSS"] for d in list_to_check]):
            print("Gloss " + double[1] + " doubled in line " + str(double[0] + 3) + ".")
    except KeyError:  # pragma: no cover
        pass

    print("\nChecking for uniqueness of 'NUMBER' and 'ID':")
    try:
        for double in _get_duplicates([dict(d)['ID'] for d in list_to_check]):
            print("ID " + double[1] + " doubled in line " + str(double[0] + 2) + ".")

        for double in _get_duplicates([dict(d)['NUMBER'] for d in list_to_check]):
            print("NUMBER " + double[1] + " doubled in line " + str(double[0] + 2) + ".")
    except KeyError:
        pass


@command()
def test(args):  # pragma: no cover
    """
    Run a number of tests on all concept lists in Concepticon.

    Notes
    -----
    Tests for issues with column names, file names, IDs, source
    availability, etc. Best run after you went through the whole
    procedure of adding a new list to Concepticon.

    Examples
    --------
    $ concepticon test
    """
    if Concepticon(args.repos).check(*args.args):
        args.log.info("all integrity tests passed: OK")
    else:
        args.log.error("inconsistent data in repository {0}".format(args.repos))


@command("relink-data")
def recreate_linking_data(args):
    """
    Regenerate <repos>/mappings/map*.

    Notes
    -----
    map* files contain lists of all concept-to-word-in-language mappings
    available within Concepticon.

    Examples
    --------
    $ concepticon recreate_linking_data
    """
    api = Concepticon(args.repos)
    for l in api.vocabularies["COLUMN_TYPES"].values():
        if getattr(l, "iso2", None):
            _write_linking_data(api, l, args)


@command("shrink")
def shrink(args):  # pragma: no cover
    """
    Shrink a list using a provided column header as unique label.

    Examples
    --------
    $ concepticon shrink Bowern-2011-204.tsv CATEGORY
    """
    with open(args.args[0], "r") as f:
        csv_list = list(csv.reader(f, delimiter="\t"))

    header = [x.lower() for x in csv_list[0]]
    head = args.args[1].lower()
    rest = [h for h in header if h != head]

    out_dict = {}

    for line in csv_list[1:]:

        tmp = dict(zip(header, line))

        try:
            for h in rest:
                out_dict[tmp[head]][h] += [tmp[h]]
        except KeyError:
            out_dict[tmp[head]] = {}
            for h in rest:
                out_dict[tmp[head]][h] = [tmp[h]]

    with open(args.args[0].replace(".tsv", ".shrink.tsv"), "w") as f:
        f.write("\t".join([x.upper() for x in [head] + rest]) + "\n")
        for k in sorted(out_dict):

            f.write(k)
            for h in rest:
                f.write("\t" + " / ".join(sorted(set(out_dict[k][h]))))
            f.write("\n")


def _write_linking_data(api, l, args):
    out, freqs = defaultdict(int), defaultdict(int)

    for clist in api.conceptlists.values():
        args.log.info("checking {clist.id}".format(clist=clist))
        for row in clist.concepts.values():
            if row.concepticon_id:
                gls = None
                if l.iso2 == "en":
                    if row.english:
                        gls = row.english.strip("*$-—+")
                else:
                    if l.name in row.attributes and row.attributes[l.name]:
                        gls = row.attributes[l.name].strip("*$-—+")

                if gls:
                    out[row.concepticon_gloss + "///" + gls, row.concepticon_id] += 1
                    freqs[row.concepticon_id] += 1

    if l.iso2 == "en":
        for cset in api.conceptsets.values():
            gloss = cset.gloss
            if cset.ontological_category == "Person/Thing":
                out[gloss + "///the " + cset.gloss.lower(), cset.id] = freqs[cset.id]
                out[gloss + "///the " + cset.gloss.lower() + "s", cset.id] = freqs[cset.id]
            elif cset.ontological_category == "Action/Process":
                out[gloss + "///to " + cset.gloss.lower(), cset.id] = freqs[cset.id]
            elif cset.ontological_category == "Property":
                out[gloss + "///" + cset.gloss.lower() + " (adjective)", cset.id] = freqs[cset.id]
            elif cset.ontological_category == "Classifier":
                out[gloss + "///" + cset.gloss.lower() + " (classifier)", cset.id] = freqs[cset.id]
            else:
                out[gloss + "///" + cset.gloss.lower(), cset.id] = freqs[cset.id]

    p = api.path("mappings", "map-{0}.tsv".format(l.iso2))
    if not p.parent.exists():
        p.parent.mkdir()
    with UnicodeWriter(p, delimiter="\t") as f:
        f.writerow(["ID", "GLOSS", "PRIORITY"])
        for i, (gloss, cid) in enumerate(sorted(out)):
            f.writerow([cid, gloss, out[gloss, cid]])
