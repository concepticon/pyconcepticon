import dataclasses
import re
import typing
import pathlib
import warnings
import functools
import collections

import cldfcatalog
import simplepybtex.database
from clldutils import jsonlib
from clldutils.apilib import API
from clldutils.markup import iter_markdown_tables
from clldutils.source import Source

from pyconcepticon.glosses import concept_map, concept_map2
# The following symbols from models can explicitly be imported from pyconcepticon.api:
from pyconcepticon.models import (  # noqa: F401
    Languoid, Concept, Conceptlist, ConceptRelations, Conceptset, REF_PATTERN, MD_SUFFIX,
)
from pyconcepticon.util import read_dicts, lowercase, to_dict, UnicodeWriter, BIB_PATTERN

assert MD_SUFFIX and Concept
Editor = collections.namedtuple('Editor', ['name', 'start', 'end'])


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

    def __init__(self, repos: typing.Optional[typing.Union[str, pathlib.Path]] = None):
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
    def editors(self) -> typing.List[Editor]:
        res = []
        header, rows = next(
            iter_markdown_tables(self.path('CONTRIBUTORS.md').read_text(encoding='utf8')))
        for (period, name) in rows:
            start, to_, end = period.strip().partition('-')
            start, end = start.strip(), end.strip()
            res.append(Editor(name.strip(), start, start if not to_ else end or None))
        return res

    @functools.cached_property
    def vocabularies(self) -> typing.Dict[str, dict]:
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
    def bibfile(self) -> pathlib.Path:
        return self.data_path('references', 'references.bib')

    @functools.cached_property
    def sources(self) -> dict:
        return jsonlib.load(self.data_path('sources', 'cdstar.json'))

    @functools.cached_property
    def retirements(self):
        return jsonlib.load(
            self.data_path('retired.json'), object_pairs_hook=collections.OrderedDict)

    def add_retirement(self, type_, repl):
        obj = collections.OrderedDict()
        for k in ['id', 'comment', 'replacement']:
            obj[k] = repl[k]
            assert obj[k]
        if type_ not in self.retirements:
            self.retirements[type_] = []
        self.retirements[type_].append(obj)
        jsonlib.dump(self.retirements, self.data_path('retired.json'), indent=2)

    @functools.cached_property
    def bibliography(self) -> typing.Dict[str, Source]:
        """
        :returns: `dict` mapping BibTeX IDs to `Reference` instances.
        """
        return to_dict(
            Source.from_entry(key, entry) for key, entry in simplepybtex.database.parse_string(
                self.bibfile.read_text(encoding='utf8'), bib_format='bibtex').entries.items())

    @functools.cached_property
    def conceptsets(self) -> typing.Dict[str, Conceptset]:
        """
        :returns: `dict` mapping ConceptSet IDs to `Conceptset` instances.
        """
        return to_dict(
            Conceptset(_api=self, **lowercase(d))
            for d in read_dicts(self.data_path('concepticon.tsv')))

    @functools.cached_property
    def conceptlists_dicts(self):
        return read_dicts(self.data_path('conceptlists.tsv'))

    @functools.cached_property
    def conceptlists(self):
        """
        :returns: `dict` mapping ConceptList IDs to `Conceptlist` instances.

        .. note:: Individual concepts can be accessed via `Conceptlist.concepts`.
        """
        return to_dict(Conceptlist(_api=self, **lowercase(d)) for d in self.conceptlists_dicts)

    @functools.cached_property
    def relations(self):
        """
        :returns: `dict` mapping concept sets to related concepts.
        """
        return ConceptRelations(self.data_path('conceptrelations.tsv'))

    @functools.cached_property
    def multirelations(self):
        """
        :returns: `dict` mapping concept sets to related concepts.
        """
        return ConceptRelations(self.data_path('conceptrelations.tsv'), multiple=True)

    @functools.cached_property
    def frequencies(self):
        D = collections.defaultdict(int)
        for cl in self.conceptlists.values():
            for concept in cl.concepts.values():
                if concept.concepticon_id:
                    D[concept.concepticon_gloss] += 1
        return D

    def _get_map_for_language(self, language, otherlist=None):
        if (language, otherlist) not in self._to_mapping:
            if otherlist is not None:
                to = []
                for item in read_dicts(otherlist):
                    to.append((item['ID'], item.get('GLOSS', item.get('ENGLISH'))))
            else:
                mapfile = self.repos / 'mappings' / 'map-{0}.tsv'.format(language)
                to = [(cs['ID'], cs['GLOSS']) for cs in read_dicts(mapfile)]
            self._to_mapping[(language, otherlist)] = to
        return self._to_mapping[(language, otherlist)]

    def map(self,
            clist,
            otherlist=None,
            out=None,
            full_search=False,
            similarity_level=5,
            language='en',
            skip_multiple=False):
        assert clist.exists(), "File %s does not exist" % clist
        from_ = read_dicts(clist)

        to = self._get_map_for_language(language, otherlist)
        gloss = {
            'fr': 'FRENCH',
            'en': 'ENGLISH',
            'es': 'SPANISH',
            'de': 'GERMAN',
            'pl': 'POLISH',
            'lt': 'LATIN',
            'zh': 'CHINESE',
            'pt': 'PORTUGUESE',
            'ru': 'RUSSIAN',
            'it': 'ITALIAN',
        }.get(language, 'GLOSS')
        cmap = (concept_map if full_search else concept_map2)(
            [i.get('GLOSS', i.get(gloss)) for i in from_],
            [i[1] for i in to],
            similarity_level=similarity_level,
            language=language
        )
        good_matches = 0
        with UnicodeWriter(out) as writer:
            writer.writerow(
                list(from_[0].keys())
                + ['CONCEPTICON_ID', 'CONCEPTICON_GLOSS', 'SIMILARITY'])
            for i, item in enumerate(from_):
                row = list(item.values())
                mapping = cmap.get_mapping(i)
                if mapping.similarity <= similarity_level:
                    good_matches += 1
                if not mapping.to_keys:
                    writer.writerow(row + ['', '???', ''])
                elif len(mapping.to_keys) == 1:
                    row.extend([
                        to[mapping.to_keys[0]][0], to[mapping.to_keys[0]][1].split('///')[0], mapping.similarity])
                    writer.writerow(row)
                else:
                    assert not full_search
                    # we need a list to retain the order by frequency
                    visited = []
                    for j in mapping.to_keys:
                        gls, cid = to[j][0], to[j][1].split('///')[0]
                        if (gls, cid) not in visited:
                            visited += [(gls, cid)]
                    if len(visited) > 1:
                        if not skip_multiple:
                            writer.writeblock(
                                row + [gls, cid, mapping.similarity] for gls, cid in visited)
                    else:
                        row.extend([visited[0][0], visited[0][1], mapping.similarity])
                        writer.writerow(row)
            writer.writerow(
                ['#',
                 '{0}/{1}'.format(good_matches, len(from_)),
                 '{0:.0f}%'.format(100 * good_matches / len(from_))]
                + (len(from_[0]) - 1) * [''])

        if out is None:
            print(writer.read().decode('utf-8'))

    def lookup(
            self,
            entries,
            full_search=False,
            similarity_level=5,
            language='en',
            mincsid=None,
            to=None,
    ):
        """
        :returns: `generator` of tuples (searchterm, concepticon_id, concepticon_gloss, similarity).
        """
        if to is None:
            to = [
                t for t in self._get_map_for_language(language, None)
                if mincsid is None or (int(t[0]) >= mincsid)]
        tox = [i[1] for i in to]
        cfunc = concept_map2 if full_search else concept_map
        cmap = cfunc(
            entries,
            tox,
            similarity_level=similarity_level,
            language=language)
        for i, e in enumerate(entries):
            mapping = cmap.get_mapping(i)
            yield set((e, to[m][0], to[m][1].split("///")[0], mapping.similarity) for m in mapping.to_keys)

    def check(self, *clids) -> bool:
        """Returns the success of the checks."""
        assert self.retirements
        print(f'testing {len(clids) if clids else len(self.conceptlists)} concept lists')

        with Checker(self) as report:
            for i, d in enumerate(self.conceptlists_dicts, start=1):
                if (not clids) or d['ID'] in clids:
                    try:
                        Conceptlist(_api=self, **lowercase(d))
                    except ValueError as e:  # pragma: no cover
                        report.error(str(e), 'conceptlists.tsv', i)

            if report.errors:  # pragma: no cover
                return False  # Exit early in case of structural errors.

            # Make sure all language-specific mappings are well specified
            report.check_language_mappings()

            # We collect all cite keys used to refer to references.
            all_refs: set[str] = set()
            refs_in_bib: set[str] = set(ref for ref in self.bibliography)

            # Make sure only records in the BibTeX file references.bib are referenced by
            # concept lists.
            for i, cl in enumerate(self.conceptlists.values()):
                if not (clids and cl.id not in clids):
                    report.check_refs(cl, i, refs_in_bib, all_refs)

            all_refs.add('List2016a')

            if not clids:
                # Only report unused references if we check all concept lists!
                for ref in refs_in_bib - all_refs:  # pragma: no cover
                    report.error(f'unused bibtex record: {ref}', 'references.bib')

            ref_cols = {
                'concepticon_id': set(self.conceptsets.keys()),
                'concepticon_gloss': set(cs.gloss for cs in self.conceptsets.values()),
            }

            for i, rel in enumerate(self.relations.raw):
                for attr, type_ in [
                    ('SOURCE', 'concepticon_id'),
                    ('TARGET', 'concepticon_id'),
                    ('SOURCE_GLOSS', 'concepticon_gloss'),
                    ('TARGET_GLOSS', 'concepticon_gloss'),
                ]:
                    if rel[attr] not in ref_cols[type_]:  # pragma: no cover
                        report.error(
                            'invalid {0}: {1}'.format(attr, rel[attr]), 'conceptrelations', i + 2)

            for fname in self.data_path('conceptlists').glob('*.tsv'):
                if clids and fname.stem not in clids:
                    continue  # pragma: no cover
                if fname.stem not in self.conceptlists:  # pragma: no cover
                    report.error(
                        'conceptlist missing in conceptlists.tsv: {0}'.format(fname.name), '')

            broken_cls = []

            for cl in self.conceptlists.values():
                if clids and cl.id not in clids:
                    continue  # pragma: no cover

                # Check consistency between the csvw metadata and the column names in the list.
                report.check_schema(cl, ref_cols, broken_cls)

            report.check_conceptsets(broken_cls)

        return not bool(report.errors)


@dataclasses.dataclass
class Checker:
    api: Concepticon
    errors: list = dataclasses.field(default_factory=list)
    ref_without_label_pattern: re.Pattern = re.compile(r'[^]]\(:(ref|bib):[A-Za-z0-9\-]+\)')
    ref_without_link_pattern: re.Pattern = re.compile('[^(]:(ref|bib):[A-Za-z0-9-]+')

    @staticmethod
    def _msg(type_, msg, name, line):  # pragma: no cover
        if line:
            line = ':%s' % line
        return '%s:%s%s: %s' % (type_.upper(), name, line or '', msg)

    def error(self, msg, name=None, line=0):  # pragma: no cover
        self.errors.append((msg, name, line))

    @classmethod
    def warning(cls, msg, name, line=0):  # pragma: no cover
        warnings.warn(cls._msg('warning', msg, name, line), Warning)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for msg, name, line in self.errors:
            print(self._msg('error', msg, name, line))

    def check_language_mappings(self):
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

    def check_schema(self, cl: Conceptlist, ref_cols, broken_cls):
        #
        # Check consistency between the csvw metadata and the column names in the list.
        #
        err = functools.partial(self.error, name=cl.id)

        missing_in_md, missing_in_list = [], []
        cols_in_md = []
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
            cols_in_md.extend(cnames)
            if not any(name in cl.cols_in_list for name in cnames):
                # Neither name nor title of the column is in the actual list header.
                missing_in_list.append(col.name)
        for col in cl.cols_in_list:
            if col not in cols_in_md:
                missing_in_md.append(col)

        for col in missing_in_list:
            err(f'Column in metadata but missing in list: {col}')
        for col in missing_in_md:
            err(f'Column in list but missing in metadata: {col}')

        try:
            # Now check individual concepts:
            for i, concept in enumerate(cl.concepts.values()):
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
                    if not (concept.attributes.get(lg.lower())
                            or getattr(concept, lg.lower(), None)
                            or (lg.lower() == 'english' and not concept.gloss)):
                        err(f'missing source language translation {lg}', line=i + 2)
                for attr, values in ref_cols.items():
                    val = getattr(concept, attr)
                    if val:
                        # check that there are not leading and trailing spaces
                        # (while computationally expensive, this helps catch really
                        # hard to find typos)
                        if val != val.strip():  # pragma: no cover
                            err(f"leading or trailing spaces in value for {attr}: '{val}'",
                                line=i + 2)

                        if val not in values:  # pragma: no cover
                            err(f'invalid value for {attr}: {val}', line=i + 2)
        except TypeError as e:  # pragma: no cover
            broken_cls.append(cl.id)
            self.error(str(e), cl.id)
            raise

    def check_conceptsets(self, broken_cls):
        sameas = {}
        glosses = set()
        for cs in self.api.conceptsets.values():
            if cs.gloss in glosses:  # pragma: no cover
                self.error('duplicate conceptset gloss: {0}'.format(cs.gloss), cs.id)
            glosses.add(cs.gloss)
            for target, rel in cs.relations.items():
                if rel == 'sameas':
                    for group in sameas.values():
                        if target in group:  # pragma: no cover
                            group.add(cs.id)
                            break
                    else:
                        sameas[cs.gloss] = {cs.id, target}

        deprecated = {}
        for s in sameas.values():
            csids = sorted(s, key=lambda j: int(j))
            for csid in csids[1:]:
                assert csid not in deprecated
                deprecated[csid] = csids[0]

        for cl in self.api.conceptlists.values():
            if cl.id in broken_cls:
                continue  # pragma: no cover
            for concept in cl.concepts.values():
                if concept.concepticon_id in deprecated:  # pragma: no cover
                    self.error('deprecated concept set {0} linked for {1}'.format(
                        concept.concepticon_id, concept.id), cl.id)
