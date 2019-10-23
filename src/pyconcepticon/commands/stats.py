"""
Generate new statistics for concepticondata/README.md.
"""
import operator
import collections

from clldutils.markup import Table

from pyconcepticon.cli_util import readme


def run(args):
    cls = args.repos.conceptlists.values()
    readme_conceptlists(args.repos, cls, args)
    readme_concept_list_meta(args.repos)
    readme_concepticondata(args.repos, cls)


def readme_conceptlists(api, cls, args):
    table = Table("name", "# mapped", "% mapped", "mergers")
    for cl in cls:
        args.log.info("processing <" + cl.path.name + ">")
        mapped, mapped_ratio, mergers = cl.stats()
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
    D, G = collections.defaultdict(list), collections.defaultdict(list)
    labels = collections.Counter()

    for cl in cls:
        for concept in [c for c in cl.concepts.values() if c.concepticon_id]:
            D[concept.concepticon_gloss].append((cl.id, concept.label))
            G[concept.label].append((concept.concepticon_id, concept.concepticon_gloss, cl.id))
            labels.update([concept.label])

    txt = ["""
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
    )]

    for attr, key in [
        ("Diverse", lambda x: (len(set([label for _, label in x[1]])), x[0] or "")),
        ("Frequent", lambda x: (len(set([clist for clist, _ in x[1]])), x[0] or "18G18G")),
    ]:
        table = Table("No.", "concept set", "distinct labels", "concept lists", "examples")
        for i, (k, v) in enumerate(sorted(D.items(), key=key, reverse=True)[:20]):
            table.append([
                i + 1,
                k,
                len(set([label for _, label in v])),
                len(set([clist for clist, _ in v])),
                ", ".join(
                    sorted(set(["«{0}»".format(label.replace("*", "`*`")) for _, label in v]))
                ),
            ])
        txt.append("## Twenty Most {0} Concept Sets\n\n{1}\n".format(attr, table.render()))

    readme(api.data_path(), txt)
    return D, G
