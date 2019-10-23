"""
Create metadata files for all conceptlists.
"""
from csvw import Column


def run(args):
    for cl in args.repos.conceptlists.values():
        mdpath = cl.path.parent.joinpath(cl.path.name + '-metadata.json')
        if not mdpath.exists():
            cols_in_md = []
            for col in cl.metadata.tableSchema.columns:
                cnames = []  # all names or aliases csvw will recognize for this column
                cnames.append(col.name)
                if col.titles:
                    c = col.titles.getfirst()
                    cnames.append(c)
                cols_in_md.extend(cnames)

            for col in cl.cols_in_list:
                if col not in cols_in_md:
                    cl.metadata.tableSchema.columns.append(
                        Column.fromvalue(dict(name=col, datatype='string')))

            cl.tg.to_file(mdpath)
