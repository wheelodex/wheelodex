from __future__ import annotations
from collections.abc import Iterable
from datetime import datetime
import platform
import re
from typing import Any
from packaging.version import Version
from pydantic import BaseModel
import requests
from . import __url__, __version__

#: The User-Agent header used for requests to PyPI's JSON API and when
#: downloading wheels
USER_AGENT = "wheelodex/{} ({}) requests/{} {}/{}".format(
    __version__,
    __url__,
    requests.__version__,
    platform.python_implementation(),
    platform.python_version(),
)


class JsonWheelPyPI(BaseModel):
    filename: str
    url: str
    project: str
    version: str
    size: int
    md5: str | None
    sha256: str | None
    uploaded: datetime


class JsonWheelMeta(BaseModel):
    processed: datetime
    wheel_inspect_version: str


class JsonWheel(BaseModel):
    pypi: JsonWheelPyPI
    data: Any = None
    wheelodex: JsonWheelMeta | None = None
    errored: bool = False


def latest_version(versions: Iterable[str]) -> str | None:
    """
    Returns the latest version in ``versions`` in PEP 440 order, except that
    prereleases are only returned when there are no non-prereleases in the
    input.  Returns `None` for an empty list.
    """
    # <https://github.com/python/mypy/issues/16267>
    return max(versions, key=version_sort_key, default=None)  # type: ignore[arg-type]


def version_sort_key(v: str) -> tuple[bool, Version]:
    """
    Returns a sort key for the given version string that sorts in PEP 440
    order, but with prereleases sorted less than non-prereleases
    """
    vobj = Version(v)
    return (not vobj.is_prerelease, vobj)


def like_escape(s: str) -> str:
    """
    Escape characters in ``s`` that have special meaning to SQL's ``LIKE``
    """
    return s.replace("\\", r"\\").replace("%", r"\%").replace("_", r"\_")


def glob2like(s: str) -> str:
    """Convert a file glob pattern to an equivalent SQL ``LIKE`` pattern"""

    def subber(m: re.Match[str]) -> str:
        x = m[1]
        if x == "*":
            return "%"
        elif x == "?":
            return "_"
        elif x in (r"\*", r"\?"):
            return x[-1]
        elif x in (r"\%", r"\_"):
            return r"\\" + x
        elif x == r"\\":
            return x
        else:
            return "\\" + x

    return re.sub(r"(\x5C.|[?*%_])", subber, s)
