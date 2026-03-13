"""
Module provides functions for the handling of concept glosses in linguistic datasets.
"""
import re
import enum
from typing import Union, Literal, Callable, Any, Optional, get_args
import functools
import itertools
import collections
from collections.abc import Iterable, Generator
import dataclasses

from .util import read_dicts, UnicodeWriter
from ._compat import StrEnum

__all__ = [
    'parse_gloss', 'Gloss', 'concept_map', 'Mapping', 'Similarity', 'Pos', 'map_list',
    'GlossLanguage', 'MapOptions']


class Pos(enum.Enum):
    """Recognized parts of speech in glosses."""
    NOUN = enum.auto()
    VERB = enum.auto()
    ADJECTIVE = enum.auto()
    ADVERB = enum.auto()
    CLASSIFIER = enum.auto()

    @classmethod
    def from_string(cls, s: str) -> 'Pos':
        """Get the enum symbol from its name."""
        return getattr(cls, s.upper())


class Similarity(enum.IntEnum):
    """Enum to make similarity measures more transparent."""
    SAME = 1
    SAME_DIFFERENT_POS = 2
    SAME_MAIN = 3
    SAME_MAIN_DIFFERENT_POS = 4
    SAME_LONGEST = 5
    SAME_LONGEST_DIFFERENT_POS = 6
    LONGEST_IS_CONTAINED = 7
    LONGEST_CONTAINS = 8
    DIFFERENT = 100

    @classmethod
    def from_int(cls, n: int = 5) -> Optional['Similarity']:
        """Get the enum symbol from its name."""
        if isinstance(n, cls):
            return n
        for sim in cls:
            if sim.value == n:
                return sim
        return None  # pragma: no cover


class GlossLanguage(StrEnum):
    """Languages used for glossing in conceptlists."""
    FRENCH = 'fr'
    ENGLISH = 'en'
    SPANISH = 'es'
    GERMAN = 'de'
    POLISH = 'pl'
    LATIN = 'lt'
    CHINESE = 'zh'
    PORTUGUESE = 'pt'
    RUSSIAN = 'ru'
    ITALIAN = 'it'

    @classmethod
    def from_string(cls, s: str = 'en') -> Optional['GlossLanguage']:
        """Get the enum symbol from its name."""
        if isinstance(s, cls):
            return s
        for lg in cls:
            if lg.value == s:
                return lg
        return None  # pragma: no cover


LanguageType = Union[str, GlossLanguage]


@dataclasses.dataclass
class Gloss:  # pylint: disable=too-many-instance-attributes
    """
    A gloss, as parsed from a string with several constituent parts.

    >>> Gloss.from_string('word [comment]').comment
    'comment'
    """
    main: str = ''
    # the start character indicating a potential comment:
    comment_start: str = ''
    # the comment (everything occurring in brackets in the input string:
    comment: str = ''
    # the end character indicating the end of a potential comment:
    comment_end: str = ''
    # the part of speech, in case this was specificied by a preceding "the" or a
    # preceding "to" in the mainpart of the string:
    pos: Optional[Pos] = None
    # the prefix, that is, words, like, eg. "be", "in", which may precede the main
    # gloss in concept lists, as in "be quiet":
    prefix: str = ''
    # the longest constituent, which is identical with the main part if there's no
    # whitespace in the main part, otherwise the longest part part of the main gloss
    # split by whitespace:
    longest_part: str = ''
    # the original gloss (for the purpose of testing):
    gloss: str = ''

    frequency: int = 0

    def __post_init__(self):
        self.gloss = self.gloss.lower().replace('*', '')
        if isinstance(self.pos, str):
            if self.pos:
                self.pos = Pos.from_string(self.pos)
            else:
                self.pos = None

    def similarity(self, other) -> Similarity:  # pylint: disable=R0911
        """Compute similarity between two glosses."""
        same_pos = self.pos and self.pos == other.pos
        # first-order-match: identical glosses
        if self.gloss == other.gloss:
            if same_pos:
                return Similarity.SAME
            return Similarity.SAME_DIFFERENT_POS
        # second-order match: identical main-parts
        if self.main == other.gloss or self.gloss == other.main or self.main == other.main:
            # best match if pos matches
            if same_pos:
                return Similarity.SAME_MAIN
            return Similarity.SAME_MAIN_DIFFERENT_POS
        if self.longest_part == other.longest_part:
            if same_pos:
                return Similarity.SAME_LONGEST
            return Similarity.SAME_LONGEST_DIFFERENT_POS
        if other.longest_part in self.main.split():
            return Similarity.LONGEST_IS_CONTAINED
        if self.longest_part in other.main.split():
            return Similarity.LONGEST_CONTAINS
        return Similarity.DIFFERENT

    @classmethod
    def from_string(cls, s: str, language: LanguageType = GlossLanguage.ENGLISH) -> 'Gloss':
        """Parse a gloss from the string."""
        if isinstance(language, str):
            language = GlossLanguage.from_string(language)
        return parse_gloss(s, language=language)[0]


POS_MARKERS_BY_LANGUAGE = {
    'en': {'the': 'noun', 'a': 'noun', 'to': 'verb'},
    'de': {'der': 'noun', 'die': 'noun', 'das': 'noun'},
    'fr': {
        'le': 'noun',
        'la': 'noun',
        'les': 'noun',
        'du': 'noun',
        'des': 'noun',
        'de': 'noun',
        'un': 'noun',
        'une': 'noun',
    },
    'es': {
        "el": "noun",
        "la": "noun",
        "los": "noun",
        "mi": "noun",
        "un": "noun",
        "una": "noun",
        "unos": "noun",
        "las": "noun",
        "su": "noun",
    }
}
PREFIXES_BY_LANGUAGE = {
    'en': ['be', 'in', 'at'],
    'fr': ['il', 'est'],
    'es': ["lo", "les", "le"],
}
POS_ABBREVIATIONS = [
    ('vb', 'verb'),
    ('v.', 'verb'),
    ('v', 'verb'),
    ('adj', 'adjective'),
    ('nn', 'noun'),
    ('n.', 'noun'),
    ('adv', 'adverb'),
    ('noun', 'noun'),
    ('verb', 'verb'),
    ('adjective', 'adjective'),
    ('cls', 'classifier')
]


@dataclasses.dataclass
class ParseSpec:
    """Specification (and implementation) for the parsing of glosses for comparison."""
    pos_markers: dict[str, Pos]
    prefixes: list[str]
    pos_abbreviations: list[tuple[str, Pos]]
    punctuation: str = '?!"¨:;,»«´“”*+-'
    split_pattern: re.Pattern = re.compile(r',|;|:|/| or | OR ')
    comment_marker: dict[str, str] = dataclasses.field(
        default_factory=lambda: {'(': ')', '[': ']', '{': '}', '（': '）', '<': '>'})

    @classmethod
    def for_language(
            cls,
            language: Optional[Union[str, GlossLanguage]] = GlossLanguage.ENGLISH,
    ) -> 'ParseSpec':
        """Get a ParseSpec, optionally tuned to a particular gloss language."""
        if isinstance(language, str):
            language = GlossLanguage.from_string(language)
        pos_markers = POS_MARKERS_BY_LANGUAGE.get(language.value, {})
        pos_markers = {k: Pos.from_string(v) for k, v in pos_markers.items()}
        abbreviations = [(k, Pos.from_string(v)) for k, v in POS_ABBREVIATIONS]
        return cls(
            pos_markers,
            PREFIXES_BY_LANGUAGE.get(language.value, []),
            # Sort abbreviations by descending length.
            sorted(abbreviations, key=lambda x: len(x[0]), reverse=True),
        )

    def split_constituents(self, gloss):
        """
        >>> spec = ParseSpec.for_language('en')
        >>> spec.split_constituents('arm OR hand')
        ['arm', 'hand', 'arm / hand']
        """
        constituents = [x.strip() for x in self.split_pattern.split(gloss) if x.strip()]
        if len(constituents) > 1:
            constituents += [' / '.join(sorted([c.strip() for c in constituents]))]
        return constituents

    def _strip_comments(self, constituent: str, res: Gloss) -> str:
        mainpart = ''
        in_comment: list[str] = []
        for char in constituent:
            if char in self.comment_marker:
                in_comment.append(self.comment_marker[char])
                if not res.comment_start:
                    res.comment_start = char
                else:
                    res.comment += char
                continue
            if in_comment and char == in_comment[-1]:
                in_comment.pop()
                if not in_comment:
                    res.comment_end = char
                else:
                    res.comment += char
                continue
            if in_comment:
                res.comment += char
            else:
                mainpart += char
        return mainpart

    def _strip_punctuation(self, s: str) -> str:
        return ''.join(c for c in s if c not in self.punctuation)

    def parse_constituent(
            self,
            full_gloss,
            constituent,
            gpos: Optional[Pos] = None,
    ) -> tuple[Optional[Gloss], Optional[Pos]]:
        """Parse a gloss constituent into a proper Gloss or part-of-speech information."""
        gloss = Gloss(gloss=full_gloss)
        mainpart = self._strip_comments(constituent, gloss)
        mainpart = self._strip_punctuation(mainpart).strip().lower().split()

        # search for pos-markers
        if gpos:
            gloss.pos = gpos
        else:
            if len(mainpart) > 1 and mainpart[0] in self.pos_markers:
                gpos = gloss.pos = self.pos_markers[mainpart.pop(0)]

        # search for strip-off-prefixes
        if len(mainpart) > 1 and mainpart[0] in self.prefixes:
            gloss.prefix = mainpart.pop(0)

        if mainpart:
            # check for a "first part" in case we encounter white space in the
            # data (and return only the largest string of them)
            gloss.longest_part = sorted(mainpart, key=len)[-1]

            # search for pos in comment
            if not gloss.pos:
                cparts = gloss.comment.split()
                for p, t in self.pos_abbreviations:
                    if p in cparts or p in mainpart or t.name in cparts or t.name in mainpart:
                        gloss.pos = t
                        break

            gloss.main = ' '.join(mainpart)
            return gloss, gpos
        return None, gpos


def parse_gloss(gloss: str, language: LanguageType = GlossLanguage.ENGLISH) -> list[Gloss]:
    """
    Parse a gloss into its constituents by applying some general logic.

    Parameters
    ----------
    gloss : str
        The gloss as found in various sources (we assume that we are dealing
        with English glosses here.

    Returns
    -------
    A list of `Gloss` instances.

    Notes
    -----

    The basic purpose of this function is to provide a means to make it easier
    to compare meanings across different resources. Often, linguists will
    annotate their resources quite differently, and for one and the same
    concept, we may find very different glosses. The concept "kill [verb]", for
    example may be glossed as "to kill", "kill", "kill (v.)", "kill
    (somebody)", etc. In order to guarantee comparability, this function tries
    to use basic knowledge of glossing tendencies to disentangle the variety of
    glossing styles which can be found in the literature. Thus, in the case of
    "kill [verb]", the function will analyze the different strings as follows::

        >>> glosses = ["to kill", "kill", "kill (v.)", "kill (somebody)"]
        >>> for gloss in glosses:
        ...     parsed_gloss = parse_gloss(gloss)[0]
        ...     print(parsed_gloss.main, parsed_gloss.pos)
        kill verb
        kill
        kill verb
        kill

    As can be seen: it seeks to extract the most important part of the gloss
    and may thus help to compare different glosses across different resources.
    """
    if not gloss:
        raise ValueError("Your gloss is empty")
    spec = ParseSpec.for_language(language)

    # we use /// as our internal marker for glosses preceded by concepticon
    # gloss information and followed by literal readings
    if '///' in gloss:
        gloss = gloss.split('///')[1]

    glosses = []
    gpos = None
    for constituent in spec.split_constituents(gloss):
        if constituent.strip():
            res, gpos = spec.parse_constituent(gloss, constituent, gpos)
            if res:
                glosses.append(res)

    return glosses


GlossDictType = dict[int, list[Gloss]]


@functools.total_ordering
@dataclasses.dataclass(frozen=True)
class SimilarPair:
    """Information about a pair of similar glosses in two conceptlists."""
    from_key: int
    to_key: int
    similarity: Similarity
    frequency: int

    def __lt__(self, other):
        """
        Order from best to worst.

        Smaller level is better. Higher frequency is better.
        """
        return (self.similarity, -self.frequency) < (other.similarity, -other.frequency)


@dataclasses.dataclass
class Mapping:
    """
    Items of a conceptlist can be associated with a Mapping, identifying similar items in a
    different list,
    """
    to_keys: Union[list[int]] = dataclasses.field(default_factory=list)
    similarity: Similarity = Similarity.DIFFERENT

    def sort_keys(self, sortkey: Callable[[int], Any]):
        """Sort keys in the mapping according to sortkey."""
        self.to_keys = sorted(self.to_keys, key=sortkey, reverse=True)


class MappingDict(dict):
    """Map conceptlist items identified by index to a Mapping"""
    def get_mapping(self, item: int) -> Mapping:
        """Get the associated mapping or the default, i.e. "null" mapping."""
        return self.get(item, Mapping())


ListIdentifierType = Literal["from_list", "to_list"]


@dataclasses.dataclass
class GlossMapper:
    """Bundle functionality to map glosses with the data from two concept lists."""
    from_list: GlossDictType = dataclasses.field(default_factory=dict)
    to_list: GlossDictType = dataclasses.field(default_factory=dict)
    mapped: dict[str, dict[ListIdentifierType, list[int]]] = dataclasses.field(
        default_factory=lambda: collections.defaultdict(lambda: collections.defaultdict(list)))

    def add(self,   # pylint: disable=R0913,R0917
            key: ListIdentifierType,
            i: int,
            glosses: Iterable[Gloss],
            pos: Optional[Pos] = None,
            frequency: Optional[int] = None):
        """Add glosses associated with a concept list item."""
        if pos or frequency:
            for gloss in glosses:
                gloss.pos = pos
                gloss.frequency = frequency
        getattr(self, key)[i] = glosses

        for gloss in glosses:
            self.mapped[gloss.main][key] += [i]

    def _iter_mapped_values(self) -> Generator[tuple[list[int], list[int]]]:
        for v in self.mapped.values():
            if all(arg in v for arg in get_args(ListIdentifierType)):
                yield v['from_list'], v['to_list']

    def _iter_similarpairs(
            self,
            similarity_level: Similarity,
    ) -> Generator[SimilarPair, None, None]:
        # now that we have prepared all the glossed list as planned, we compare them item by
        # item and check for similarity
        for i, fglosses in self.from_list.items():
            for fgloss in fglosses:
                for j, tglosses in self.to_list.items():
                    for tgloss in tglosses:
                        sim = fgloss.similarity(tgloss)
                        if sim and sim <= similarity_level:
                            yield SimilarPair(i, j, sim, tgloss.frequency)

    def best_matches(self, similarity_level: Similarity) -> MappingDict:
        """
        The default matching implementation.
        """
        # we keep track of which target concepts have already been chosen as best matches:
        best, consumed, alternatives = MappingDict(), set(), collections.defaultdict(list)
        # go through *all* matches from best to worst:
        for pair in sorted(list(self._iter_similarpairs(similarity_level))):
            if  pair.from_key not in best and pair.to_key not in consumed:
                best[pair.from_key] = Mapping([pair.to_key], pair.similarity)
                consumed.add(pair.to_key)
            elif pair.to_key not in alternatives[pair.from_key]:
                alternatives[pair.from_key].append(pair.to_key)
        return best

    def best_matches_2(self) -> MappingDict:
        """
        An alternative matching implentation.
        """
        mappings = MappingDict()
        for from_list, to_list in self._iter_mapped_values():
            for i in from_list:
                current = Mapping()
                if i in mappings:
                    current = Mapping(mappings[i].to_keys, mappings[i].similarity)
                for j in to_list:
                    for gloss_a, gloss_b in itertools.product(self.from_list[i], self.to_list[j]):
                        sim = gloss_a.similarity(gloss_b)
                        if sim < current.similarity:
                            current.to_keys = [j]
                            current.similarity = sim
                        elif sim == current.similarity:
                            current.to_keys.append(j)
                mappings[i] = current
        return mappings


def concept_map2(
        from_: Iterable[str],
        to: Iterable[str],
        freqs: Optional[dict[str, int]] = None,
        language: Optional[LanguageType] = GlossLanguage.ENGLISH,
        **_,
) -> MappingDict:
    """
    Match concepts from one list to the concepts of another one, optionally taking into account
    frequencies.
    """
    # extract glossing information from the data
    glosses = GlossMapper()
    key: ListIdentifierType

    for l_, key in [(from_, 'from_list'), (to, 'to_list')]:
        for i, concept in enumerate(l_):
            glosses.add(key, i, parse_gloss(concept, language=language))

    freqs = freqs or collections.defaultdict(int)
    mappings = glosses.best_matches_2()
    for m in mappings.values():
        m.sort_keys(lambda x: freqs.get(to[x].split('///')[0], 0))
    return mappings


def concept_map(
        from_: Iterable[Union[tuple[str, str, float], str]],
        to: Iterable[Union[tuple[str, str, float], str]],
        similarity_level: Similarity = Similarity.SAME_LONGEST,
        language: Optional[LanguageType] = GlossLanguage.ENGLISH,
) -> MappingDict:
    """
    Function compares two concept lists and outputs suggestions for mapping.

    Notes
    -----
    Idea is to take one conceptlist as the basic list and then to search for a plausible
    mapping of concepts in the second list to the first list. All suggestions can then be
    output in various forms, both with multiple matches excluded or included, and in
    textform or in other forms.
    """
    # extract glossing information from the data
    glosses = GlossMapper()
    key: ListIdentifierType
    for l_, key in [(from_, 'from_list'), (to, 'to_list')]:
        for i, concept in enumerate(l_):
            if isinstance(concept, tuple):
                concept, pos, frequency = concept
            else:
                pos, frequency = None, 0
            glosses.add(
                key, i, parse_gloss(concept, language=language), pos=pos, frequency=frequency)

    return glosses.best_matches(similarity_level)


@dataclasses.dataclass
class MapOptions:
    """Bag of options informing the mapping of glosses."""
    language: GlossLanguage = GlossLanguage.ENGLISH
    full_search: bool = False
    similarity_level: Similarity = Similarity.SAME_LONGEST
    skip_multiple: bool = False

    def __post_init__(self):
        if isinstance(self.language, str):
            self.language = GlossLanguage.from_string(self.language) or GlossLanguage.ENGLISH


def map_list(
        clist,
        to,
        out=None,
        options: MapOptions = MapOptions(),
):
    """Map items in a conceptlist to concepticon."""
    assert clist.exists(), f"File {clist} does not exist"
    from_ = read_dicts(clist)

    language = GlossLanguage.from_string(options.language)
    gloss = language.name if language else 'GLOSS'
    cmap: MappingDict = (concept_map if options.full_search else concept_map2)(
        [i.get('GLOSS', i.get(gloss)) for i in from_],
        [i[1] for i in to],
        similarity_level=options.similarity_level,
        language=language,
    )
    good_matches = 0

    with UnicodeWriter(out) as writer:
        writer.writerow(
            list(from_[0].keys())
            + ['CONCEPTICON_ID', 'CONCEPTICON_GLOSS', 'SIMILARITY'])
        for i, item in enumerate(from_):
            row = list(item.values())
            mapping = cmap.get_mapping(i)
            if mapping.similarity <= options.similarity_level:
                good_matches += 1
            _map_row(row, mapping, to, options, writer)
        writer.writerow(
            ['#', f'{good_matches}/{len(from_)}', f'{100 * good_matches / len(from_):.0f}%']
            + (len(from_[0]) - 1) * [''])

    if out is None:
        print(writer.read().decode('utf-8'))


def _map_row(row, mapping: Mapping, to, options: MapOptions, writer):
    if not mapping.to_keys:
        writer.writerow(row + ['', '???', ''])
        return
    if len(mapping.to_keys) == 1:
        row.extend([
            to[mapping.to_keys[0]][0],
            to[mapping.to_keys[0]][1].split('///')[0],
            mapping.similarity.value])
        writer.writerow(row)
        return
    assert not options.full_search
    # we need a list to retain the order by frequency
    visited = []
    for j in mapping.to_keys:
        gls, cid = to[j][0], to[j][1].split('///')[0]
        if (gls, cid) not in visited:
            visited += [(gls, cid)]
    if len(visited) > 1:
        if not options.skip_multiple:
            writer.writeblock(row + [gls, cid, mapping.similarity] for gls, cid in visited)
    else:
        writer.writerow(row + [visited[0][0], visited[0][1], mapping.similarity])
