"""
Compat with older python versions.
"""
import sys

if sys.version_info >= (3, 11):
    from enum import StrEnum
    assert StrEnum
else:
    from backports.strenum import StrEnum  # pragma: no cover
