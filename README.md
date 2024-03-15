# pyconcepticon

Tooling to access and curate [Concepticon data](https://github.com/concepticon/concepticon-data).

[![Build Status](https://github.com/concepticon/pyconcepticon/workflows/tests/badge.svg)](https://github.com/concepticon/pyconcepticon/actions?query=workflow%3Atests)
[![PyPI](https://img.shields.io/pypi/v/pyconcepticon.svg)](https://pypi.org/project/pyconcepticon)


## Installation

`pyconcepticon` can be installed from [PyPI](https://pypi.python.org/pypi) running
```shell script
pip install pyconcepticon
```

Note that `pyconcepticon` requires a clone or export of the [concepticon data repository](https://github.com/concepticon/concepticon-data).


## Usage

To use `pyconcepticon` you must have a local copy of the Concepticon data, i.e. either

* the sources of a [released version](https://github.com/concepticon/concepticon-data/releases), as provided in the **Downloads** 
  section of a release, or
* a clone of this repository (or your personal fork of it).
* or a released version of the data as archived on [ZENODO](https://doi.org/10.5281/zenodo.596412).


### Python API

Assuming you have downloaded release 1.2.0 [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.1313461.svg)](https://doi.org/10.5281/zenodo.1313461)
and unpacked the sources to a directory `clld-concepticon-data-41d2bf0`, you can access
the data as follows:
```python
>>> from pyconcepticon import Concepticon
>>> api = Concepticon('clld-concepticon-data-41d2bf0')
>>> conceptlist = list(api.conceptlists.values())[0]
>>> conceptlist.author
'Perrin, Loïc-Michel'
>>> conceptlist.tags
['annotated']
>>> len(conceptlist.concepts)
110
>>> list(conceptlist.concepts.values())[0]
Concept(
    id='Perrin-2010-110-1', number='1', concepticon_id='1906', concepticon_gloss='SOUR', gloss=None, 
    english='ACID', attributes={'german': 'sauer', 'french': 'acide'}, 
    _list=Conceptlist(
        _api=<pyconcepticon.api.Concepticon object at 0x7f31693be518>, 
        id='Perrin-2010-110', author='Perrin, Loïc-Michel', year=2010, list_suffix='', items=110, 
        tags=['annotated'], source_language=['english', 'french', 'german'], 
        target_language='Global', 
        url='https://journals.dartmouth.edu/cgi-bin/WebObjects/Journals.woa/xmlpage/1/article/353?htmlOnce=yes', 
        refs=['Perrin2010'], pdf=['Perrin2010'], 
        note='This list was used as an initial questionnaire for colexification studies on a world-wide sample of languages.', 
        pages='276f', alias=[], local=False))
```

### Command line interface

Having installed `pyconcepticon`, you can also directly query concept lists via the terminal command 
`concepticon`. To learn about the functionality it provides run
```shell script
$ concepticon -h
usage: concepticon [-h] [--log-level LOG_LEVEL] [--repos REPOS]
                   [--repos-version REPOS_VERSION]
                   COMMAND ...

optional arguments:
  -h, --help            show this help message and exit
  --log-level LOG_LEVEL
                        log level [ERROR|WARN|INFO|DEBUG] (default: 20)
  --repos REPOS         clone of concepticon/concepticon-data
  --repos-version REPOS_VERSION
                        version of repository data. Requires a git clone!
                        (default: None)

available commands:
  Run "COMAMND -h" to get help for a specific command.

  COMMAND
    attributes          Print all columns in concept lists that contain
                        surplus information.
...
```

To learn about individual subcommands run `concepticon COMMAND -h`, e.g.
```shell
$ concepticon lookup -h
usage: concepticon lookup [-h]
                          [--format {fancy_grid,fancy_outline,github,grid,html,jira,latex,latex_booktabs,latex_longtable,latex_raw,mediawiki,moinmoin,orgtbl,pipe,plain,presto,pretty,psql,rst,simple,textile,tsv,unsafehtml,youtrack}]
                          [--similarity SIMILARITY] [--full-search]
                          [--language LANGUAGE]
                          GLOSS [GLOSS ...]

Look up the specified glosses in Concepticon.

positional arguments:
  GLOSS

optional arguments:
  -h, --help            show this help message and exit
  --format {fancy_grid,fancy_outline,github,grid,html,jira,latex,latex_booktabs,latex_longtable,latex_raw,mediawiki,moinmoin,orgtbl,pipe,plain,presto,pretty,psql,rst,simple,textile,tsv,unsafehtml,youtrack}
                        Format of tabular output. (default: simple)
  --similarity SIMILARITY
                        specify level of similarity for concept mapping
                        (default: 5)
  --full-search         select between approximate search (default) and full
                        search (default: False)
  --language LANGUAGE   specify your desired language for mapping (default:
                        en)
```


## Configuration

The Python API as well as the CLI can lookup the location of the data from a
[`cldfcatalog` config file](https://github.com/cldf/cldfcatalog/#configuration), under the key `concepticon`.

Such a config file (and the repository clone) can be created automatically,
by installing [`cldfbench`](https://pypi.org/cldfbench) and running
`cldfbench config`.
