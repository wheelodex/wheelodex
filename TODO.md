Architecture
------------
- getting configuration from config file
- fetching & parsing wheels and adding data to database
    - fetching wheels
        - fetching all wheels uploaded to PyPI since some point in the past
            - initial fetch
        - fetching all wheels for a given project and all recursive
          dependencies
        - fetching all wheels from PyPI
    - parsing wheels
        - Use `distlib` to verify wheels' RECORDs and discard invalid wheels?
        - `METADATA`
        - `WHEEL`
            - tags? (PEP 425 and PEP 513)
        - `RECORD` / list of files?
        - entry points
        - `top_level.txt`
        - `namespace_packages.txt`
        - other namespace packages?
        - dependency links
        - `metadata.json` / `pydist.json` ???
        - signatures?
    - Reject wheels with non-PEP440 version numbers?
    - storing in database
- JSON REST API
    - getting data from database
    - searching
- web interface to API's data using AJAX(?)
    - provide a download of a database export rebuilt daily
    - Items displayed on the page for a given wheel:
        - metadata
            - links to dependencies
        - links to reverse dependencies (specifically, those projects whose
          highest-numbered non-prerelease versions depend upon some version of
          the project to which the wheel belongs, regardless of platform etc.
          compatibility)

`METADATA` Parser
-----------------
- PEP 345 says that Classifiers and Requires-Python fields can have markers;
  assuming anyone's ever used this feature, support it
- Obsoletes-Dist, Provides-Dist, Provides-Extra, and Requires-External are
  technically structured, but the payoff from parsing them isn't worth the
  work.  Do it anyway.
- Support `Description-Content-Type` (same syntax as a regular `Content-Type`
  field)
- Convert markers to a `dict` representation (This will require `packaging` to
  first expose markers' structured information)
