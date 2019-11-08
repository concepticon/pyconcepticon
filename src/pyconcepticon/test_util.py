import pathlib

TEST_REPOS = pathlib.Path(__file__).parent / 'test_repos'


def get_test_api():
    from pyconcepticon import Concepticon

    return Concepticon(TEST_REPOS)
