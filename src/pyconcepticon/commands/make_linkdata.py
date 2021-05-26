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
    for lang in args.repos.vocabularies["COLUMN_TYPES"].values():
        if getattr(lang, "iso2", None):
            _write_linking_data(args.repos, lang, args)


def _write_linking_data(api, lang, args):
    out, freqs = collections.defaultdict(int), collections.defaultdict(int)
    # find those concept sets that are wrongly linked, they should not go into
    # the mapping, so we just make a re-linker here
    rep = {}
    for c in api.conceptsets.values():
        if c.replacement_id:
            rep[c.id] = c.replacement_id
            rep[c.gloss] = api.conceptsets[c.replacement_id].gloss
        else:
            rep[c.id] = c.id
            rep[c.gloss] = c.gloss

    for clist in api.conceptlists.values():
        args.log.info("checking {clist.id}".format(clist=clist))
        for row in clist.concepts.values():
            if row.concepticon_id:
                gls = None
                if lang.iso2 == "en":
                    if row.english:
                        gls = row.english.strip("*$-—+")
                else:
                    if lang.name in row.attributes and row.attributes[lang.name]:
                        gls = row.attributes[lang.name].strip("*$-—+")

                if gls:
                    out[rep[row.concepticon_gloss] + "///" + gls, rep[row.concepticon_id]] += 1
                    freqs[rep[row.concepticon_id]] += 1

    if lang.iso2 == "en":
        for cset in api.conceptsets.values():
            gloss = rep[cset.gloss]
            cid = rep[cset.id]
            if cset.ontological_category == "Person/Thing":
                out[gloss + "///the " + cset.gloss.lower(), cid] = freqs[cid]
                out[gloss + "///the " + cset.gloss.lower() + "s", cid] = freqs[cid]
            elif cset.ontological_category == "Action/Process":
                out[gloss + "///to " + cset.gloss.lower(), cid] = freqs[cid]
            elif cset.ontological_category == "Property":
                out[gloss + "///" + cset.gloss.lower() + " (adjective)", cid] = freqs[cid]
            elif cset.ontological_category == "Classifier":
                out[gloss + "///" + cset.gloss.lower() + " (classifier)", cid] = freqs[cid]
            else:
                out[gloss + "///" + cset.gloss.lower(), cid] = freqs[cid]

    p = api.path("mappings", "map-{0}.tsv".format(lang.iso2))
    if not p.parent.exists():
        p.parent.mkdir()
    with UnicodeWriter(p, delimiter="\t") as f:
        f.writerow(["ID", "GLOSS", "PRIORITY"])
        for i, (gloss, cid) in enumerate(sorted(out)):
            f.writerow([cid, gloss, out[gloss, cid]])
