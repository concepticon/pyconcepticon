"""
test
"""
import pathlib

d = pathlib.Path(__file__).resolve().parent
t = d.parent.joinpath(f'{d.name}.tsv').read_text(encoding='utf8')
t = t.replace(
    '[{"ID":"Sun-1991-1004-83","DEGREE":7}]', '[{"ID":"Sun-1991-1004-87","DEGREE":7}]')
d.joinpath(f'{d.name}.tsv').write_text(t, encoding='utf8')
