"""
Module provides functions for the handling of concept glosses in linguistic datasets.
"""
import re
import enum
from typing import Union, Literal, Callable, Any, Optional
import functools
import itertools
import collections
from collections.abc import Iterable, Generator
import dataclasses

__all__ = ['parse_gloss', 'Gloss', 'concept_map', 'Mapping', 'SimilarityLevel']


class SimilarityLevel(enum.Enum):
    SAME = 1
    SAME_DIFFERENT_POS = 2
    SAME_MAIN = 3
    SAME_MAIN_DIFFERENT_POS = 4
    SAME_LONGEST = 5
    SAME_LONGEST_DIFFERENT_POS = 6
    LONGEST_IS_CONTAINED = 7
    LONGEST_CONTAINS = 8
    DIFFERENT = 100


@dataclasses.dataclass
class Gloss:
    main: str = ''
    # the start character indicating a potential comment:
    comment_start: str = ''
    # the comment (everything occurring in brackets in the input string:
    comment: str = ''
    # the end character indicating the end of a potential comment:
    comment_end: str = ''
    # the part of speech, in case this was specificied by a preceding "the" or a
    # preceding "to" in the mainpart of the string:
    pos: str = ''
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

    @functools.cached_property
    def tokens(self):
        return ' '.join(s for s in self.gloss.split() if s not in ['or'])

    def similarity(self, other) -> SimilarityLevel:
        same_pos = self.pos and self.pos == other.pos
        # first-order-match: identical glosses
        if self.gloss == other.gloss:
            if same_pos:
                return SimilarityLevel.SAME
            return SimilarityLevel.SAME_DIFFERENT_POS
        # second-order match: identical main-parts
        if self.main == other.gloss or self.gloss == other.main or self.main == other.main:
            # best match if pos matches
            if same_pos:
                return SimilarityLevel.SAME_MAIN
            return SimilarityLevel.SAME_MAIN_DIFFERENT_POS
        if self.longest_part == other.longest_part:
            if same_pos:
                return SimilarityLevel.SAME_LONGEST
            return SimilarityLevel.SAME_LONGEST_DIFFERENT_POS
        if other.longest_part in self.main.split():
            return SimilarityLevel.LONGEST_IS_CONTAINED
        if self.longest_part in other.main.split():
            return SimilarityLevel.LONGEST_CONTAINS
        return SimilarityLevel.DIFFERENT

    @classmethod
    def from_string(cls, s, language='en'):
        return parse_gloss(s, language=language)[0]


class Pos(enum.Enum):
    NOUN = enum.auto()
    VERB = enum.auto()
    ADJECTIVE = enum.auto()
    ADVERB = enum.auto()
    CLASSIFIER = enum.auto()

    @classmethod
    def from_string(cls, s):
        return getattr(cls, s.upper())


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
    pos_markers: dict[str, Pos]
    prefixes: list[str]
    pos_abbreviations: list[tuple[str, Pos]]
    punctuation: str = '?!"¨:;,»«´“”*+-'
    split_pattern: re.Pattern = re.compile(r',|;|:|/| or | OR ')
    comment_marker: dict[str, str] = dataclasses.field(
        default_factory=lambda: {'(': ')', '[': ']', '{': '}', '（': '）', '<': '>'})

    @classmethod
    def for_language(cls, language='en'):
        pos_markers = POS_MARKERS_BY_LANGUAGE.get(language, {})
        pos_markers = {k: Pos.from_string(v) for k, v in pos_markers.items()}
        abbreviations = [(k, Pos.from_string(v)) for k, v in POS_ABBREVIATIONS]
        return cls(
            pos_markers,
            PREFIXES_BY_LANGUAGE.get(language, []),
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

    def parse_constituent(self, full_gloss, constituent, gpos) -> tuple[Optional[Gloss], str]:
        gloss = Gloss(gloss=full_gloss)
        mainpart = self._strip_comments(constituent, gloss)
        mainpart = self._strip_punctuation(mainpart).strip().lower().split()

        # search for pos-markers
        if gpos:
            gloss.pos = gpos
        else:
            if len(mainpart) > 1 and mainpart[0] in self.pos_markers:
                gpos = gloss.pos = self.pos_markers[mainpart.pop(0)].name.lower()

        # search for strip-off-prefixes
        if len(mainpart) > 1 and mainpart[0] in self.prefixes:
            gloss.prefix = mainpart.pop(0)

        if mainpart:
            # check for a "first part" in case we encounter white space in the
            # data (and return only the largest string of them)
            gloss.longest_part = sorted(mainpart, key=lambda x: len(x))[-1]

            # search for pos in comment
            if not gloss.pos:
                cparts = gloss.comment.split()
                for p, t in self.pos_abbreviations:
                    if p in cparts or p in mainpart or t.name in cparts or t.name in mainpart:
                        gloss.pos = t.name.lower()
                        break

            gloss.main = ' '.join(mainpart)
            return gloss, gpos
        return None, gpos


def parse_gloss(gloss: str, language='en') -> list[Gloss]:
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

    # if the gloss consists of multiple parts, we store both the separate part
    # and a normalized form of the full gloss
    constituents = spec.split_constituents(gloss)

    glosses = []
    gpos = ''
    for constituent in constituents:
        if constituent.strip():
            res, gpos = spec.parse_constituent(gloss, constituent, gpos)
            if res:
                glosses.append(res)

    return glosses


GlossDictType = dict[int, list[Gloss]]


@functools.total_ordering
@dataclasses.dataclass(frozen=True)
class Similarity:
    from_key: int
    to_key: int
    level: int
    frequency: int

    def __lt__(self, other):
        """
        Order from best to worst.

        Smaller level is better. Higher frequency is better.
        """
        return (self.level, -self.frequency) < (other.level, -other.frequency)


@dataclasses.dataclass
class Mapping:
    to_keys: Union[list[int]] = dataclasses.field(default_factory=list)
    similarity: int = SimilarityLevel.DIFFERENT.value

    def sort_keys(self, sortkey: Callable[[int], Any]):
        self.to_keys = sorted(self.to_keys, key=sortkey, reverse=True)


class MappingDict(dict):
    def get_mapping(self, item):
        return self.get(item, Mapping())


@dataclasses.dataclass
class GlossMapper:
    """Bundle functionality to map glosses with the data from two concept lists."""
    from_list: GlossDictType = dataclasses.field(default_factory=dict)
    to_list: GlossDictType = dataclasses.field(default_factory=dict)
    mapped: dict[str, dict[Literal["from_list", "to_list"], list[int]]] = dataclasses.field(
        default_factory=lambda: collections.defaultdict(lambda: collections.defaultdict(list)))

    def add(self, key, i, glosses, pos=None, frequency=None):  # pylint: disable=R0913,R0917
        if pos or frequency:
            for gloss in glosses:
                gloss.pos = pos
                gloss.frequency = frequency
        getattr(self, key)[i] = glosses

        for gloss in glosses:
            self.mapped[gloss.main][key] += [i]

    def _iter_similarities(self, similarity_level) -> Generator[Similarity, None, None]:
        # now that we have prepared all the glossed list as planned, we compare them item by
        # item and check for similarity
        for i, fglosses in self.from_list.items():
            for fgloss in fglosses:
                for j, tglosses in self.to_list.items():
                    for tgloss in tglosses:
                        sim = fgloss.similarity(tgloss).value
                        if sim and sim <= similarity_level:
                            yield Similarity(i, j, sim, tgloss.frequency)

    def best_matches(self, similarity_level) -> MappingDict:
        # we keep track of which target concepts have already been chosen as best matches:
        best, consumed, alternatives = MappingDict(), set(), collections.defaultdict(list)
        # go through *all* matches from best to worst:
        for sim in sorted(list(self._iter_similarities(similarity_level))):
            if sim.from_key not in best and sim.to_key not in consumed:
                best[sim.from_key] = Mapping([sim.to_key], sim.level)
                consumed.add(sim.to_key)
            elif sim.to_key not in alternatives[sim.from_key]:
                alternatives[sim.from_key].append(sim.to_key)
        return best

    def best_matches_2(self) -> MappingDict:
        mappings = MappingDict()
        for v in self.mapped.values():
            if not ('from_list' in v and 'to_list' in v):
                continue
            for i in v['from_list']:
                current = Mapping()
                if i in mappings:
                    current = Mapping(mappings[i].to_keys, mappings[i].similarity)
                for j in v['to_list']:
                    for gloss_a, gloss_b in itertools.product(self.from_list[i], self.to_list[j]):
                        sim = gloss_a.similarity(gloss_b).value
                        if sim < current.similarity:
                            current.to_keys = [j]
                            current.similarity = sim
                        elif sim == current.similarity:
                            current.to_keys.append(j)
                mappings[i] = current
        return mappings


def concept_map2(from_, to, freqs=None, language='en', **_):
    # extract glossing information from the data
    glosses = GlossMapper()
    for l_, key in [(from_, 'from_list'), (to, 'to_list')]:
        for i, concept in enumerate(l_):
            glosses.add(key, i, parse_gloss(concept, language=language))

    # get frequencies
    freqs = freqs or collections.defaultdict(int)
    mappings = glosses.best_matches_2()
    for m in mappings.values():
        m.sort_keys(lambda x: freqs.get(to[x].split('///')[0], 0))
    return mappings


def concept_map(
        from_: Iterable[Union[tuple[str, str, float], str]],
        to: Iterable[Union[tuple[str, str, float], str]],
        similarity_level=5,
        language='en',
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
    for l_, key in [(from_, 'from_list'), (to, 'to_list')]:
        for i, concept in enumerate(l_):
            if isinstance(concept, tuple):
                concept, pos, frequency = concept
            else:
                pos, frequency = None, 0
            glosses.add(
                key, i, parse_gloss(concept, language=language), pos=pos, frequency=frequency)

    return glosses.best_matches(similarity_level)
