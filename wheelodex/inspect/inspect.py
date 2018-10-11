from   cgi                 import parse_header
from   collections         import defaultdict
import csv
import hashlib
import io
import os.path
from   zipfile             import ZipFile
from   distlib.wheel       import Wheel
from   pkg_resources       import EntryPoint, yield_lines
from   readme_renderer.rst import render
from   .metadata           import parse_metadata
from   .util               import extract_modules, split_keywords, \
                                    unique_projects
from   .wheel_info         import parse_wheel_info

DIGEST_CHUNK_SIZE = 65535

def parse_record(fp):
    # Defined in PEP 376
    return [{
        "path": path,
        "digests": dict([digests.split('=', 1)]) if digests else {},
        "size": int(size) if size else None,
    } for path, digests, size in csv.reader(fp, delimiter=',', quotechar='"')]

def parse_entry_points(fp):
    return {
        gr: {
            k: {
                "module": e.module_name,
                "attr": '.'.join(e.attrs) if e.attrs else None,
                "extras": list(e.extras),
            } for k,e in eps.items()
        } for gr, eps in EntryPoint.parse_map(fp).items()
    }

def readlines(fp):
    return list(yield_lines(fp))

DIST_INFO_FILES = [
    # file name, handler function, result dict key
    ('METADATA', parse_metadata, 'metadata'),
    ('RECORD', parse_record, 'record'),
    ('WHEEL', parse_wheel_info, 'wheel'),
    # <https://setuptools.readthedocs.io/en/latest/formats.html>:
    ('dependency_links.txt', readlines, 'dependency_links'),
    ('entry_points.txt', parse_entry_points, 'entry_points'),
    ('namespace_packages.txt', readlines, 'namespace_packages'),
    ('top_level.txt', readlines, 'top_level'),
]

def inspect_wheel(fname):
    whl = Wheel(fname)
    about = {
        "filename": os.path.basename(fname),
        "project": whl.name,
        "version": whl.version,
        "buildver": whl.buildver,
        "pyver": whl.pyver,
        "abi": whl.abi,
        "arch": whl.arch,
    }
    try:
        whl.verify()
    except Exception as e:
        about["valid"] = False
        about["validation_error"] = {
            "type": type(e).__name__,
            "str": str(e),
        }
    else:
        about["valid"] = True

    about["file"] = {"size": os.path.getsize(fname)}
    digests = {
        "md5": hashlib.md5(),
        "sha256": hashlib.sha256(),
    }
    with open(fname, 'rb') as fp:
        for chunk in iter(lambda: fp.read(DIGEST_CHUNK_SIZE), b''):
            for d in digests.values():
                d.update(chunk)
    about["file"]["digests"] = {k: v.hexdigest() for k,v in digests.items()}

    about["dist_info"] = {}
    whlzip = ZipFile(fname)
    dist_info_folder = defaultdict(set)
    for fname in whlzip.namelist():
        dirname, _, basename = fname.partition('/')
        if dirname.endswith('.dist-info') and basename:
            dist_info_folder[dirname].add(basename)
    try:
        (dist_info_name, dist_info_contents), = dist_info_folder.items()
    except ValueError:
        raise ValueError('no unique *.dist-info/ directory in wheel')
    for fname, parser, key in DIST_INFO_FILES:
        if fname in dist_info_contents:
            with whlzip.open(dist_info_name + '/' + fname) as fp:
                about["dist_info"][key] = parser(io.TextIOWrapper(fp, 'utf-8'))
    if 'zip-safe' in dist_info_contents:
        about["dist_info"]["zip_safe"] = True
    elif 'not-zip-safe' in dist_info_contents:
        about["dist_info"]["zip_safe"] = False

    md = about["dist_info"].get("metadata", {})
    about["derived"] = {
        "description_in_body": "BODY" in md,
        "description_in_headers": "description" in md,
    }

    if "BODY" in md and "description" not in md:
        md["description"] = md["BODY"]
    md.pop("BODY", None)
    readme = md.get("description")
    if readme is not None:
        md["description"] = {"length": len(md["description"])}
        dct = md.get("description_content_type")
        if dct is None or parse_header(dct)[0] == 'text/x-rst':
            about["derived"]["readme_renders"] = render(readme) is not None
        else:
            about["derived"]["readme_renders"] = True
    else:
        about["derived"]["readme_renders"] = None

    if md.get("keywords") is not None:
        about["derived"]["keywords"], about["derived"]["keyword_separator"] \
            = split_keywords(md["keywords"])
    else:
        about["derived"]["keywords"], about["derived"]["keyword_separator"] \
            = [], None

    about["derived"]["dependencies"] = sorted(unique_projects(
        req["name"] for req in md.get("requires_dist", [])
    ))

    about["derived"]["modules"] = extract_modules([
        rec["path"] for rec in about["dist_info"].get("record", [])
    ])

    return about
