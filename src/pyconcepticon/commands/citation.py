"""
Print a full bibliographic citation for a Concepticon version
"""
import html
import collections
from datetime import date

from clldutils.path import git_describe
from clldutils.jsonlib import dump
from nameparser import HumanName


def register(parser):  # pylint: disable=C0116
    parser.add_argument('--version', default=None)
    parser.add_argument('--year', default=date.today().year, type=int)


def zenodo_json(citation, version, editors):  # pylint: disable=C0116
    return collections.OrderedDict([
        ("upload_type", "dataset"),
        ("description", f"<p>{html.escape(citation)}</p>"),
        ("alternate_identifiers",
         [{"scheme": "url", "identifier": "https://concepticon.clld.org"}]),
        ("title", f"CLLD Concepticon {version.replace('v', '')}"),
        ("access_right", "open"),
        ("license", {"id": "CC-BY-4.0"}),
        ("keywords", ["linguistics"]),
        ("creators", [{"name": e.name} for e in editors]),
        ("communities", [{"identifier": "calc"}, {"identifier": "clld"}, {"identifier": "dighl"}])
    ])


def run(args):  # pylint: disable=C0116
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
        editor_names.append(f'{name.last}, {name.first} {name.middle}'.strip())
    editor_names = ' & '.join(editor_names)
    md = args.repos.dataset_metadata
    res = (f"{editor_names} (eds.) {args.year}. {md.title} {args.version}. {md.description}. "
           f"{md.publisher.place}: {md.publisher.name}. Available online at {md.url}")
    print(res)
    dump(
        zenodo_json(res, args.version, current_editors),
        args.repos.repos / '.zenodo.json',
        indent=4)
