from   collections import defaultdict
import csv
import io
from   zipfile     import ZipFile
from   .metadata   import parse_metadata
from   .wheel_info import parse_wheel_info

def parse_record(fp):
    # Defined in PEP 376?
    return (
        [path for path, _, _ in csv.reader(fp, delimiter=',', quotechar='"')],
        set(),
    )

def readlines(fp):
    return fp.read().splitlines(), set()

DIST_INFO_FILES = [
    # file name, handler function, result dict key
    ('METADATA', parse_metadata, 'metadata'),
    ('WHEEL', parse_wheel_info, 'wheel'),
    ('RECORD', parse_record, 'contents'),
    ###('entry_points.txt', ???, 'entry_points'),
    ('top_level.txt', readlines, 'top_level'),
    ('namespace_packages.txt', readlines, 'namespace_packages'),
    ('dependency_links.txt', readlines, 'dependency_links'),

    ### metadata.json?
    ### pydist.json?
    ### signatures?
]

def inspect_wheel(fp):
    whl = ZipFile(fp)
    ### TODO: Verify wheel

    dist_info_folder = defaultdict(set)
    for fname in whl.namelist():
        dirname, _, basename = fname.partition('/')
        if dirname.endswidth('.dist-info') and basename:
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
        else:
            about[key] = None

    ### Compare data in WHEEL with data in filename?
    ### Reject wheels with non-PEP440 version numbers?
    ### Do something with signatures?

    return about
