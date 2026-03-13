import posix

import pytest

from pyconcepticon.glosses import *
from pyconcepticon.glosses import ParseSpec


def test_ParseSpec_parse_constituent():
    spec = ParseSpec.for_language('en')
    gloss, pos = spec.parse_constituent('full gloss', 'word [with (nested) comment]', '')
    assert gloss.comment_start == '['
    assert gloss.comment_end == ']'
    assert gloss.comment == 'with (nested) comment'


@pytest.mark.parametrize(
    'g,res',
    [
        (
            'the dog (n)',
            ('dog', '(', 'n', ')', 'noun', '', 'dog', 'the dog (n)')),
        (
            'to be a dog',
            ('a dog', '', '', '', 'verb', 'be', 'dog', 'to be a dog')),
        (
            "to kill",
            ('kill', '', '', '', 'verb', '', 'kill', 'to kill')),
        (
            "kill",
            ('kill', '', '', '', '', '', 'kill', 'kill')),
        (
            "kill (v.)",
            ('kill', '(', 'v.', ')', 'verb', '', 'kill', 'kill (v.)')),
        (
            "kill (somebody)",
            ('kill', '(', 'somebody', ')', '', '', 'kill', 'kill (somebody)')),
    ]
)
def test_parse_gloss(g, res):
    assert parse_gloss(g)[0] == Gloss(*res)


def test_parse_gloss_2():
    assert parse_gloss('the mountain or hill')[1].pos == Pos.NOUN

    g1 = Gloss.from_string('der Berg', language='de')
    g2 = Gloss.from_string('Berg (n.)')
    assert g1.similarity(g2) == Similarity.SAME_MAIN

    g1 = Gloss.from_string('der Berg', language='de')
    g2 = Gloss.from_string('Berg')
    assert g1.similarity(g2) == Similarity.SAME_MAIN_DIFFERENT_POS

    g1 = Gloss.from_string('der Berg a', language='de')
    g2 = Gloss.from_string('Berg b (n.)')
    assert g1.similarity(g2) == Similarity.SAME_LONGEST

    g = Gloss.from_string('la montagne', language='fr')
    assert g.pos == Pos.NOUN

    g1 = Gloss.from_string('montagne', language='fr')
    g2 = Gloss.from_string('la montagne', language='fr')
    assert g1.similarity(g2) == Similarity.SAME_MAIN_DIFFERENT_POS

    # error on invalid gloss
    with pytest.raises(ValueError):
        parse_gloss(None)

    with pytest.raises(ValueError):
        parse_gloss('')


def test_concept_map():
    f, t = ['the dog', 'to kill'], ['kill', 'dog (verb)', 'to kill']
    assert concept_map(f, t) == {0: Mapping([1], 4), 1: Mapping([2], 1)}
    assert 0 not in concept_map(f, t, similarity_level=1)

    assert concept_map([('house', 'noun', 5)], [('house', 'noun', 4)]) == {0: Mapping([0], 1)}
