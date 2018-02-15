- Expand README
- Write a JSON Schema for the API's representation of wheels
- Add logging
- Set a custom User-Agent when interacting with PyPI
- Update for PEP 566 (especially the JSONification section)

Architecture
------------
- getting configuration from config file
- fetching & parsing wheels and adding data to database
    - fetching wheels
        - fetching all wheels uploaded to PyPI since some point in the past
            - initial fetch
        - fetching all wheels for a given project and optionally all of its
          recursive dependencies
        - fetching all wheels from PyPI
        - entry points for performing all of the above and storing the parsed
          wheel data in the database (with an option for whether or not to
          refetch & update wheels already in the database) and/or outputting
          said data as JSON
    - parsing wheels
        - Use `distlib` to verify wheels' RECORDs and discard invalid wheels
        - Compare data in `*.dist-info/` with data in filename?
        - Record file hashes & sizes in RECORD?
        - Record extras upon which individual entry points depend
        - determine namespace packages other than those listed in
          `namespace_packages.txt`?
            - cf. <https://github.com/takluyver/wheeldex>?
        - Do something with `metadata.json` and `pydist.json`?
        - Do something with wheel signatures?
    - Reject wheels with non-PEP440 version numbers?
    - storing in database
        - replacing pre-existing database entries
        - updating reverse dependencies?
        - updating latest version of a project?
- JSON REST API
    - getting data from database
    - searching
- web interface to API's data using AJAX(?)
    - provide a download of a database export rebuilt daily
    - Items displayed on the page for a given wheel:
        - metadata
            - links to dependencies
            - list of extras with their dependencies listed under them
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
  work.  Do it anyway (eventually).
- Support `Description-Content-Type` (same syntax as a regular `Content-Type`
  field)
- Convert markers to a `dict` representation (This will require `packaging` to
  first expose markers' structured information)
    - One this is done, extras' dependencies can be split out from
      `Requires-Dist`
