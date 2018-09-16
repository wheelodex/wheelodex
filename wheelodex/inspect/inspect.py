from   collections   import defaultdict
import csv
import io
from   zipfile       import ZipFile
from   pkg_resources import EntryPoint, yield_lines
from   .metadata     import parse_metadata
from   .wheel_info   import parse_wheel_info

def parse_record(fp):
    # Defined in PEP 376
    return [{
        "path": path,
        "digests": dict([digests.split('=', 1)]) if digests else {},
        "size": int(size) if size else None,
    } for path, digests, size in csv.reader(fp, delimiter=',', quotechar='"')]

def parse_entry_points(fp):
    return {
        gr: sorted(eps.keys()) for gr, eps in EntryPoint.parse_map(fp).items()
    }

def readlines(fp):
    return list(yield_lines(fp)), set()

DIST_INFO_FILES = [
    # file name, handler function, result dict key
    ('METADATA', parse_metadata, 'metadata'),
    ('RECORD', parse_record, 'contents'),
    ('WHEEL', parse_wheel_info, 'wheel'),
    # <https://setuptools.readthedocs.io/en/latest/formats.html>:
    ('dependency_links.txt', readlines, 'dependency_links'),
    ('entry_points.txt', parse_entry_points, 'entry_points'),
    ('namespace_packages.txt', readlines, 'namespace_packages'),
    ('top_level.txt', readlines, 'top_level'),
    ### TODO: Do something with `zip-safe` file? (seen in python-dateutil wheel)
]

def inspect_wheel(fp):
    whl = ZipFile(fp)
    ### TODO: Verify wheel
    dist_info_folder = defaultdict(set)
    for fname in whl.namelist():
        dirname, _, basename = fname.partition('/')
        if dirname.endswith('.dist-info') and basename:
            dist_info_folder[dirname].add(basename)
    try:
        (dist_info_name, dist_info_contents), = dist_info_folder.items()
    except ValueError:
        raise ValueError('no unique *.dist-info/ directory in wheel')
    about = {"flags": set()}
    for fname, parser, key in DIST_INFO_FILES:
        if fname in dist_info_contents:
            with whl.open(dist_info_name + '/' + fname) as fp:
                about[key], flags = parser(io.TextIOWrapper(fp, 'utf-8'))
                about["flags"].update(flags)
                ### TODO: Log all flags? (Here or when set?)
        else:
            about[key] = None
    return about
