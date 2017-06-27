import io
import json
import sys
from   zipfile   import ZipFile
from   .metadata import parse_metadata

def unzip_text(zpf, fname):
    return io.TextIOWrapper(zpf.open(fname), 'utf-8')

def inspect_wheel(fp):
    whl = ZipFile(fp)
    ### Verify

    #try:
    dist_info, = set(
        filter(
            lambda s: s.endswith('.dist-info'),
            (fname.split('/')[0] for fname in whl.namelist()),
        )
    )
    #except ValueError:
    #    ### Custom error message?

    metadata, flags = parse_metadata(unzip_text(whl, dist_info + '/METADATA'))
    return metadata

    ### WHEEL
    ### tags
    ### Compare data in WHEEL with data in filename
    ### Reject wheels with non-PEP440 version numbers?

    ### RECORD
    ### entry_points.txt
    ### `top_level.txt`
    ### `namespace_packages.txt`
    ### dependency links
    ### `metadata.json` / `pydist.json` ???
    ### signatures?

    ### return JSON object (with flags merged in)

def main():
    for wheelfile in sys.argv[1:]:
        with open(wheelfile, 'rb') as fp:
            about = inspect_wheel(fp)
            print(json.dumps(about, sort_keys=True, indent=4))

if __name__ == '__main__':
    main()
