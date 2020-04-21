from   collections       import defaultdict
from   functools         import total_ordering
import platform
import re
from   flask             import Response
from   flask.json        import dumps
from   packaging.version import parse
import pyrfc3339
import requests
import requests_download
from   wheel_filename    import parse_wheel_filename
from   .                 import __url__, __version__

#: The User-Agent header used for requests to PyPI's JSON API and when
#: downloading wheels
USER_AGENT = 'wheelodex/{} ({}) requests/{} requests_download/{} {}/{}'.format(
    __version__,
    __url__,
    requests.__version__,
    requests_download.__version__,
    platform.python_implementation(),
    platform.python_version(),
)

def latest_version(versions):
    """
    Returns the latest version in ``versions`` in PEP 440 order, except that
    prereleases are only returned when there are no non-prereleases in the
    input.  Returns `None` for an empty list.
    """
    return max(versions, key=version_sort_key, default=None)

def version_sort_key(v):
    """
    Returns a sort key for the given version string that sorts in PEP 440
    order, but with prereleases sorted less than non-prereleases
    """
    v = parse(v)
    return (not v.is_prerelease, v)

def reprify(obj, fields):
    """
    Returns a string suitable as a ``__repr__`` for ``obj`` that includes the
    fields in the list ``fields``
    """
    return '{0.__module__}.{0.__name__}({1})'.format(
        type(obj),
        ', '.join('{}={!r}'.format(f, getattr(obj, f)) for f in fields),
    )

PYTHON_PREFERENCES = defaultdict(lambda: -1, {
    'py': 4,
    'cp': 3,
    'pp': 2,
    'jy': 1,
    'ip': 0,
})

ARCH_PREFERENCES = defaultdict(lambda: -1, {
    'universal': 7,
    'fat':       6,
    'intel':     5,
    'x86_64':    4,
    'i686':      3,
    'i386':      2,
    'armv7l':    1,
    'armv6l':    0,
})

@total_ordering
class VersionNoDot:
    """
    This class represents "``py_version_nodot``" strings as used in PEP 425
    Python and ABI tags.  Comparison between `VersionNoDot` objects treats
    ``'12'`` as more general than, and thus "larger" than, ``'123'``;
    comparison when one string is not a prefix of the other is lexicographic.
    """

    def __init__(self, vstr):
        components = vstr.split('_')
        if len(components) > 1:
            self.vs = tuple(int(c) for c in components)
        else:
            self.vs = tuple(int(c) for c in components[0])

    def __eq__(self, other):
        if type(self) is type(other):
            return self.vs == other.vs
        else:
            return NotImplemented

    def __le__(self, other):
        if type(self) is type(other):
            return self.vs[:len(other.vs)] == other.vs or self.vs < other.vs
        else:
            return NotImplemented

    def __repr__(self):
        if any(c >= 10 for c in self.vs):
            s = '_'.join(map(str, self.vs))
        else:
            s = ''.join(map(str, self.vs))
        return 'VersionNoDot({!r})'.format(s)


def wheel_sort_key(filename):
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
        whlname = parse_wheel_filename(filename)
    except ValueError:
        return (0, filename)

    if whlname.build is not None:
        n = re.fullmatch(r'(?P<buildno>\d+)(?P<buildstr>[^-]*)', whlname.build)
        if not n:
            return (0, filename)
        build_rank = (int(n.group('buildno')), n.group('buildstr'))
    else:
        build_rank = (-1, '')

    pyver_rank = []
    for py in whlname.python_tags:
        n = re.fullmatch(r'(\w+?)(\d[\d_]*)', py)
        if not n:
            return (0, filename)
        pyver_rank.append((
            PYTHON_PREFERENCES[n.group(1)],
            VersionNoDot(n.group(2)),
        ))
    pyver_rank.sort(reverse=True)

    ### TODO: distlib expects wheels to have only one ABI tag in their filename
    ### while wheel_inspect does not.  If the latter turns out to be the
    ### correct approach, adjust this code to handle multiple tags.
    abi = whlname.abi_tags[0]
    ### TODO: Should abi3 be given some rank?
    if abi == 'none':
        abi_rank = (1,)
    else:
        n = re.fullmatch(r'(\wp)(\d+)(\w*)', abi)
        if n:
            py_imp, py_ver, flags = n.groups()
            abi_rank = (0,PYTHON_PREFERENCES[py_imp],VersionNoDot(py_ver),flags)
        else:
            abi_rank = (0, -1, -1, '')

    platform_rank = []
    for plat in whlname.platform_tags:
        for rank, rgx in enumerate([
            r'macosx_10_(?P<version>\d+)_(?P<arch>\w+)',
            'macosx',
            'win32',
            'win64',
            'win_amd64',
            r'linux_(?P<arch>\w+)',
            r'manylinux(?P<version>\d+)_(?P<arch>\w+)',
            'any',
        ]):
            n = re.fullmatch(rgx, plat)
            if n:
                d = n.groupdict()
                version = d.get('version')
                version = int(version) if version is not None else -1
                arch = ARCH_PREFERENCES[d.get('arch')]
                platform_rank.append((rank, version, arch))
                break
        else:
            ### TODO: Don't discard
            pass
    platform_rank.sort(reverse=True)

    tiebreaker = '{}-{}-{}'.format(
        '.'.join(whlname.python_tags),
        '.'.join(whlname.abi_tags),
        '.'.join(whlname.platform_tags),
    )

    return (1, pyver_rank, platform_rank, abi_rank, tiebreaker, build_rank)

def json_response(obj, status_code=200):
    """ Like `flask.jsonify()`, but supports setting a custom status code """
    return Response(
        response = dumps(obj),
        status   = status_code,
        mimetype = 'application/json',
    )

def like_escape(s):
    """
    Escape characters in ``s`` that have special meaning to SQL's ``LIKE``
    """
    return s.replace('\\', r'\\').replace('%', r'\%').replace('_', r'\_')

def glob2like(s):
    """ Convert a file glob pattern to an equivalent SQL ``LIKE`` pattern """
    def subber(m):
        x = m.group(1)
        if x == '*':
            return '%'
        elif x == '?':
            return '_'
        elif x in (r'\*', r'\?'):
            return x[-1]
        elif x in (r'\%', r'\_'):
            return r'\\' + x
        elif x == r'\\':
            return x
        else:
            return '\\' + x
    return re.sub(r'(\x5C.|[?*%_])', subber, s)

def parse_timestamp(s):
    """ Parse an ISO 8601 timestamp, assuming anything naïve is in UTC """
    if re.fullmatch(r'\d{4}-\d\d-\d\d[T ]\d\d:\d\d:\d\d(\.\d+)?', s):
        s += 'Z'
    return pyrfc3339.parse(s)

    # Python 3.7+:
    #if s.endswith('Z'):
    #    s = s[:-1] + '+00:00'
    #dt = datetime.fromisoformat(s)
    #if dt.tzinfo is None:
    #    dt = dt.replace(tzinfo=timezone.utc)
    #return dt
