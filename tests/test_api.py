import pytest

from pyconcepticon.models import Concept, Conceptlist, Conceptset


def test_Concept():
    d = {f: '' for f in Concept.public_fields()}
    with pytest.raises(ValueError):
        Concept(**d)

    d['id'] = 'i'
    with pytest.raises(ValueError):
        Concept(**d)

    d['number'] = 'i'
    with pytest.raises(ValueError):
        Concept(**d)

    d['number'] = '1b'
    with pytest.raises(ValueError):
        Concept(**d)

    d['gloss'] = 'g'
    Concept(**d)


def test_dataset_metadata(api):
    assert api.dataset_metadata.publisher.place == 'example'
    assert api.dataset_metadata.license.url == 'http://example.org'
    assert api.dataset_metadata.license.icon == 'cc-by.png'
    assert api.dataset_metadata.domain == 'example.org'


def test_Conceptlist(fixturedir, api):
    clist = Conceptlist.from_file(fixturedir.joinpath('conceptlist.tsv'), api=api)
    assert len(clist.concepts) == 1

    with pytest.raises(ValueError):
        Conceptlist(
            api=None,
            id='xy',
            author='x',
            year='1234',
            alias=None,
            items=4,
            list_suffix=None,
            note='',
            pages='',
            pdf='',
            refs='',
            source_language='y',
            tags='',
            target_language=None,
            url=None)


@pytest.mark.filterwarnings("ignore:Unspecified column")
def test_Conceptset(api):
    assert len(api.conceptsets['1906'].concepts) > 0

    d = {a: '' for a in Conceptset.public_fields()}
    d['semanticfield'] = 'xx'
    d['api'] = api
    with pytest.raises(ValueError):
        Conceptset(**d)


def test_editors(api):
    assert len(api.editors) == 4


def test_map(api, capsys, fixturedir):
    api.map(fixturedir.joinpath('conceptlist.tsv'))
    out, err = capsys.readouterr()
    assert 'CONCEPTICON_ID' in out
    assert len(api.conceptsets['1'].concepts) == 0

    api.map(
        fixturedir.joinpath('conceptlist.tsv'),
        fixturedir.joinpath('conceptlist2.tsv'))
    out, err = capsys.readouterr()
    assert 'CONCEPTICON_ID' in out


def test_lookup(api):
    if api.repos.exists():
        assert list(api.lookup(['sky', 'sun'])) == \
            [
                {('sky', '1732', 'SKY', 2)},
                {('sun', '1343', 'SUN', 2)},
            ]
        # there are at least four 'thins' so lets see if we get them.
        assert len(list(api.lookup(['thin'], full_search=True))[0]) >= 4


def test_check(api, capsys):
    assert not api.check()
    out, _ = capsys.readouterr()
    assert 'Duplicate ISO' in out
    assert 'link without label' in out


def test_Concepticon(api):
    assert len(api.frequencies) == 941
    assert len(api.conceptsets) == 3175


def test_ConceptRelations(api):
    from pyconcepticon.api import ConceptRelations
    rels = ConceptRelations(api.repos / 'concepticondata' / 'conceptrelations.tsv')
    assert list(rels.iter_related('1212', 'narrower'))[0][0] in ['1130', '1131']
    assert list(rels.iter_related('1212', 'hasform'))[0][0] == '2310'


def test_MultiRelations(api):
    assert api.multirelations


def test_superseded_concepts(api):
    # 282 POLE has a replacement to 281 POST
    assert api.conceptsets['283'].superseded
    assert api.conceptsets['283'].replacement == api.conceptsets['140']
