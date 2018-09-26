import re
from   packaging.version import parse

def latest_version(versions):
    """
    Returns the latest version in ``versions`` in PEP 440 order, except that
    prereleases are only returned when there are no non-prereleases in the
    input.  Returns `None` for an empty list.
    """
    return max(versions, key=version_sort_key, default=None)

def version_sort_key(v):
    v = parse(v)
    return (not v.is_prerelease, v)

def parse_memory(s):
    """
    >>> parse_memory('42')
    42
    >>> parse_memory('42k')
    43008
    >>> parse_memory('42 MB')
    44040192
    """
    m = re.match(r'^(\d+)(?:\s*([kMGTPE])B?)?$', s)
    if not m:
        raise ValueError(s)
    x = int(m.group(1))
    if m.group(2) is not None:
        x <<= 10 * ('kMGTPE'.index(m.group(2)) + 1)
    return x

def reprify(obj, fields):
    return '{0.__module__}.{0.__name__}({1})'.format(
        type(obj),
        ', '.join('{}={!r}'.format(f, getattr(obj, f)) for f in fields),
    )
