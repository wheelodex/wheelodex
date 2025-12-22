from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
from enum import IntEnum
from functools import total_ordering
import re
from typing import Any, ClassVar
from wheel_filename import WheelFilename

PYTHON_PREFERENCES = defaultdict(
    lambda: -1,
    {
        "py": 4,
        "cp": 3,
        "pp": 2,
        "jy": 1,
        "ip": 0,
    },
)

ARCH_PREFERENCES = defaultdict(
    lambda: -1,
    {
        "universal": 7,
        "fat": 6,
        "intel": 5,
        "x86_64": 4,
        "i686": 3,
        "i386": 2,
        "armv7l": 1,
        "armv6l": 0,
    },
)


@total_ordering
class VersionNoDot:
    """
    This class represents "``py_version_nodot``" strings as used in PEP 425
    Python and ABI tags.  Comparison between `VersionNoDot` objects treats
    ``'12'`` as more general than, and thus "larger" than, ``'123'``;
    comparison when one string is not a prefix of the other is lexicographic.
    """

    def __init__(self, vstr: str) -> None:
        components = vstr.split("_")
        if len(components) > 1:
            self.vs = tuple(int(c) for c in components)
        else:
            self.vs = tuple(int(c) for c in components[0])

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, VersionNoDot):
            return self.vs == other.vs
        else:
            return NotImplemented

    def __le__(self, other: VersionNoDot) -> bool:
        return self.vs[: len(other.vs)] == other.vs or self.vs < other.vs

    def __repr__(self) -> str:
        if any(c >= 10 for c in self.vs):
            s = "_".join(map(str, self.vs))
        else:
            s = "".join(map(str, self.vs))
        return f"VersionNoDot({s!r})"


@total_ordering
@dataclass
class WheelSortKey:
    filename: str | None
    data: ParsedKey | None

    def __le__(self, other: WheelSortKey) -> bool:
        if self.filename is not None:
            if other.filename is not None:
                return self.filename <= other.filename
            else:
                return True
        else:
            assert self.data is not None
            if other.filename is not None:
                return False
            else:
                assert other.data is not None
                return self.data <= other.data

    @classmethod
    def unparseable(cls, filename: str) -> WheelSortKey:
        return WheelSortKey(filename=filename, data=None)

    @classmethod
    def parsed(cls, data: ParsedKey) -> WheelSortKey:
        return WheelSortKey(filename=None, data=data)


@dataclass(order=True)
class ParsedKey:
    pyver_rank: list[tuple[int, VersionNoDot]]
    platform_rank: list[tuple[int, int, int]]
    abi_rank: AbiRank
    tiebreaker: str
    build_rank: tuple[int, str]


class AbiRankKind(IntEnum):
    UNPARSEABLE = -1
    BINARY = 0
    NONE = 1


@total_ordering
@dataclass
class AbiRank:
    UNPARSEABLE: ClassVar[AbiRank]
    NONE: ClassVar[AbiRank]
    kind: AbiRankKind
    data: tuple[int, VersionNoDot, str] | None

    def __le__(self, other: AbiRank) -> bool:
        if self.kind < other.kind:
            return True
        elif self.kind == other.kind:
            if self.kind is AbiRankKind.BINARY:
                assert self.data is not None
                assert other.data is not None
                return self.data <= other.data
            else:
                return True
        else:
            return False

    @classmethod
    def binary(cls, data: tuple[int, VersionNoDot, str]) -> AbiRank:
        return cls(kind=AbiRankKind.BINARY, data=data)


AbiRank.UNPARSEABLE = AbiRank(kind=AbiRankKind.UNPARSEABLE, data=None)
AbiRank.NONE = AbiRank(kind=AbiRankKind.NONE, data=None)


def wheel_sort_key(filename: str) -> WheelSortKey:
    """
    Returns a sort key for the given wheel filename that will be used to select
    the "preferred" or "default" wheel to display for a given project &
    version.

    General rules:

    - It is assumed that only wheels for the same version of the same project
      are ever compared, and so those parts of the filename are ignored.

    - Prefer more general wheels (e.g., pure Python) to more specific (e.g.,
      platform specific).

        - Prefer compability with more versions to fewer.
        - "any" is the most preferred platform.
        - "none" is the most preferred ABI.

    - Prefer compability with higher versions to lower.

    - Unrecognized values are ignored if possible, otherwise sorted at the
      bottom.

    Specific, arbitrary preferences:

    - Sort by Python tag first, then platform tag, then ABI tag, then
      "pyver-abi-platform" string (as a tiebreaker), then build tag.

    - Filenames that can't be parsed sort the lowest and sort relative to each
      other based on filename.

    - Python implementations: py (generic) > cp (CPython) > pp (PyPy) > jy
      (Jython) > ip (IronPython) > everything else

    - Platforms: any > manylinux > Linux > Windows > Mac OS X > everything else
    """

    try:
        whlname = WheelFilename.parse(filename)
    except ValueError:
        return WheelSortKey.unparseable(filename)

    build_rank = whlname.build_tuple or (-1, "")

    pyver_rank: list[tuple[int, VersionNoDot]] = []
    for py in whlname.python_tags:
        if m := re.fullmatch(r"(\w+?)(\d[\d_]*)", py):
            pyver_rank.append((PYTHON_PREFERENCES[m[1]], VersionNoDot(m[2])))
        else:
            return WheelSortKey.unparseable(filename)
    pyver_rank.sort(reverse=True)

    ### TODO: distlib expects wheels to have only one ABI tag in their filename
    ### while wheel_inspect does not.  If the latter turns out to be the
    ### correct approach, adjust this code to handle multiple tags.
    abi = whlname.abi_tags[0]
    ### TODO: Should abi3 be given some rank?
    if abi == "none":
        abi_rank = AbiRank.NONE
    elif m := re.fullmatch(r"(\wp)(\d+)(\w*)", abi):
        py_imp, py_ver, flags = m.groups()
        abi_rank = AbiRank.binary(
            (PYTHON_PREFERENCES[py_imp], VersionNoDot(py_ver), flags)
        )
    else:
        abi_rank = AbiRank.UNPARSEABLE

    platform_rank: list[tuple[int, int, int]] = []
    for plat in whlname.platform_tags:
        for rank, rgx in enumerate(
            [
                r"macosx_10_(?P<version>\d+)_(?P<arch>\w+)",
                "macosx",
                "win32",
                "win64",
                "win_amd64",
                r"linux_(?P<arch>\w+)",
                r"manylinux(?P<version>\d+)_(?P<arch>\w+)",
                "any",
            ]
        ):
            if m := re.fullmatch(rgx, plat):
                d = m.groupdict()
                if "version" in d:
                    version = int(d["version"])
                    arch = ARCH_PREFERENCES[d["arch"]]
                else:
                    version = -1
                    arch = -1
                platform_rank.append((rank, version, arch))
                break
        else:
            ### TODO: Don't discard
            pass
    platform_rank.sort(reverse=True)

    tiebreaker = "{}-{}-{}".format(
        ".".join(whlname.python_tags),
        ".".join(whlname.abi_tags),
        ".".join(whlname.platform_tags),
    )

    return WheelSortKey.parsed(
        ParsedKey(
            pyver_rank=pyver_rank,
            platform_rank=platform_rank,
            abi_rank=abi_rank,
            tiebreaker=tiebreaker,
            build_rank=build_rank,
        )
    )
