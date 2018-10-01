import platform
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

def wheel_sort_key(filename):
    return filename
