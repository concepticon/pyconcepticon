"""
Print a full bibliographic citation for a Concepticon version
"""
import html
import collections
from datetime import date

from clldutils.path import git_describe
from clldutils.jsonlib import dump
from nameparser import HumanName


def register(parser):
    parser.add_argument('--version', default=None)
    parser.add_argument('--year', default=date.today().year, type=int)


def zenodo_json(citation, version, editors):
    return collections.OrderedDict([
        ("upload_type", "dataset"),
        ("description", "<p>{}</p>".format(html.escape(citation))),
        ("alternate_identifiers",
         [{"scheme": "url", "identifier": "https://concepticon.clld.org"}]),
        ("title", "CLLD Concepticon {}".format(version.replace('v', ''))),
        ("access_right", "open"),
        ("license", {"id": "CC-BY-4.0"}),
        ("keywords", ["linguistics"]),
        ("creators", [{"name": e.name} for e in editors]),
        ("communities", [{"identifier": "calc"}, {"identifier": "clld"}, {"identifier": "dighl"}])
    ])


def run(args):
    if not args.version:  # pragma: no cover
        args.version = git_describe(args.repos.repos)
        if args.version.startswith('v'):
            args.version = args.version[1:]
    current_editors = [
        e for e in args.repos.editors
        if (not e.end) and int(e.start) <= args.year]
    editor_names = []
    for e in current_editors:
        name = HumanName(e.name)
        editor_names.append('{0.last}, {0.first} {0.middle}'.format(name).strip())
    editor_names = ' & '.join(editor_names)
    res = "{0} (eds.) {1.year}. {2.title} {1.version}. {2.description}. "\
        "{2.publisher.place}: {2.publisher.name}. Available online at {2.url}".format(
            editor_names, args, args.repos.dataset_metadata,
        )
    print(res)
    dump(
        zenodo_json(res, args.version, current_editors),
        args.repos.repos / '.zenodo.json',
        indent=4)
