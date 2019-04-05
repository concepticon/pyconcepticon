import re
from operator import itemgetter
from collections import defaultdict, namedtuple
import warnings


import pybtex.database
from clldutils.path import readlines
from clldutils import jsonlib
from clldutils.misc import lazyproperty
from clldutils.apilib import API
from clldutils.source import Source

from pyconcepticon.util import read_dicts, lowercase, to_dict, UnicodeWriter, split, BIB_PATTERN
from pyconcepticon.glosses import concept_map, concept_map2

# The following symbols from models can explicitly be imported from pyconcepticon.api:
from pyconcepticon.models import (  # noqa: F401
    Languoid, Metadata, Concept, Conceptlist, ConceptRelations, Conceptset,
    REF_PATTERN, compare_conceptlists,
)


class Concepticon(API):
    """
    API to access the concepticon data.

    Objects for the various types of data stored in concepticon-data can be accessed as
    dictionaries mapping object IDs to specific object type instances.
    """
    def __init__(self, repos):
        """
        :param repos: Path to a clone or source dump of concepticon-data.
        """
        API.__init__(self, repos)
        self._to_mapping = {}

    def data_path(self, *comps):
        """
        Create a path relative to the `concepticondata` directory within the source repos.
        """
        return self.path('concepticondata', *comps)

    @lazyproperty
    def editors(self):
        res = []
        Editor = namedtuple('Editor', ['name', 'start', 'end'])
        in_editors, in_table = False, False
        for line in readlines(self.path('CONTRIBUTORS.md'), strip=True):
            if in_editors and line.startswith('#'):
                in_editors, in_table = False, False
                continue

            if line.endswith('# Editors'):
                in_editors = True
                continue

            if in_editors and line.startswith('--- '):
                in_table = True
                continue

            if in_table and '|' in line:
                period, _, name = line.partition('|')
                period = period.strip().partition('-')
                res.append(
                    Editor(name.strip(), period[0].strip(), period[2].strip() or None))
        return res

    @lazyproperty
    def vocabularies(self):
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
    def bibfile(self):
        return self.data_path('references', 'references.bib')

    @lazyproperty
    def sources(self):
        return jsonlib.load(self.data_path('sources', 'cdstar.json'))

    @lazyproperty
    def retirements(self):
        return jsonlib.load(self.data_path('retired.json'))

    @lazyproperty
    def bibliography(self):
        """
        :returns: `dict` mapping BibTeX IDs to `Reference` instances.
        """
        refs = []
        with self.bibfile.open(encoding='utf8') as fp:
            for key, entry in pybtex.database.parse_string(
                    fp.read(), bib_format='bibtex').entries.items():
                refs.append(Source.from_entry(key, entry))
        return to_dict(refs)

    @lazyproperty
    def conceptsets(self):
        """
        :returns: `dict` mapping ConceptSet IDs to `Conceptset` instances.
        """
        return to_dict(
            Conceptset(api=self, **lowercase(d))
            for d in read_dicts(self.data_path('concepticon.tsv')))

    @lazyproperty
    def conceptlists_dicts(self):
        return read_dicts(self.data_path('conceptlists.tsv'))

    @lazyproperty
    def conceptlists(self):
        """
        :returns: `dict` mapping ConceptList IDs to `Conceptlist` instances.

        .. note:: Individual concepts can be accessed via `Conceptlist.concepts`.
        """
        return to_dict(Conceptlist(api=self, **lowercase(d)) for d in self.conceptlists_dicts)

    @lazyproperty
    def metadata(self):
        """
        :returns: `dict` mapping metadata provider IDs to `Metadata` instances.
        """
        return to_dict(map(
            self._metadata,
            [p.stem for p in self.data_path('concept_set_meta').glob('*.tsv')]))

    def _metadata(self, id_):
        values_path = self.data_path('concept_set_meta', id_ + '.tsv')
        md_path = self.data_path('concept_set_meta', id_ + '.tsv-metadata.json')
        assert values_path.exists() and md_path.exists()
        md = jsonlib.load(md_path)
        return Metadata(
            id=id_,
            meta=md,
            values=to_dict(
                read_dicts(values_path, schema=md['tableSchema']),
                key=itemgetter('CONCEPTICON_ID')))

    @lazyproperty
    def relations(self):
        """
        :returns: `dict` mapping concept sets to related concepts.
        """
        return ConceptRelations(self.data_path('conceptrelations.tsv'))

    @lazyproperty
    def frequencies(self):
        D = defaultdict(int)
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
        cmap = (concept_map if full_search else concept_map2)(
            [i.get('GLOSS', i.get('ENGLISH')) for i in from_],
            [i[1] for i in to],
            similarity_level=similarity_level,
        )
        good_matches = 0
        with UnicodeWriter(out) as writer:
            writer.writerow(
                list(from_[0].keys())
                + ['CONCEPTICON_ID', 'CONCEPTICON_GLOSS', 'SIMILARITY'])
            for i, item in enumerate(from_):
                row = list(item.values())
                matches, sim = cmap.get(i, ([], 10))
                if sim <= similarity_level:
                    good_matches += 1
                if not matches:
                    writer.writerow(row + ['', '???', ''])
                elif len(matches) == 1:
                    row.extend([
                        to[matches[0]][0], to[matches[0]][1].split('///')[0], sim])
                    writer.writerow(row)
                else:
                    assert not full_search
                    # we need a list to retain the order by frequency
                    visited = []
                    for j in matches:
                        gls, cid = to[j][0], to[j][1].split('///')[0]
                        if (gls, cid) not in visited:
                            visited += [(gls, cid)]
                    if len(visited) > 1:
                        if not skip_multiple:
                            writer.writeblock(
                                row + [gls, cid, sim] for gls, cid in visited)
                    else:
                        row.extend([visited[0][0], visited[0][1], sim])
                        writer.writerow(row)
            writer.writerow(
                ['#',
                 '{0}/{1}'.format(good_matches, len(from_)),
                 '{0:.0f}%'.format(100 * good_matches / len(from_))]
                + (len(from_[0]) - 1) * [''])

        if out is None:
            print(writer.read().decode('utf-8'))

    def lookup(self, entries, full_search=False, similarity_level=5, language='en'):
        """
        :returns: `generator` of tuples (searchterm, concepticon_id, concepticon_gloss, \
        similarity).
        """
        to = self._get_map_for_language(language, None)
        tox = [i[1] for i in to]
        cfunc = concept_map2 if full_search else concept_map
        cmap = cfunc(
            entries,
            tox,
            similarity_level=similarity_level)
        for i, e in enumerate(entries):
            match, simil = cmap.get(i, [[], 100])
            yield set((e, to[m][0], to[m][1].split("///")[0], simil) for m in match)

    def check(self, *clids):
        errors = []
        assert self.retirements

        def _msg(type_, msg, name, line):  # pragma: no cover
            if line:
                line = ':%s' % line
            return '%s:%s%s: %s' % (type_.upper(), name, line or '', msg)

        def error(msg, name, line=0):  # pragma: no cover
            errors.append((msg, name, line))

        def warning(msg, name, line=0):  # pragma: no cover
            warnings.warn(_msg('warning', msg, name, line), Warning)

        for i, d in enumerate(self.conceptlists_dicts, start=1):
            try:
                Conceptlist(api=self, **lowercase(d))
            except ValueError as e:
                error(str(e), 'conceptlists.tsv', i)

        if errors:
            for msg, name, line in errors:
                print(_msg('error', msg, name, line))
            return not bool(errors)

        REF_WITHOUT_LABEL_PATTERN = re.compile(r'[^\]]\(:(ref|bib):[A-Za-z0-9\-]+\)')
        REF_WITHOUT_LINK_PATTERN = re.compile('[^(]:(ref|bib):[A-Za-z0-9-]+')

        # We collect all cite keys used to refer to references.
        all_refs = set()
        refs_in_bib = set(ref for ref in self.bibliography)
        for meta in self.metadata.values():
            cnames_schema = set(var['name'] for var in meta.meta['tableSchema']['columns'])
            cnames_tsv = set(list(meta.values.values())[0])
            if cnames_tsv - cnames_schema:  # pragma: no cover
                error('column names in {0} but not in json-specs'.format(meta.id), 'name')
            for i, value in enumerate(meta.values.values()):
                if set(value.keys()) != cnames_schema:  # pragma: no cover
                    error('meta data {0} contains irregular number of columns in line {1}'
                          .format(meta.id, i + 2), 'name')
            for ref in split(meta.meta.get('dc:references') or ''):
                if ref not in refs_in_bib:
                    error('cited bibtex record not in bib: {0}'.format(ref), 'name')
                all_refs.add(ref)

        # Make sure only records in the BibTeX file references.bib are referenced by
        # concept lists.
        for i, cl in enumerate(self.conceptlists.values()):
            if clids and cl.id not in clids:
                continue
            fl = ('conceptlists.tsv', i + 2)
            for ref in re.findall(BIB_PATTERN, cl.note) + cl.refs:
                if ref not in refs_in_bib:
                    error('cited bibtex record not in bib: {0}'.format(ref), *fl)
                else:
                    all_refs.add(ref)

            for m in REF_WITHOUT_LABEL_PATTERN.finditer(cl.note):
                error('link without label: {0}'.format(m.string[m.start():m.end()]), *fl)

            for m in REF_WITHOUT_LINK_PATTERN.finditer(cl.note):
                error('reference not in link: {0}'.format(m.string[m.start():m.end()]), *fl)

            for m in REF_PATTERN.finditer(cl.note):
                if m.group('id') not in self.conceptlists:
                    error('invalid conceptlist ref: {0}'.format(m.group('id')), *fl)

            # make also sure that all sources are accompanied by a PDF, but only write a
            # warning if this is not the case
            for ref in cl.pdf:
                if ref not in self.sources:  # pragma: no cover
                    warning('no PDF found for {0}'.format(ref), 'conceptlists.tsv')
        all_refs.add('List2016a')

        if not clids:
            # Only report unused references if we check all concept lists!
            for ref in refs_in_bib - all_refs:
                error('unused bibtex record: {0}'.format(ref), 'references.bib')

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
                    error(
                        'invalid {0}: {1}'.format(attr, rel[attr]), 'conceptrelations', i + 2)

        for fname in self.data_path('conceptlists').glob('*.tsv'):
            if clids and fname.stem not in clids:
                continue
            if fname.stem not in self.conceptlists:  # pragma: no cover
                error(
                    'conceptlist missing in conceptlists.tsv: {0}'.format(fname.name), '')

        broken_cls = []

        for cl in self.conceptlists.values():
            #
            # Check consistency between the csvw metadata and the column names in the list.
            #
            missing_in_md, missing_in_list = [], []
            cols_in_md = []
            for col in cl.metadata.tableSchema.columns:
                cnames = []  # all names or aliases csvw will recognize for this column
                if col.name in cols_in_md:
                    error('Duplicate name ot title in table schema: {0}'.format(col.name), cl.id)
                cnames.append(col.name)
                if col.titles:
                    c = col.titles.getfirst()
                    if c in cols_in_md:
                        error('Duplicate name ot title in table schema: {0}'.format(c), cl.id)
                    cnames.append(c)
                cols_in_md.extend(cnames)
                if not any(name in cl.cols_in_list for name in cnames):
                    # Neither name nor title of the column is in the actual list header.
                    missing_in_list.append(col.name)
            for col in cl.cols_in_list:
                if col not in cols_in_md:
                    missing_in_md.append(col)

            for col in missing_in_list:
                error('Column in metadata but missing in list: {0}'.format(col), cl.id)
            for col in missing_in_md:
                error('Column in list but missing in metadata: {0}'.format(col), cl.id)

            try:
                # Now check individual concepts:
                for i, concept in enumerate(cl.concepts.values()):
                    if not concept.id.startswith(cl.id):  # pragma: no cover
                        error(
                            'concept ID does not match concept list ID pattern %s' % concept.id,
                            cl.id)

                    if concept.concepticon_id:
                        cs = self.conceptsets.get(concept.concepticon_id)
                        if not cs:
                            error('invalid conceptset ID %s' % concept.concepticon_id, cl.id)
                        elif cs.gloss != concept.concepticon_gloss:
                            error(
                                'wrong conceptset GLOSS for ID {0}: {1} -> {2}'.format(
                                    cs.id, concept.concepticon_gloss, cs.gloss),
                                cl.id)

                    if i == 0:  # pragma: no cover
                        for lg in cl.source_language:
                            if lg.lower() not in concept.cols:
                                error('missing source language col %s' % lg.upper(), cl.id)

                    for lg in cl.source_language:  # pragma: no cover
                        if not (concept.attributes.get(lg.lower())
                                or getattr(concept, lg.lower(), None)
                                or (lg.lower() == 'english' and not concept.gloss)):
                            error('missing source language translation %s' % lg, cl.id, i + 2)
                    for attr, values in ref_cols.items():
                        val = getattr(concept, attr)
                        if val:
                            # check that there are not leading and trailing spaces
                            # (while computationally expensive, this helps catch really
                            # hard to find typos)
                            if val != val.strip():
                                error("leading or trailing spaces in value for %s: '%s'" %
                                      (attr, val), cl.id, i + 2)

                            if val not in values:  # pragma: no cover
                                error('invalid value for %s: %s' % (attr, val), cl.id, i + 2)
            except TypeError as e:
                broken_cls.append(cl.id)
                error(str(e), cl.id)

        sameas = {}
        glosses = set()
        for cs in self.conceptsets.values():
            if cs.gloss in glosses:  # pragma: no cover
                error('duplicate conceptset gloss: {0}'.format(cs.gloss), cs.id)
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

        for cl in self.conceptlists.values():
            if cl.id in broken_cls:
                continue
            for concept in cl.concepts.values():
                if concept.concepticon_id in deprecated:  # pragma: no cover
                    error('deprecated concept set {0} linked for {1}'.format(
                        concept.concepticon_id, concept.id), cl.id)

        for msg, name, line in errors:
            print(_msg('error', msg, name, line))
        return not bool(errors)

    def _set_operation(self, type_, *clids, **kw):
        assert type_ in ['union', 'intersection']
        for c, lists in compare_conceptlists(self, *clids, **kw):
            if type_ == 'union' \
                    or len(set([x[0] for x in lists if x[1] >= 0])) == len(clids):
                # For union, take all conceptsets in any of the lists, for intersection only
                # conceptsets which appear in all lists.
                marker = '*' if not len([0 for x in lists if x[1] == 0]) else ' '
                marker += '<' if len([x for x in lists]) < len(clids) else ' '
                yield (
                    marker,
                    c,
                    self.conceptsets[c].gloss,
                    ', '.join(
                        ['{0[3]} ({0[1]}, {0[0]})'.format(x) for x in
                         lists if x[1] != 0]))

    def union(self, *clids, **kw):
        return list(self._set_operation('union', *clids, **kw))

    def intersection(self, *clids, **kw):
        return list(self._set_operation('intersection', *clids, **kw))
