from   collections       import defaultdict
from   functools         import total_ordering
import platform
import re
from   flask             import Response
from   flask.json        import dumps
from   packaging.version import parse
import requests
import requests_download
from   .                 import __url__, __version__

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
    v = parse(v)
    return (not v.is_prerelease, v)

def reprify(obj, fields):
    return '{0.__module__}.{0.__name__}({1})'.format(
        type(obj),
        ', '.join('{}={!r}'.format(f, getattr(obj, f)) for f in fields),
    )

# Based on distlib.wheel.FILENAME_RE:
WHEEL_RGX = re.compile(r'''
    [^-]+
    -[^-]+
    (?:-(?P<buildno>\d+)(?P<buildstr>[^-]*))?
    -(?P<python>\w+\d+(?:\.\w+\d+)*)
    -(?P<abi>\w+)
    -(?P<platform>\w+(?:\.\w+)*)
    \.whl
''', re.X)

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
    def __init__(self, vstr):
        self.vstr = vstr

    def __eq__(self, other):
        if type(self) is type(other):
            return self.vstr == other.vstr
        else:
            return NotImplemented

    def __le__(self, other):
        if type(self) is type(other):
            return self.vstr.startswith(other.vstr) or self.vstr < other.vstr
        else:
            return NotImplemented

    def __repr__(self):
        return 'VersionNoDot({!r})'.format(self.vstr)


def wheel_sort_key(filename):
    """
    Returns a sort key for the given wheel filename that will be used to select
    the "preferred" or "default" wheel to display for a given project &
    version.

    General rules:

    - It is assumed that only wheels for the same version of the same project
      are ever compared, and so those parts of the filename are ignored.

    - Prefer more general wheels (e.g., pure Python) to more specific (e.g.,
      platform specific)

        - Prefer compability with more versions to fewer
        - "any" is the most preferred platform.
        - "none" is the most preferred ABI.

    - Prefer compability with higher versions to lower

    - Unrecognized values are ignored if possible, otherwise sorted at the
      bottom

    Specific, arbitrary preferences:

    - Sort by Python tag first, then platform tag, then ABI tag, then
      "pyver-abi-platform" string (as a tiebreaker), then build tag

    - Filenames that can't be parsed sort the lowest and sort relative to each
      other based on filename

    - Python implementations: py (generic) > cp (CPython) > pp (PyPy) > jy
      (Jython) > ip (IronPython) > everything else

    - Platforms: any > manylinux > Linux > Windows > Mac OS X > everything else
    """

    m = WHEEL_RGX.fullmatch(filename)
    if not m:
        return (0, filename)

    if m.group('buildno') is not None:
        build_rank = (int(m.group('buildno')), m.group('buildstr'))
    else:
        build_rank = (-1, '')

    pyver_rank = []
    for py in m.group('python').split('.'):
        n = re.fullmatch(r'(\w+?)(\d+)', py)
        assert n
        pyver_rank.append((
            PYTHON_PREFERENCES[n.group(1)],
            VersionNoDot(n.group(2)),
        ))
    pyver_rank.sort(reverse=True)

    abi = m.group('abi')
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
    for plat in m.group('platform').split('.'):
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
        m.group('python'), m.group('abi'), m.group('platform'),
    )

    return (1, pyver_rank, platform_rank, abi_rank, tiebreaker, build_rank)

def json_response(obj, status_code=200):
    return Response(
        response = dumps(obj),
        status   = status_code,
        mimetype = 'application/json',
    )
