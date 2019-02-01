import re
from collections import deque, defaultdict
from pathlib import Path
from operator import setitem

import attr
from clldutils.apilib import DataObject
from clldutils.misc import lazyproperty
from csvw.metadata import TableGroup, Link

from pyconcepticon.util import split, split_ids, read_dicts, to_dict

__all__ = [
    'Languoid', 'Concept', 'Conceptlist', 'ConceptRelations', 'Conceptset', 'Metadata',
    'REF_PATTERN']

CONCEPTLIST_ID_PATTERN = re.compile(
    '(?P<author>[A-Za-z]+)-(?P<year>[0-9]+)-(?P<items>[0-9]+)(?P<letter>[a-z]?)$')
REF_PATTERN = re.compile(':ref:(?P<id>[a-zA-Z0-9-]+)')


@attr.s
class Languoid(object):
    name = attr.ib(converter=lambda s: s.lower())
    glottocode = attr.ib()
    iso2 = attr.ib()


class Bag(DataObject):
    @classmethod
    def public_fields(cls):
        return [n for n in cls.fieldnames() if not n.startswith('_')]


def valid_conceptlist_id(instance, attribute, value):
    if not instance.local:
        if not CONCEPTLIST_ID_PATTERN.match(value):
            raise ValueError('invalid {0}.{1}: {2}'.format(
                instance.__class__.__name__,
                attribute.name,
                value))


def valid_key(instance, attribute, value):
    vocabulary = None
    if hasattr(instance._api, 'vocabularies'):
        vocabulary = instance._api.vocabularies[attribute.name.upper()]
    if value and vocabulary:
        if not isinstance(value, (list, tuple)):
            value = [value]
        if not all(v in vocabulary for v in value):
            raise ValueError('invalid {0}.{1}: {2}'.format(
                instance.__class__.__name__,
                attribute.name,
                value))


@attr.s
class Conceptset(Bag):
    id = attr.ib()
    gloss = attr.ib()
    semanticfield = attr.ib(validator=valid_key)
    definition = attr.ib()
    ontological_category = attr.ib(validator=valid_key)
    replacement_id = attr.ib()
    _api = attr.ib(default=None)

    @property
    def superseded(self):
        return bool(self.replacement_id)

    @property
    def replacement(self):
        if self._api and self.replacement_id:
            return self._api.conceptsets[self.replacement_id]

    @lazyproperty
    def relations(self):
        return self._api.relations.get(self.id, {}) if self._api else {}

    @lazyproperty
    def concepts(self):
        res = []
        if self._api:
            for clist in self._api.conceptlists.values():
                for concept in clist.concepts.values():
                    if concept.concepticon_id == self.id:
                        res.append(concept)
        return res


@attr.s
class Metadata(Bag):
    id = attr.ib()
    meta = attr.ib(default=attr.Factory(dict))
    values = attr.ib(default=attr.Factory(dict))


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
    def __init__(self, path):
        rels = defaultdict(dict)
        self.raw = list(read_dicts(path))
        for item in self.raw:
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

        :param search_depth: maximal depth of search
        :param relation: the concept relation to be searched (currently only
            "broader" and "narrower".

        """
        queue = deque([(concept, 0)])
        while queue:
            current_concept, depth = queue.popleft()
            depth += 1
            for target, rel in self.get(current_concept, {}).items():
                if rel == relation and depth <= max_degree_of_separation:
                    queue.append((target, depth))
                    yield (target, depth)


@attr.s
class Concept(Bag):
    id = attr.ib(validator=valid_concept)
    number = attr.ib()
    concepticon_id = attr.ib(
        default=None, converter=lambda s: s if s is None else '{0}'.format(s))
    concepticon_gloss = attr.ib(default=None)
    gloss = attr.ib(default=None)
    english = attr.ib(default=None)
    attributes = attr.ib(default=attr.Factory(dict))
    _list = attr.ib(default=None)

    @property
    def label(self):
        return self.gloss or self.english

    @lazyproperty
    def cols(self):
        return Concept.public_fields() + list(self.attributes.keys())


@attr.s
class Conceptlist(Bag):
    _api = attr.ib()
    id = attr.ib(validator=valid_conceptlist_id)
    author = attr.ib()
    year = attr.ib(converter=int)
    list_suffix = attr.ib()
    items = attr.ib(converter=int)
    tags = attr.ib(converter=split_ids, validator=valid_key)
    source_language = attr.ib(converter=lambda v: split(v.lower()))
    target_language = attr.ib()
    url = attr.ib()
    refs = attr.ib(converter=split_ids)
    pdf = attr.ib(converter=split_ids)
    note = attr.ib()
    pages = attr.ib()
    alias = attr.ib(converter=lambda s: [] if s is None else split(s))
    local = attr.ib(default=False)

    @property
    def metadata(self):
        md = self.path.parent.joinpath(self.path.name + '-metadata.json')
        if not md.exists():
            if hasattr(self._api, 'repos'):
                ddir = self._api.path('concepticondata')
                if self.local:
                    md = ddir.joinpath('conceptlists', 'local-metadata.json')
                if not md.exists():
                    md = ddir.joinpath('conceptlists', 'default-metadata.json')
            else:
                md = Path(__file__).parent / 'conceptlist-metadata.json'
        tg = TableGroup.from_file(md)
        if isinstance(self._api, Path):
            tg._fname = self._api.parent.joinpath(self._api.name + '-metadata.json')
        tg.tables[0].url = Link('{0}.tsv'.format(self.id))
        return tg.tables[0]

    @property
    def path(self):
        if isinstance(self._api, Path):
            return self._api
        return self._api.data_path('conceptlists', self.id + '.tsv')

    @lazyproperty
    def attributes(self):
        return [c.name for c in self.metadata.tableSchema.columns
                if c.name.lower() not in Concept.public_fields()]

    @lazyproperty
    def concepts(self):
        res = []
        if self.path.exists():
            for item in self.metadata:
                kw, attributes = {}, {}
                for k, v in item.items():
                    if k:
                        kl = k.lower()
                        setitem(kw if kl in Concept.public_fields() else attributes, kl, v)
                res.append(Concept(list=self, attributes=attributes, **kw))
        return to_dict(res)

    @classmethod
    def from_file(cls, path, **keywords):
        """
        Function loads a concept list outside the Concepticon collection.

        @todo: uniqueness-check hier einbauen, siehe Funktion read_dicts
        """
        path = Path(path)
        assert path.exists()
        attrs = {f: keywords.get(f, '') for f in Conceptlist.public_fields()}
        attrs.update(
            id=path.stem,
            items=keywords.get('items', len(read_dicts(path))),
            year=keywords.get('year', 0),
            local=True)
        return cls(api=path, **attrs)
