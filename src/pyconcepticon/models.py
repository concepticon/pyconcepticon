"""
OO wrappers for the data in the Concepticon TSV files.
"""
import re
import pathlib
import operator
import warnings
import functools
import collections
from collections.abc import Generator, Sequence
import dataclasses
from typing import Optional, Any, Union

import csvw
from clldutils.jsonlib import load
from csvw.dsv import reader
from csvw.metadata import TableGroup, Link

from pyconcepticon.util import split, split_ids, read_dicts, to_dict

__all__ = [
    'Languoid', 'Concept', 'Conceptlist', 'ConceptRelations', 'Conceptset',
    'REF_PATTERN', 'MD_SUFFIX']

RelationsType = dict[str, dict[str, Union[str, set[str]]]]

CONCEPTLIST_ID_PATTERN = re.compile(
    '(?P<author>[A-Za-z]+)-(?P<year>[0-9]+)-(?P<items>[0-9]+)(?P<letter>[a-z]?)$')
REF_PATTERN = re.compile(':ref:(?P<id>[a-zA-Z0-9-]+)')
MD_SUFFIX = '-metadata.json'
warnings.filterwarnings('ignore', category=UserWarning, module='csvw.metadata')
# Conceptlist columns which are assumed to contain concept network information:
# Keys are column names, values are booleans indicating whether the edges are directed or not.
CONCEPT_NETWORK_COLUMNS = {c + '_CONCEPTS': c != 'LINKED' for c in ["TARGET", "SOURCE", "LINKED"]}


@dataclasses.dataclass
class Languoid:
    """A bag of attributes identifying a languoid."""
    name: str
    glottocode: str
    iso2: str

    def __post_init__(self):
        self.name = self.name.lower()


@dataclasses.dataclass
class Bag:
    """Mixin class to make access to dataclass fields simpler."""
    @classmethod
    def fieldnames(cls):  # pylint: disable=C0116
        return [f.name for f in dataclasses.fields(cls)]

    @classmethod
    def public_fields(cls) -> list[str]:  # pylint: disable=C0116
        return [n for n in cls.fieldnames() if not n.startswith('_')]


def valid_key(instance: object, attribute: str, value: Union[str, list[str], tuple[str]]):
    """Raises ValueError on invalid value."""
    vocabulary = None
    if hasattr(instance._api, 'vocabularies'):  # pylint: disable=W0212
        vocabulary = instance._api.vocabularies[attribute.upper()]  # pylint: disable=W0212
    if value and vocabulary:
        if not isinstance(value, (list, tuple)):
            value = [value]
        if not all(v in vocabulary for v in value):
            raise ValueError(f'invalid {instance.__class__.__name__}.{attribute}: {value}')


@dataclasses.dataclass
class Conceptset(Bag):
    """A Concepticon Concept Set, i.e. a row in concepticon.tsv."""
    id: str
    gloss: str
    semanticfield: str
    definition: str
    ontological_category: str
    replacement_id: str
    _api: Any = None

    def __post_init__(self):
        valid_key(self, 'semanticfield', self.semanticfield)
        valid_key(self, 'ontological_category', self.ontological_category)

    @property
    def superseded(self) -> bool:
        """If a conceptset has a replacement, it's superseded."""
        return bool(self.replacement_id)

    @property
    def replacement(self) -> Optional['Conceptset']:
        """The conceptset that replaces self - or None."""
        if self._api and self.replacement_id:
            return self._api.conceptsets[self.replacement_id]
        return None  # pragma: no cover

    @functools.cached_property
    def relations(self) -> dict[str, str]:
        """
        >>> c = Concepticon('src/pyconcepticon/test_repos')
        >>> c.conceptsets['2461'].relations
        {'2460': 'narrower', '2448': 'narrower', '522': 'narrower', '2009': 'narrower'}
        """
        return self._api.relations.get(self.id, {}) if self._api else {}

    @functools.cached_property
    def concepts(self) -> list['Concept']:
        """
        >>> c = Concepticon('src/pyconcepticon/test_repos')
        >>> c.conceptsets['1360'].concepts[0].id
        'Sun-1991-1004-138'
        """
        res = []
        if self._api:
            for clist in self._api.conceptlists.values():
                for concept in clist.concepts.values():
                    if concept.concepticon_id == self.id:
                        res.append(concept)
        return res


_INVERSE_RELATIONS = {'broader': 'narrower'}
_INVERSE_RELATIONS.update({v: k for k, v in _INVERSE_RELATIONS.items()})


class ConceptRelations(dict):
    """
    Class handles relations between concepts.
    """
    def __init__(self, path, multiple=False):
        rels: RelationsType = collections.defaultdict(lambda: collections.defaultdict(set))
        self.raw = list(read_dicts(path))
        for item in self.raw:
            if multiple:
                rels[item['SOURCE']][item['TARGET']].add(item['RELATION'])
                rels[item['SOURCE_GLOSS']][item['TARGET_GLOSS']].add(item['RELATION'])
                if item['RELATION'] in _INVERSE_RELATIONS:
                    rels[item['TARGET']][item['SOURCE']].add(
                        _INVERSE_RELATIONS[item['RELATION']])
                    rels[item['TARGET_GLOSS']][item['SOURCE_GLOSS']].add(
                        _INVERSE_RELATIONS[item['RELATION']])
            else:
                rels[item['SOURCE']][item['TARGET']] = item['RELATION']
                rels[item['SOURCE_GLOSS']][item['TARGET_GLOSS']] = item['RELATION']
                if item['RELATION'] in _INVERSE_RELATIONS:
                    rels[item['TARGET']][item['SOURCE']] = \
                        _INVERSE_RELATIONS[item['RELATION']]
                    rels[item['TARGET_GLOSS']][item['SOURCE_GLOSS']] = \
                        _INVERSE_RELATIONS[item['RELATION']]
        dict.__init__(
            self,
            ((k, {x: y for x, y in v.items()}) for k, v in rels.items())  # pylint: disable=R1721
        )

    def iter_related(
            self,
            concept: str,
            relation: str,
            max_degree_of_separation: int = 2,
    ) -> Generator[tuple[str, int], None, None]:
        """
        Search for concept relations of a given concept.

        :param concept: CONCEPTICON_ID for which to perform the search
        :param max_degree_of_separation: maximal depth of search
        :param relation: the concept relation to be searched (currently only "broader" and \
        "narrower")
        """
        queue = collections.deque([(concept, 0)])
        while queue:
            current_concept, depth = queue.popleft()
            depth += 1
            for target, rels in self.get(current_concept, {}).items():
                if (relation in rels or relation == rels) and depth <= max_degree_of_separation:
                    queue.append((target, depth))
                    yield target, depth


@dataclasses.dataclass
class Concept(Bag):  # pylint: disable=R0902
    """Concepts are the items in conceptlists."""
    id: str
    number: str
    concepticon_id: Optional[str] = None
    concepticon_gloss: Optional[str] = None
    gloss: Optional[str] = None
    english: Optional[str] = None
    attributes: dict = dataclasses.field(default_factory=dict)
    _list: Any = None

    def __post_init__(self):
        if not self.id:
            raise ValueError(f'missing concept id {self}')
        if not re.match('[0-9]+.*', self.number):
            raise ValueError(f'invalid concept number: {self}')
        if not self.label:
            raise ValueError(f'fields gloss *and* english missing: {self}')

        self.concepticon_id = self.concepticon_id \
            if self.concepticon_id is None else f'{self.concepticon_id}'

    @property
    def label(self) -> str:
        """A description of the concept."""
        return self.gloss or self.english

    @functools.cached_property
    def cols(self) -> list[str]:
        """Column names of the concept list to which the concept belongs."""
        return Concept.public_fields() + list(self.attributes.keys())


@dataclasses.dataclass(frozen=True)
class ConceptStats:
    """Summary statistics on concepts."""
    mapped: list[Concept]
    mapped_ratio_percent: int
    mergers: list[tuple[str, int]]

    @classmethod
    def from_concepts(cls, concepts: Sequence[Concept]) -> 'ConceptStats':
        """Compute stats on a bunch of concepts."""
        mapped = [c for c in concepts if c.concepticon_id]
        mapped_ratio = 0
        if concepts:
            mapped_ratio = int((len(mapped) / len(concepts)) * 100)
        concepticon_ids = collections.Counter(c.concepticon_id for c in concepts)
        mergers = [(k, v) for k, v in concepticon_ids.items() if k and v > 1]
        return cls(mapped, mapped_ratio, mergers)


@dataclasses.dataclass
class Conceptlist(Bag):  # pylint: disable=R0902
    """Concept lists are the core entities of the Concepticon."""
    _api: Any
    id: str
    author: str
    year: int
    list_suffix: str
    items: int
    tags: Union[str, list[str]]
    source_language: Union[str, list[str]]
    target_language: str
    url: str
    refs: Union[str, list[str]]
    pdf: Union[str, list[str]]
    note: str
    pages: str
    alias: Union[str, list[str]]
    local: bool = False

    def __post_init__(self):
        if not self.local:
            if not CONCEPTLIST_ID_PATTERN.match(self.id):
                raise ValueError(f'Conceptlist.id: {self.id}')

        if self.author.count(',') > 1 and (not any(s in self.author for s in [' and ', ' AND '])):
            raise ValueError(f'invalid format for multiple authors: {self.author}')
        if any(len(s) > 200 for s in re.split(r'\s+(?:and|AND)\s+', self.author)):
            raise ValueError(f'suspiciously long author name in {self.author}')

        self.year = int(self.year)
        self.items = int(self.items)
        self.tags = split_ids(self.tags)
        valid_key(self, 'tags', self.tags)
        if isinstance(self.source_language, str):
            self.source_language = split(self.source_language.lower())
        self.refs = split_ids(self.refs)
        self.pdf = split_ids(self.pdf)
        self.alias = [] if self.alias is None else split(self.alias)

    @functools.cached_property
    def tg(self) -> csvw.TableGroup:
        """A CSVW TableGroup instance describing the TSV file of the list."""
        md = self.path.parent.joinpath(self.path.name + MD_SUFFIX)
        if not md.exists():
            if hasattr(self._api, 'repos'):
                ddir = self._api.path('concepticondata')
                if self.local:
                    md = ddir.joinpath('conceptlists', 'local' + MD_SUFFIX)
                if not md.exists():
                    md = ddir.joinpath('conceptlists', 'default' + MD_SUFFIX)
            else:
                md = pathlib.Path(__file__).parent / 'conceptlist-metadata.json'
        metadata = load(md)
        metadata['tables'][0]['url'] = 'u'
        tg = TableGroup.from_file(md, data=metadata)

        if isinstance(self._api, pathlib.Path):
            tg._fname = self._api.parent.joinpath(  # pylint: disable=W0212
                self._api.name + MD_SUFFIX)
        tg.tables[0].url = Link(f'{self.id}.tsv')
        return tg

    @functools.cached_property
    def metadata(self) -> csvw.Table:
        """CSVW metadata for the TSV file of the conceptlist."""
        return self.tg.tables[0]

    @property
    def path(self) -> pathlib.Path:
        """Path of the TSV file of the conceptlist."""
        if isinstance(self._api, pathlib.Path):
            return self._api
        return self._api.data_path('conceptlists', self.id + '.tsv')

    @functools.cached_property
    def cols_in_list(self) -> list[str]:
        """Actual column names in the TSV file of the conceptlist."""
        return list(next(reader(self.path, dicts=True, delimiter='\t')).keys())

    @functools.cached_property
    def attributes(self) -> list[str]:
        """Attributes are additional, non-standard columns in a conceptlist."""
        return [c.name for c in self.metadata.tableSchema.columns
                if c.name.lower() not in Concept.public_fields()]

    @functools.cached_property
    def concepts(self) -> dict[str, Concept]:
        """List of concepts which are mapped to this conceptset."""
        res = []
        if self.path.exists():
            for item in self.metadata:
                # Partition the data read from the TSV table for instantiation of a Concept.
                kw, attributes = {}, {}
                for k, v in item.items():
                    if k:
                        kl = k.lower()
                        d = kw if kl in Concept.public_fields() else attributes
                        operator.setitem(d, kl, v)
                res.append(Concept(_list=self, attributes=attributes, **kw))
        return to_dict(res)

    @classmethod
    def from_file(cls, path, **keywords):
        """
        Function loads a concept list outside the Concepticon collection.

        @todo: uniqueness-check hier einbauen, siehe Funktion read_dicts
        """
        path = pathlib.Path(path)
        assert path.exists()
        attrs = {f: keywords.get(f, '') for f in Conceptlist.public_fields()}
        attrs.update(
            id=path.stem,
            items=keywords.get('items', len(read_dicts(path))),
            year=keywords.get('year', 0),
            local=True)
        return cls(_api=path, **attrs)

    def stats(self) -> ConceptStats:
        """Return simple statistics for a given concept list"""
        # @todo: refine for custom-concept lists
        return ConceptStats.from_concepts(self.concepts.values())
