- Components:
    - system for fetching & parsing wheels and adding data to database
        - fetching wheels
        - parsing wheels
            - Use `distlib` to verify wheels' RECORDs and discard invalid
              wheels?
            - listing all files in wheels?
    - JSON REST API
        - getting data from database
        - searching
    - web interface to API's data using AJAX(?)
        - option to download an export of the database

- To support:
    - wheels (PEP 427)
    - wheel tags? (PEP 425)
    - manylinux1 tags? (PEP 513)

- Not supported:
    - releases without wheels
    - non-PEP440 version numbers
    - Wheel v1.9 (PEP 491, still in draft)
    - `metadata.json`/`pydist.json` (PEP 426, still in draft; not actually used
      by anything anyway?)
    - wheels with invalid metadata
    - wheels with non-UTF-8 metadata?
    - wheels whose filename tags don't match the tags in WHEEL?
    - large wheels

- Don't use distlib for this because:
    - Its PKG-INFO/METADATA parser discards unknown fields and
      Descriptions-as-bodies
    - Its wheel parser only exposes `metadata.json` (or `METADATA` if that
      doesn't exist) and `WHEEL`

- Related prior art:
    - <https://pydigger.com>
    - <https://github.com/takluyver/wheeldex>
    - <https://github.com/LuisAlejandro/pypicontents>
