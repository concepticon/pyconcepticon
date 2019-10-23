"""
Link concepts to concept sets for a given concept list.

Notes
-----
If either CONCEPTICON_GLOSS or CONCEPTICON_ID is given in the list, the other is added.
"""
from pyconcepticon.util import rewrite, CS_GLOSS, CS_ID
from pyconcepticon.cli_util import add_conceptlist, get_conceptlist


def register(parser):
    add_conceptlist(parser)


def run(args):
    cl = get_conceptlist(args, path_only=True)
    rewrite(cl, Linker(cl.stem, args.repos.conceptsets.values()))


class Linker(object):
    def __init__(self, clid, conceptsets):
        self.clid = clid
        self.concepts = {
            CS_ID: {cs.id: cs.gloss for cs in conceptsets},
            # maps ID to GLOSS
            CS_GLOSS: {cs.gloss: cs.id for cs in conceptsets},
            # maps GLOSS to ID
        }

        self._cid_index = None
        self._cgloss_index = None
        self._link_col = (None, None)
        self._number_index = None

    def __call__(self, i, row):
        if i == 0:
            assert (CS_ID in row) or (CS_GLOSS in row)
            assert "NUMBER" in row
            if (CS_ID in row) and (CS_GLOSS in row):
                self._cid_index = row.index(CS_ID)
                self._cgloss_index = row.index(CS_GLOSS)
            else:
                # either CONCEPTICON_ID or CONCEPTICON_GLOSS is given, and the
                # other is missing.
                add = {CS_ID: CS_GLOSS, CS_GLOSS: CS_ID}
                for j, col in enumerate(row):
                    if col in add:
                        row = [add[col]] + row
                        self._link_col = (j, col)
                        break
            if "ID" not in row:
                self._number_index = row.index("NUMBER")
                row = ["ID"] + row
            return row

        if self._link_col[1]:
            val = self.concepts[self._link_col[1]].get(row[self._link_col[0]], "")
            if not val:
                print("unknown %s: %s" % (self._link_col[1], row[self._link_col[0]]))
            row = [val] + row
        else:
            cid = self.concepts[CS_GLOSS].get(row[self._cgloss_index], "")
            if not cid:
                print("unknown CONCEPTICON_GLOSS: {0}".format(row[self._cgloss_index]))
            elif cid != row[self._cid_index]:
                if not row[self._cid_index]:
                    row[self._cid_index] = cid
                else:
                    print(
                        "unknown CONCEPTICON_ID/GLOSS mismatch: %s %s"
                        % (row[self._cid_index], row[self._cgloss_index])
                    )

        if self._number_index is not None:
            row = ["%s-%s" % (self.clid, row[self._number_index])] + row
        return row
