"""
Regenerate <repos>/mappings/map*.

Notes
-----
map* files contain lists of all concept-to-word-in-language mappings
available within Concepticon.
"""
import functools
import collections

from pyconcepticon.util import UnicodeWriter


def run(args):  # pylint: disable=C0116
    rep = _current_conceptsets(args.repos)
    for lang in args.repos.vocabularies["COLUMN_TYPES"].values():
        if getattr(lang, "iso2", None):
            args.log.info(lang)
            _write_linking_data(args.repos, lang, rep)


def _current_conceptsets(api):
    """
    find those concept sets that are wrongly linked, they should not go into
    the mapping, so we just make a re-linker here
    """
    rep = {}
    for c in api.conceptsets.values():
        if c.replacement_id:
            rep[c.id] = c.replacement_id
            rep[c.gloss] = api.conceptsets[c.replacement_id].gloss
        else:
            rep[c.id] = c.id
            rep[c.gloss] = c.gloss
    return rep


def _local_gloss(rep, concepticon_gloss, local):
    return f'{rep[concepticon_gloss]}///{local}'


def _get_frequencies(api, lang, rep):
    out, freqs = collections.defaultdict(int), collections.defaultdict(int)
    local_gloss = functools.partial(_local_gloss, rep)

    for clist in api.conceptlists.values():
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
                    out[local_gloss(row.concepticon_gloss, gls), rep[row.concepticon_id]] += 1
                    freqs[rep[row.concepticon_id]] += 1
    return out, freqs


def _write_linking_data(api, lang: str, rep):
    out, freqs = _get_frequencies(api, lang, rep)

    if lang.iso2 == "en":
        for cset in api.conceptsets.values():
            lgloss = cset.gloss.lower()

            if cset.ontological_category == "Person/Thing":
                lgloss = "the " + lgloss
                out[_local_gloss(rep, cset.gloss, lgloss + "s"), rep[cset.id]] = freqs[rep[cset.id]]
            elif cset.ontological_category == "Action/Process":
                lgloss = "to " + lgloss
            elif cset.ontological_category == "Property":
                lgloss += " (adjective)"
            elif cset.ontological_category == "Classifier":
                lgloss += " (classifier)"

            out[_local_gloss(rep, cset.gloss, lgloss), rep[cset.id]] = freqs[rep[cset.id]]

    p = api.path("mappings", f"map-{lang.iso2}.tsv")
    if not p.parent.exists():
        p.parent.mkdir()
    with UnicodeWriter(p) as f:
        f.writerow(["ID", "GLOSS", "PRIORITY"])
        for gloss, cid in sorted(out):
            f.writerow([cid, gloss, out[gloss, cid]])
