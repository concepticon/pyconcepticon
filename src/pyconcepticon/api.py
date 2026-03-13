"""
API to curate and access Concepticon data.
"""
import re
from typing import Any, Optional, Union, TypedDict, Literal
import pathlib
import warnings
import functools
import collections
from collections.abc import Iterable, Container
import dataclasses

import cldfcatalog
import simplepybtex.database
from clldutils import jsonlib
from clldutils.apilib import API
from clldutils.markup import iter_markdown_tables
from clldutils.source import Source

from pyconcepticon.glosses import concept_map, concept_map2, MappingDict, map_list, MapOptions, \
    Similarity, GlossLanguage
# The following symbols from models can explicitly be imported from pyconcepticon.api:
from pyconcepticon.models import (  # noqa: F401
    Languoid, Concept, Conceptlist, ConceptRelations, Conceptset, REF_PATTERN, MD_SUFFIX,
)
from pyconcepticon.util import read_dicts, lowercase, to_dict, BIB_PATTERN

assert MD_SUFFIX and Concept
Editor = collections.namedtuple('Editor', ['name', 'start', 'end'])
PathType = Union[str, pathlib.Path]
ResourceType = Literal["Concept", "Conceptset", "Conceptlist"]


class Retirement(TypedDict):
    """Retirements are stored as JSON objects."""
    id: str
    comment: str
    replacement: str


class Concepticon(API):
    """
    API to access the concepticon data.

    Objects for the various types of data stored in concepticon-data can be accessed as
    dictionaries mapping object IDs to specific object type instances.
    """
    __default_metadata__ = {
        'url': 'https://concepticon.clld.org',
        'title': 'Concepticon',
        'description': 'A Resource for the Linking of Concept Lists',
        'publisher.name': 'Max Planck Institute for Evolutionary Anthropology',
        'publisher.place': 'Leipzig',
        'publisher.url': 'https://www.eva.mpg.de',
        'publisher.contact': 'concepticon@eva.mpg.de',
    }

    def __init__(self, repos: Optional[PathType] = None):
        """
        :param repos: Path to a clone or source dump of concepticon-data.
        """
        repos = repos or cldfcatalog.Config.from_file().get_clone('concepticon')
        API.__init__(self, repos)
        self._to_mapping = {}

    def data_path(self, *comps: str) -> pathlib.Path:
        """
        Create a path relative to the `concepticondata` directory within the source repos.
        """
        return self.path('concepticondata', *comps)

    @functools.cached_property
    def editors(self) -> list[Editor]:
        """The Concepticon editors, current and earlier."""
        res = []
        _, rows = next(
            iter_markdown_tables(self.path('CONTRIBUTORS.md').read_text(encoding='utf8')))
        for (period, name) in rows:
            start, to_, end = period.strip().partition('-')
            start, end = start.strip(), end.strip()
            res.append(Editor(name.strip(), start, start if not to_ else end or None))
        return res

    @functools.cached_property
    def vocabularies(self) -> dict[str, dict]:
        """
        Provide access to a `dict` of controlled vocabularies.
        """
        res = jsonlib.load(self.data_path('concepticon.json'))
        for k in res['COLUMN_TYPES']:
            v = res['COLUMN_TYPES'][k]
            if isinstance(v, list) and v and v[0] == 'languoid':
                res['COLUMN_TYPES'][k] = Languoid(k, *v[1:])
        return res

    @property
    def bibfile(self) -> pathlib.Path:  # pylint: disable=C0116
        return self.data_path('references', 'references.bib')

    @functools.cached_property
    def sources(self) -> dict[str, dict[str, Any]]:  # pylint: disable=C0116
        return jsonlib.load(self.data_path('sources', 'cdstar.json'))

    @functools.cached_property
    def retirements(self) -> dict[str, list[Retirement]]:
        """Lists of retirements by resource type."""
        return jsonlib.load(
            self.data_path('retired.json'), object_pairs_hook=collections.OrderedDict)

    def add_retirement(self, type_: ResourceType, repl: Retirement):
        """Add info about a retired object to the retirements registry."""
        obj = collections.OrderedDict()
        for k in Retirement.__annotations__:
            obj[k] = repl[k]
            assert obj[k]
        if type_ not in self.retirements:
            self.retirements[type_] = []
        # It feels a bit hacky to mutate a cached property - but it works.
        self.retirements[type_].append(obj)
        jsonlib.dump(self.retirements, self.data_path('retired.json'), indent=2)

    @functools.cached_property
    def bibliography(self) -> dict[str, Source]:
        """
        :returns: `dict` mapping BibTeX IDs to `Reference` instances.
        """
        return to_dict(
            Source.from_entry(key, entry) for key, entry in simplepybtex.database.parse_string(
                self.bibfile.read_text(encoding='utf8'), bib_format='bibtex').entries.items())

    @functools.cached_property
    def conceptsets(self) -> dict[str, Conceptset]:
        """
        :returns: `dict` mapping ConceptSet IDs to `Conceptset` instances.
        """
        return to_dict(
            Conceptset(_api=self, **lowercase(d))
            for d in read_dicts(self.data_path('concepticon.tsv')))

    @functools.cached_property
    def conceptlists_dicts(self) -> list[dict[str, Union[str, int, float]]]:
        """Read items in conceptlists.tsv into dicts."""
        return read_dicts(self.data_path('conceptlists.tsv'))

    @functools.cached_property
    def conceptlists(self) -> dict[str, Conceptlist]:
        """
        :returns: `dict` mapping ConceptList IDs to `Conceptlist` instances.

        .. note:: Individual concepts can be accessed via `Conceptlist.concepts`.
        """
        return to_dict(Conceptlist(_api=self, **lowercase(d)) for d in self.conceptlists_dicts)

    @functools.cached_property
    def relations(self) -> ConceptRelations:
        """
        :returns: `dict` mapping concept sets to related concepts.
        """
        return ConceptRelations(self.data_path('conceptrelations.tsv'))

    @functools.cached_property
    def multirelations(self) -> ConceptRelations:
        """
        :returns: `dict` mapping concept sets to related concepts.
        """
        return ConceptRelations(self.data_path('conceptrelations.tsv'), multiple=True)

    @functools.cached_property
    def frequencies(self) -> collections.Counter:
        """Maps concepticon conceptset glosses to the number of concepts linked to them."""
        d = collections.Counter()
        for cl in self.conceptlists.values():
            d.update(
                concept.concepticon_gloss for concept in cl.concepts.values()
                if concept.concepticon_id)
        return d

    def _get_map_for_language(
            self,
            language,
            otherlist: Optional[PathType] = None,
    ) -> list[Union[tuple[str, str], tuple[str, str, str]]]:
        if (language, otherlist) not in self._to_mapping:
            if otherlist is not None:
                to = []
                for item in read_dicts(otherlist):
                    to.append((item['ID'], item.get('GLOSS', item.get('ENGLISH'))))
            else:
                mapfile = self.repos / 'mappings' / f'map-{language}.tsv'
                to = [(cs['ID'], cs['GLOSS']) for cs in read_dicts(mapfile)]
            self._to_mapping[(language, otherlist)] = to
        return self._to_mapping[(language, otherlist)]

    def map(self,  # pylint: disable=R0913,R0917
            clist,
            otherlist=None,
            out=None,
            full_search: bool = False,
            similarity_level: Optional[Union[Similarity, int]] = Similarity.SAME_LONGEST,
            language: Optional[Union[GlossLanguage, str]] = GlossLanguage.ENGLISH,
            skip_multiple: bool = False):
        """Map items in a conceptlist to concepticon."""
        map_list(
            clist,
            self._get_map_for_language(language, otherlist),
            out=out,
            options=MapOptions(
                full_search=full_search,
                similarity_level=Similarity.from_int(similarity_level),
                language=GlossLanguage.from_string(language),
                skip_multiple=skip_multiple,
            ),
        )

    def lookup(  # pylint: disable=R0913,R0917
            self,
            entries: Iterable[str],
            full_search: bool = False,
            similarity_level=5,
            language='en',
            mincsid=None,
            to=None,
    ):
        """
        :returns: `generator` of tuples (searchterm, concepticon_id, concepticon_gloss, similarity).
        """
        if to is None:
            to = [t for t in self._get_map_for_language(language, None)
                  if mincsid is None or (int(t[0]) >= mincsid)]
        cmap: MappingDict = (concept_map2 if full_search else concept_map)(
            entries,
            [i[1] for i in to],
            similarity_level=similarity_level,
            language=language)
        for i, e in enumerate(entries):
            mapping = cmap.get_mapping(i)
            yield {
                (e, to[m][0], to[m][1].split("///")[0], mapping.similarity)
                for m in mapping.to_keys}

    def check(self, *clids) -> bool:
        """Returns the success of the checks."""
        assert self.retirements
        print(f'testing {len(clids) if clids else len(self.conceptlists)} concept lists')

        with Checker(self) as checker:
            checker.check_conceptlists(clids)
            if checker.errors:  # pragma: no cover
                return False  # Exit early in case of structural errors.

            # Make sure all language-specific mappings are well specified
            checker.check_language_mappings()

            # We collect all cite keys used to refer to references.
            all_refs: set[str] = set()
            refs_in_bib: set[str] = set(ref for ref in self.bibliography)

            # Make sure only records in the BibTeX file references.bib are referenced by
            # concept lists.
            for i, cl in enumerate(self.conceptlists.values()):
                if not (clids and cl.id not in clids):
                    checker.check_refs(cl, i, refs_in_bib, all_refs)

            all_refs.add('List2016a')

            if not clids:
                # Only report unused references if we check all concept lists!
                for ref in refs_in_bib - all_refs:  # pragma: no cover
                    checker.error(f'unused bibtex record: {ref}', 'references.bib')

            checker.check_relations()

            for fname in self.data_path('conceptlists').glob('*.tsv'):
                if clids and fname.stem not in clids:
                    continue  # pragma: no cover
                if fname.stem not in self.conceptlists:  # pragma: no cover
                    checker.error(f'conceptlist missing in conceptlists.tsv: {fname.name}')

            broken_cls = []

            for cl in self.conceptlists.values():
                if clids and cl.id not in clids:
                    continue  # pragma: no cover

                # Check consistency between the csvw metadata and the column names in the list.
                checker.check_schema(cl, broken_cls)

            checker.check_conceptsets(broken_cls)

        return not bool(checker.errors)


@dataclasses.dataclass
class Checker:
    """Implements consistency checks for the concepticon data."""
    api: Concepticon
    errors: list = dataclasses.field(default_factory=list)
    ref_without_label_pattern: re.Pattern = re.compile(r'[^]]\(:(ref|bib):[A-Za-z0-9\-]+\)')
    ref_without_link_pattern: re.Pattern = re.compile('[^(]:(ref|bib):[A-Za-z0-9-]+')

    concepticon_ids: set[str] = dataclasses.field(default_factory=set)
    concepticon_glosses: set[str] = dataclasses.field(default_factory=set)

    def __post_init__(self):
        self.concepticon_ids = set(self.api.conceptsets.keys())
        self.concepticon_glosses = set(cs.gloss for cs in self.api.conceptsets.values())

    @staticmethod
    def _msg(type_, msg, name, line):  # pragma: no cover  # pylint: disable=C0116
        if line:
            line = f':{line}'
        return f"{type_.upper()}:{name}{line or ''}: {msg}"

    def error(self, msg, name=None, line=0):  # pragma: no cover  # pylint: disable=C0116
        self.errors.append((msg, name, line))

    @classmethod
    def warning(cls, msg, name, line=0):  # pragma: no cover  # pylint: disable=C0116
        warnings.warn(cls._msg('warning', msg, name, line), Warning)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for msg, name, line in self.errors:
            print(self._msg('error', msg, name, line))

    def check_conceptlists(self, clids: Optional[Union[Container[str], Iterable[str]]] = None):
        """Make sure Conceptlist objects can be instantiated."""
        for i, d in enumerate(self.api.conceptlists_dicts, start=1):
            if (not clids) or d['ID'] in clids:
                try:
                    Conceptlist(_api=self, **lowercase(d))
                except ValueError as e:  # pragma: no cover
                    self.error(str(e), 'conceptlists.tsv', i)

    def check_relations(self):
        """Make sure relations only reference valid objects."""
        for i, rel in enumerate(self.api.relations.raw):
            for attr, set_ in [
                ('SOURCE', self.concepticon_ids),
                ('TARGET', self.concepticon_ids),
                ('SOURCE_GLOSS', self.concepticon_glosses),
                ('TARGET_GLOSS', self.concepticon_glosses),
            ]:
                if rel[attr] not in set_:  # pragma: no cover
                    self.error(f'invalid {attr}: {rel[attr]}', 'conceptrelations', i + 2)

    def check_language_mappings(self):
        """Make sure only valid gloss languages are specified."""
        iso_langs = [
            lang.iso2 for lang in self.api.vocabularies['COLUMN_TYPES'].values()
            if isinstance(lang, Languoid) and lang.iso2]
        if len(iso_langs) != len(set(iso_langs)):
            self.error(
                f'Duplicate ISO codes: {collections.Counter(iso_langs).most_common(1)}',
                'concepticon.json')
        assert set(p.stem.split('-')[1] for p in self.api.path('mappings').glob('map-*.tsv')) \
            .issubset(iso_langs)

    def check_refs(self, cl: Conceptlist, i: int, refs_in_bib: set[str], all_refs: set[str]):
        """
        Check items referenced in a conceptlists note or refs field.
        """
        err = functools.partial(self.error, name='conceptlists.tsv', line=i + 2)

        for ref in re.findall(BIB_PATTERN, cl.note) + cl.refs:
            if ref not in refs_in_bib:
                err(f'cited bibtex record not in bib: {ref}')
            else:
                all_refs.add(ref)

        for m in self.ref_without_label_pattern.finditer(cl.note):
            err(f'link without label: {m.string[m.start():m.end()]}')

        for m in self.ref_without_link_pattern.finditer(cl.note):  # pragma: no cover
            err(f'reference not in link: {m.string[m.start():m.end()]}')

        for m in REF_PATTERN.finditer(cl.note):
            if m.group('id') not in self.api.conceptlists:  # pragma: no cover
                err(f'invalid conceptlist ref: {m.group("id")}')

        # make also sure that all sources are accompanied by a PDF, but only write a
        # warning if this is not the case
        for ref in cl.pdf:
            if ref not in self.api.sources:  # pragma: no cover
                self.warning(f'no PDF found for {ref}', 'conceptlists.tsv')

    def _check_cols_in_md(self, cl, err):
        cols_in_md = {}
        for col in cl.metadata.tableSchema.columns:
            cnames = []  # all names or aliases csvw will recognize for this column
            if col.name in cols_in_md:  # pragma: no cover
                err(f'Duplicate name ot title in table schema: {col.name}')
            cnames.append(col.name)
            if col.titles:
                c = col.titles.getfirst()
                if c in cols_in_md:  # pragma: no cover
                    err(f'Duplicate name or title in table schema: {c}')
                cnames.append(c)
            cols_in_md[col.name] = cnames
        return cols_in_md

    def _check_concept(  # pylint: disable=R0912
            self,
            concept: Concept,
            i: int,
            cl: Conceptlist,
            err):
        if not concept.id.startswith(cl.id):  # pragma: no cover
            err(f'concept ID does not match concept list ID pattern {concept.id}')

        if concept.concepticon_id:
            cs = self.api.conceptsets.get(concept.concepticon_id)
            if not cs:  # pragma: no cover
                err(f'invalid conceptset ID {concept.concepticon_id}')
            elif cs.gloss != concept.concepticon_gloss:  # pragma: no cover
                err(f'wrong conceptset GLOSS for ID '
                    f'{cs.id}: {concept.concepticon_gloss} -> {cs.gloss}')

        if i == 0:  # pragma: no cover
            for lg in cl.source_language:
                if lg.lower() not in concept.cols:
                    err(f'missing source language col {lg.upper()}')

        for lg in cl.source_language:  # pragma: no cover
            if not any((
                    concept.attributes.get(lg.lower()),
                    getattr(concept, lg.lower(), None),
                    lg.lower() == 'english' and not concept.gloss)):
                err(f'missing source language translation {lg}', line=i + 2)

        for attr, values in [
            ('concepticon_id', self.concepticon_ids),
            ('concepticon_gloss', self.concepticon_glosses),
        ]:
            val = getattr(concept, attr)
            if val:
                # check that there are no leading and trailing spaces (while computationally
                # expensive, this helps catch really hard to find typos)
                if val != val.strip():  # pragma: no cover
                    err(f"leading or trailing spaces in value for {attr}: '{val}'", line=i + 2)

                if val not in values:  # pragma: no cover
                    err(f'invalid value for {attr}: {val}', line=i + 2)

    def check_schema(self, cl: Conceptlist, broken_cls):
        """Check consistency between the csvw metadata and the column names in the list."""
        err = functools.partial(self.error, name=cl.id)

        cols_in_md = self._check_cols_in_md(cl, err)
        for cname, cnames in cols_in_md.items():
            if not any(name in cl.cols_in_list for name in cnames):
                # Neither name nor title of the column is in the actual list header.
                err(f'Column in metadata but missing in list: {cname}')

        for col in cl.cols_in_list:
            if not any(col in cnames for cnames in cols_in_md.values()):
                err(f'Column in list but missing in metadata: {col}')

        try:
            # Now check individual concepts:
            for i, concept in enumerate(cl.concepts.values()):
                self._check_concept(concept, i, cl, err)
        except TypeError as e:  # pragma: no cover
            broken_cls.append(cl.id)
            self.error(str(e), cl.id)
            raise

    def check_conceptsets(self, broken_cls):
        """
        Determine deprecated conceptsets and make sure they are not referenced anymore.
        """
        # We partition conceptsets via the "sameas" relation ...
        sameas: dict[str, set[str]] = {}
        # ... and also check for duplicate glosses.
        glosses: set[str] = set()
        for cs in self.api.conceptsets.values():
            if cs.gloss in glosses:  # pragma: no cover
                self.error(f'duplicate conceptset gloss: {cs.gloss}', cs.id)
            glosses.add(cs.gloss)
            for target, rel in cs.relations.items():
                if rel == 'sameas':
                    for group in sameas.values():
                        if target in group:  # pragma: no cover
                            group.add(cs.id)
                            break
                    else:
                        sameas[cs.gloss] = {cs.id, target}

        # Conceptsets marked as "sameas" some other conceptset are considered deprecated
        # (except for the "earliest" conceptset among the same).
        deprecated: dict[str, str] = {}
        for s in sameas.values():
            csids = sorted(s, key=int)
            for csid in csids[1:]:
                assert csid not in deprecated
                deprecated[csid] = csids[0]

        # Make sure no deprecated conceptsets are referenced in conceptlists.
        for cl in (cl_ for cl_ in self.api.conceptlists.values() if cl_.id not in broken_cls):
            for concept in cl.concepts.values():
                if concept.concepticon_id in deprecated:  # pragma: no cover
                    self.error(f'deprecated concept set {concept.concepticon_id} linked '
                               f'for {concept.id}', cl.id)
