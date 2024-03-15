"""
Recreate the concept lists containing network data.
"""
import json
import shutil
import subprocess

from csvw.dsv import reader

from pyconcepticon.models import CONCEPT_NETWORK_COLUMNS


def register(parser):
    parser.add_argument(
        '--download',
        action='store_true',
        default=False,
        help="Also run download script if available")
    parser.add_argument(
        '--diff',
        action='store_true',
        default=False,
        help="Do not overwrite lists, but compute diff")


def idname(t):
    d = dict(t)
    rem = '\t'.join('{}: {}'.format(k, v) for k, v in t if k not in ['ID', 'NAME'])
    return '{}\t{}\t{}'.format(d['ID'], d.get('NAME', ''), rem)


def hashable_dict(d):
    return tuple(sorted([(k, tuple(v) if isinstance(v, list) else v) for k, v in d.items()]))


def diff(new, old):
    old = {r['ID']: r for r in reader(old, dicts=True, delimiter='\t')}
    new = {r['ID']: r for r in reader(new, dicts=True, delimiter='\t')}

    for k, i1 in old.items():
        i2 = new[k]
        for col in CONCEPT_NETWORK_COLUMNS:
            if col in i1:
                v1 = set(hashable_dict(i) for i in json.loads(i1[col] or '[]'))
                v2 = set(hashable_dict(i) for i in json.loads(i2[col] or '[]'))
                if v1 != v2:
                    print('== {}\t{}'.format(k, col))
                    for ii in v1:
                        if ii not in v2:
                            print('-- {}'.format(idname(ii)))
                    for ii in v2:
                        if ii not in v1:
                            print('++ {}'.format(idname(ii)))


def run(args):
    for cl in args.repos.conceptlists.values():
        d = cl.path.parent / cl.path.stem
        if d.exists() and d.is_dir():
            print(d)
            if d.joinpath('download.py').exists() and args.download:  # pragma: no cover
                subprocess.check_call(['python', 'download.py'], cwd=d)
            subprocess.check_call(['python', 'convert.py'], cwd=d)
            if args.diff and cl.path.exists():
                diff(d / cl.path.name, cl.path)
            else:
                shutil.move(d / cl.path.name, cl.path)
