"""
Write concepticon linking data to file.
"""
import json
import zipfile
import collections

from csvw.dsv import UnicodeDictReader


def register(parser):
    parser.add_argument(
        "--destination",
        default=None,
        help="Name of the file to store data in compressed form."
    )


def run(args):
    paths = {p.stem.split('-')[1]: p for p in args.repos.path(
        'mappings').glob('map-*.tsv')}
    translate = {
        'Person/Thing': 'noun',
        'Other': 'other',
        'Number': 'numeral',
        'Action/Process': 'verb',
        'Property': 'adjective',
        'Classifier': 'classifier'
    }
    mappings = {}
    for language, path in paths.items():
        mappings[language] = collections.defaultdict(set)
        with UnicodeDictReader(path, delimiter='\t') as reader:
            for line in reader:
                gloss = line['GLOSS'].split('///')[1]
                oc = translate.get(
                    args.repos.conceptsets[line['ID']].ontological_category,
                    'other')
                cgl = args.repos.conceptsets[line['ID']].gloss
                mappings[language][gloss].add(
                    (line['ID'], cgl, int(line['PRIORITY']), oc, 1))
            for gloss in list(mappings[language].keys()):
                if gloss.lower() not in mappings[language]:
                    mappings[language][gloss.lower()] = set([
                        (x[0], x[1], x[2], x[3], 0) for x in
                        mappings[language][gloss]])

    for language, path in paths.items():
        for k, v in mappings[language].items():
            mappings[language][k] = sorted(v, key=lambda x: x[1], reverse=True)

    with zipfile.ZipFile(
        args.destination,
        mode='w',
        compression=zipfile.ZIP_DEFLATED
    ) as myzip:
        myzip.writestr('concepticon.json', json.dumps(mappings))
