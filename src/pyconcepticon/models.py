import re
import json
import pathlib
import operator
import warnings
import functools
import collections
import dataclasses
from typing import Optional, Any

from clldutils.jsonlib import load
from csvw.dsv import reader
from csvw.metadata import TableGroup, Link

from pyconcepticon.util import split, split_ids, read_dicts, to_dict

__all__ = [
    'Languoid', 'Concept', 'Conceptlist', 'ConceptRelations', 'Conceptset', 'Metadata',
    'REF_PATTERN', 'MD_SUFFIX']

CONCEPTLIST_ID_PATTERN = re.compile(
    '(?P<author>[A-Za-z]+)-(?P<year>[0-9]+)-(?P<items>[0-9]+)(?P<letter>[a-z]?)$')
REF_PATTERN = re.compile(':ref:(?P<id>[a-zA-Z0-9-]+)')
MD_SUFFIX = '-metadata.json'
warnings.filterwarnings('ignore', category=UserWarning, module='csvw.metadata')
# Conceptlist columns which are assumed to contain concept network information:
# Keys are column names, values are booleans indicating whether the edges are directed or not.
CONCEPT_NETWORK_COLUMNS = {c + '_CONCEPTS': c != 'LINKED' for c in ["TARGET", "SOURCE", "LINKED"]}


def value_ascsv(v):
    if v is None:
        return ''
    elif isinstance(v, float):
        return "{0:.5f}".format(v)
    elif isinstance(v, dict):
        return json.dumps(v)
    elif isinstance(v, list):
        return ';'.join(v)
    return "{0}".format(v)


@dataclasses.dataclass
class DataObject:

    @classmethod
    def fieldnames(cls):
        return [f.name for f in dataclasses.fields(cls)]

    def ascsv(self):
        res = []
        for f, v in zip(dataclasses.fields(self.__class__), dataclasses.astuple(self)):
            res.append((f.metadata.get('ascsv') or value_ascsv)(v))
        return res


@dataclasses.dataclass
class Languoid:
    name: str
    glottocode: str
    iso2: str

    def __post_init__(self):
        self.name = self.name.lower()


class Bag(DataObject):
    @classmethod
    def public_fields(cls):
        return [n for n in cls.fieldnames() if not n.startswith('_')]


def valid_int(attr_name, value):
    try:
        int(value)
    except ValueError:  # pragma: no cover
        raise ValueError('invalid integer {0}: {1}'.format(attr_name, value))


def valid_conceptlist_id(instance, attribute, value):
    if not instance.local:
        if not CONCEPTLIST_ID_PATTERN.match(value):
            raise ValueError('invalid {0}.{1}: {2}'.format(
                instance.__class__.__name__,
                attribute,
                value))


def valid_conceptlist_author(instance, attribute, value):
    if value.count(',') > 1 and (not any(s in value for s in [' and ', ' AND '])):
        raise ValueError('invalid format for multiple authors: {}'.format(value))
    if any(len(s) > 200 for s in re.split(r'\s+(?:and|AND)\s+', value)):
        raise ValueError('suspiciously long author name in {}'.format(value))


def valid_key(instance, attribute, value):
    vocabulary = None
    if hasattr(instance._api, 'vocabularies'):
        vocabulary = instance._api.vocabularies[attribute.upper()]
    if value and vocabulary:
        if not isinstance(value, (list, tuple)):
            value = [value]
        if not all(v in vocabulary for v in value):
            raise ValueError('invalid {0}.{1}: {2}'.format(
                instance.__class__.__name__,
                attribute,
                value))


@dataclasses.dataclass
class Conceptset(Bag):
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
    def superseded(self):
        return bool(self.replacement_id)

    @property
    def replacement(self):
        if self._api and self.replacement_id:
            return self._api.conceptsets[self.replacement_id]

    @functools.cached_property
    def relations(self):
        return self._api.relations.get(self.id, {}) if self._api else {}

    @functools.cached_property
    def concepts(self):
        res = []
        if self._api:
            for clist in self._api.conceptlists.values():
                for concept in clist.concepts.values():
                    if concept.concepticon_id == self.id:
                        res.append(concept)
        return res


@dataclasses.dataclass
class Metadata(Bag):
    id: str
    meta: dict = dataclasses.field(default_factory=dict)
    values: dict = dataclasses.field(default_factory=dict)


def valid_concept(instance, attribute, value):
    if not value:
        raise ValueError('missing concept id %s' % instance)
    if not re.match('[0-9]+.*', instance.number):
        raise ValueError('invalid concept number: %s' % instance)
    if not instance.label:
        raise ValueError('fields gloss *and* english missing: %s' % instance)


_INVERSE_RELATIONS = {'broader': 'narrower'}
_INVERSE_RELATIONS.update({v: k for k, v in _INVERSE_RELATIONS.items()})


class ConceptRelations(dict):
    """
    Class handles relations between concepts.
    """
    def __init__(self, path, multiple=False):
        rels = collections.defaultdict(lambda: collections.defaultdict(set))
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
        dict.__init__(self, rels.items())

    def iter_related(self, concept, relation, max_degree_of_separation=2):
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
class Concept(Bag):
    id: str
    number: str
    concepticon_id: Optional[str] = None
    concepticon_gloss: Optional[str] = None
    gloss: Optional[str] = None
    english: Optional[str] = None
    attributes: dict = dataclasses.field(default_factory=dict)
    _list: Any = None

    def __post_init__(self):
        valid_concept(self, 'id', self.id)
        self.concepticon_id = self.concepticon_id \
            if self.concepticon_id is None else f'{self.concepticon_id}'

    @property
    def label(self):
        return self.gloss or self.english

    @functools.cached_property
    def cols(self):
        return Concept.public_fields() + list(self.attributes.keys())


@dataclasses.dataclass
class Conceptlist(Bag):
    _api: Any
    id: str
    author: str
    year: int
    list_suffix: str
    items: int
    tags: list[str]
    source_language: list[str]
    target_language: str
    url: str
    refs: list[str]
    pdf: list[str]
    note: str
    pages: str
    alias: list[str]
    local: bool = False

    def __post_init__(self):
        valid_conceptlist_id(self, 'id', self.id)
        valid_conceptlist_author(self, 'author', self.author)
        self.year = int(self.year)
        self.items = int(self.items)
        self.tags = split_ids(self.tags)
        valid_key(self, 'tags', self.tags)
        self.source_language = split(self.source_language.lower())
        self.refs = split_ids(self.refs)
        self.pdf = split_ids(self.pdf)
        self.alias = [] if self.alias is None else split(self.alias)

    @functools.cached_property
    def tg(self):
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
            tg._fname = self._api.parent.joinpath(self._api.name + MD_SUFFIX)
        tg.tables[0].url = Link('{0}.tsv'.format(self.id))
        return tg

    @functools.cached_property
    def metadata(self):
        return self.tg.tables[0]

    @property
    def path(self):
        if isinstance(self._api, pathlib.Path):
            return self._api
        return self._api.data_path('conceptlists', self.id + '.tsv')

    @functools.cached_property
    def cols_in_list(self):
        return list(next(reader(self.path, dicts=True, delimiter='\t')).keys())

    @functools.cached_property
    def attributes(self):
        return [c.name for c in self.metadata.tableSchema.columns
                if c.name.lower() not in Concept.public_fields()]

    @functools.cached_property
    def concepts(self):
        res = []
        if self.path.exists():
            for item in self.metadata:
                kw, attributes = {}, {}
                for k, v in item.items():
                    if k:
                        kl = k.lower()
                        operator.setitem(kw if kl in Concept.public_fields() else attributes, kl, v)
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

    def stats(self):
        """Return simple statistics for a given concept list"""
        # @todo: refine for custom-concept lists
        concepts = self.concepts.values()
        mapped = [c for c in concepts if c.concepticon_id]
        mapped_ratio = 0
        if concepts:
            mapped_ratio = int((len(mapped) / len(concepts)) * 100)
        concepticon_ids = collections.Counter(
            [c.concepticon_id for c in concepts if c.concepticon_id])
        mergers = [(k, v) for k, v in concepticon_ids.items() if v > 1]
        return mapped, mapped_ratio, mergers
