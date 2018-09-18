import re
from   packaging.version import parse

def latest_version(versions):
    candidates = [(parse(rel), rel) for rel in versions]
        # The unparsed version string needs to be kept around because the
        # alternative approach (stringifying the Version object once
        # comparisons are done) can result in a different string (e.g.,
        # "2001.01.01" becomes "2001.1.1"), leading to a 404.
    candidates = filter(lambda v: not v[0].is_prerelease, candidates)
    return max(candidates, default=[None, None])[1]

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
