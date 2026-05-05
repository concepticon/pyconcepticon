"""
Functionality to provide a Concepticon API for testing purposes.
"""
import pathlib

TEST_REPOS = pathlib.Path(__file__).parent / 'test_repos'


def get_test_api():
    """Returns a Concepticon API object to access the data in the test repos."""
    from pyconcepticon import Concepticon  # pylint: disable=C0415

    return Concepticon(TEST_REPOS)
