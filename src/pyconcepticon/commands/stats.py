"""
Generate new statistics for concepticondata/README.md.
"""
import operator
import collections
import dataclasses

from clldutils.markup import Table

from pyconcepticon.cli_util import readme


def run(args):  # pylint: disable=C0116
    cls = args.repos.conceptlists.values()
    readme_conceptlists(args.repos, cls, args)
    readme_concepticondata(args.repos, cls)


def readme_conceptlists(api, cls, args):
    """Write README.md in the conceptlists directory."""
    table = Table("name", "# mapped", "% mapped", "mergers")
    for cl in cls:
        args.log.info("processing <" + cl.path.name + ">")
        stats = cl.stats()
        table.append([
            f"[{cl.id}]({cl.path.name}) ",
            len(stats.mapped),
            stats.mapped_ratio_percent,
            len(stats.mergers)])
    readme(
        api.data_path("conceptlists"),
        f"# Concept Lists\n\n{table.render(verbose=True, sortkey=operator.itemgetter(0))}",
    )


@dataclasses.dataclass
class Concepts:
    """Container for concept info suitable to derive summary stats."""
    by_concepticon_gloss: dict[str, tuple[str, str]] = dataclasses.field(
        default_factory=lambda: collections.defaultdict(list))
    by_label: dict[str, tuple[str, str, str]] = dataclasses.field(
        default_factory=lambda: collections.defaultdict(list))
    label_counter: dict[str, int] = dataclasses.field(default_factory=collections.Counter)

    def add(self, concept, cl):  # pylint: disable=C0116
        self.by_concepticon_gloss[concept.concepticon_gloss].append((cl.id, concept.label))
        self.by_label[concept.label].append(
            (concept.concepticon_id, concept.concepticon_gloss, cl.id))
        self.label_counter.update([concept.label])

    @property
    def n_conceptsets(self) -> int:  # pylint: disable=C0116
        return len(self.by_concepticon_gloss)

    @property
    def concepts_per_conceptset(self) -> float:  # pylint: disable=C0116
        return sum(len(v) for v in self.by_concepticon_gloss.values()) / self.n_conceptsets

    @property
    def unique_labels_per_conceptset(self) -> float:  # pylint: disable=C0116
        return sum(len({label for _, label in v}) for v in self.by_concepticon_gloss.values()) \
            / self.n_conceptsets


def readme_concepticondata(api, cls):
    """
    Returns a dictionary with concept set label as value and tuples of concept
    list identifier and concept label as values.
    """
    concepts = Concepts()
    for cl in cls:
        for concept in [c for c in cl.concepts.values() if c.concepticon_id]:
            concepts.add(concept, cl)

    txt = [
        "",
        "# Concepticon Statistics",
        f"* concept sets (used): {concepts.n_conceptsets}",
        f"* concept lists: {len(cls)}",
        f"* concept labels: {sum(concepts.label_counter.values())}",
        f"* concept labels (unique): {len(concepts.label_counter)}",
        f"* Ø concepts per list: {sum(concepts.label_counter.values()) / len(cls):.2f}",
        f"* Ø concepts per concept set: {concepts.concepts_per_conceptset:.2f}",
        f"* Ø unique concept labels per concept set: {concepts.unique_labels_per_conceptset:.2f}",
        "",
    ]

    for attr, key in [
        # Most diverse conceptsets, i.e. the ones with the highest number of distinct glosses
        # mapped.
        ("Diverse", lambda x: (-len({label for _, label in x[1]}), x[0] or "")),
        # Most frequent conceptsets, i.e. the ones for which there are concepts in most lists.
        ("Frequent", lambda x: (-len({clist for clist, _ in x[1]}), x[0] or "18G18G")),
    ]:
        table = Table("No.", "concept set", "distinct labels", "concept lists", "examples")
        for i, (k, v) in enumerate(sorted(concepts.by_concepticon_gloss.items(), key=key)[:20]):
            table.append([
                i + 1,
                k,
                len({label for _, label in v}),
                len({clist for clist, _ in v}),
                ", ".join(sorted({f'«{label.replace("*", "`*`")}»' for _, label in v})),
            ])
        txt.append(f"## Twenty Most {attr} Concept Sets\n\n{table.render()}\n")

    readme(api.data_path(), txt)
