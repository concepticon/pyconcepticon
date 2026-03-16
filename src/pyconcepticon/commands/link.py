"""
Link concepts to concept sets for a given concept list.

Notes
-----
If either CONCEPTICON_GLOSS or CONCEPTICON_ID is given in the list, the other is added.
"""
import dataclasses
from typing import Optional, get_args, Literal
from collections.abc import Iterable

from pyconcepticon.models import Conceptset
from pyconcepticon.util import rewrite
from pyconcepticon.cli_util import add_conceptlist, get_conceptlist

LinkColType = Literal['CONCEPTICON_ID', 'CONCEPTICON_GLOSS']
CS_ID = get_args(LinkColType)[0]
CS_GLOSS = get_args(LinkColType)[1]
RowType = list[str]


def register(parser):  # pylint: disable=C0116
    add_conceptlist(parser)


def run(args):  # pylint: disable=C0116
    cl = get_conceptlist(args, path_only=True)
    rewrite(cl, Linker(cl.stem, args.repos.conceptsets.values()))


@dataclasses.dataclass(frozen=True)
class LinkCol:
    """Index and name of a column that links to a concepticon conceptset."""
    index: int
    col: LinkColType


@dataclasses.dataclass
class ColIndex:
    """Bag to store indices of certain columns in the rows of a conceptlist."""
    cid: Optional[int] = None
    cgloss: Optional[int] = None
    number: Optional[int] = None


class Linker:  # pylint: disable=R0903
    """Implements the rewriting of the conceptlist rows."""
    def __init__(self, clid: str, conceptsets: Iterable[Conceptset]):
        self.clid: str = clid
        self.concepts: dict[LinkColType, dict[str, str]] = {
            CS_ID: {cs.id: cs.gloss for cs in conceptsets},
            # maps ID to GLOSS
            CS_GLOSS: {cs.gloss: cs.id for cs in conceptsets},
            # maps GLOSS to ID
        }
        self.col_index: ColIndex = ColIndex()
        self.link_col: Optional[LinkCol] = None

    def _header_row(self, row: RowType) -> RowType:
        assert any(col in row for col in get_args(LinkColType))
        assert "NUMBER" in row
        if all(col in row for col in get_args(LinkColType)):
            self.col_index.cid = row.index(CS_ID)
            self.col_index.cgloss = row.index(CS_GLOSS)
        else:
            # either CONCEPTICON_ID or CONCEPTICON_GLOSS is given, and the other is missing.
            add = {CS_ID: CS_GLOSS, CS_GLOSS: CS_ID}
            for j, col in enumerate(row):
                if col in add:
                    col: LinkColType
                    row = [add[col]] + row
                    self.link_col = LinkCol(j, col)
                    break
        if "ID" not in row:
            self.col_index.number = row.index("NUMBER")
            row = ["ID"] + row
        return row

    def __call__(self, i: int, row: RowType) -> RowType:
        if i == 0:
            return self._header_row(row)

        if self.link_col:
            val = self.concepts[self.link_col.col].get(row[self.link_col.index], "")
            if not val:  # pragma: no cover
                print(f"unknown {self.link_col}")
            row = [val] + row
        else:
            cid = self.concepts[CS_GLOSS].get(row[self.col_index.cgloss], "")
            if not cid:
                print(f"unknown CONCEPTICON_GLOSS: {row[self.col_index.cgloss]}")
            elif cid != row[self.col_index.cid]:
                if not row[self.col_index.cid]:
                    row[self.col_index.cid] = cid
                else:
                    print(f"unknown CONCEPTICON_ID/GLOSS mismatch: "
                          f"{row[self.col_index.cid]} {row[self.col_index.cgloss]}")

        if self.col_index.number is not None:
            row = [f"{self.clid}-{row[self.col_index.number]}"] + row
        return row
