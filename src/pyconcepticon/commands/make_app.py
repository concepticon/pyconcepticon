"""
Dumps Concepticon's contents for English, German, Chinese, and French.

Notes
-----
Data are by default dumped into a structured JSON file in html/data.js.
"""
import json
import argparse
import collections

from pyconcepticon import Concepticon


def register(parser):  # pylint: disable=C0116
    parser.add_argument('--recreate', default=True, help=argparse.SUPPRESS)


@Concepticon.app_wrapper
def run(args):  # pylint: disable=C0116
    data = collections.defaultdict(list)

    def key(g, l_):
        return f"{g}---{l_}"

    for lang in ["en", "de", "zh", "fr", "ru", "es", "pt"]:
        for cidx, gloss in args.api._get_map_for_language(lang):  # pylint: disable=W0212
            g0, _, g1 = gloss.partition("///")
            csspec = (
                cidx,
                args.api.conceptsets[cidx].gloss,
                args.api.conceptsets[cidx].definition,
                args.api.conceptsets[cidx].ontological_category,
            )
            data[key(g1, lang)].append(csspec)
            if lang == "en":
                data[key(g0, lang)].append(csspec)
                data[key(g0.lower(), lang)].append(csspec)
    data["language"] = "en"
    args.api.appdatadir.joinpath("data.js").write_text(
        f"var Concepticon = {json.dumps(data, indent=2)};\n", encoding='utf-8')
    args.log.info("app data recreated")
