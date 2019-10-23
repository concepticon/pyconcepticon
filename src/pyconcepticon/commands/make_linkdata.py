"""
Regenerate <repos>/mappings/map*.

Notes
-----
map* files contain lists of all concept-to-word-in-language mappings
available within Concepticon.
"""
import collections

from csvw.dsv import UnicodeWriter


def run(args):
    for l in args.repos.vocabularies["COLUMN_TYPES"].values():
        if getattr(l, "iso2", None):
            _write_linking_data(args.repos, l, args)


def _write_linking_data(api, l, args):
    out, freqs = collections.defaultdict(int), collections.defaultdict(int)

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
