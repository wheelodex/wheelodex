- Expand README
- Write a JSON Schema for the API's representation of wheels
- Add logging
- Set a custom User-Agent when interacting with PyPI
- Add tests
- Support PEP 561?  [Is this a typo for PEP 566?]
- Parse `Description-Content-Type` into a structured `dict`?
- Parse `Requires-Dist` and similar fields into structured `dict`s?
- Should flat modules inside packages be discarded from `.derived.modules`?
- Compare `extract_modules()` with <https://github.com/takluyver/wheeldex>
- Does `extract_modules()` need to take compiled library files into account?
- `config.ini`: Either use the `long_descriptions` and `[pypi.urls]` options or
  get rid of them
- Replace the wheel queue with a table of *all* wheels in PyPI, with a flag
  column added for whether to download them?

Architecture
------------
- getting configuration from config file
- fetching & parsing wheels and adding data to database
    - fetching wheels
        - fetching all wheels uploaded to PyPI since some point in the past
        - initial fetch / fetching all wheels from PyPI
        - entry points for performing all of the above and storing the parsed
          wheel data in the database (with an option for whether or not to
          refetch & update wheels already in the database) and/or outputting
          said data as JSON
    - parsing wheels
        - Record extras upon which individual entry points depend
        - determine namespace packages other than those listed in
          `namespace_packages.txt`?
            - cf. <https://github.com/takluyver/wheeldex>?
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
        - list of files in the wheel
        - list of commands and other entry points defined by the wheel
    - pages listing all defined entry points and all projects that define each
      entry point
        - Where possible, include a description of each entry point, including
          what project consumes it
    - page for searching for wheels that contain a given module
    - page for searching for wheels that contain a given file
    - pages of various statistics:
        - wheel generators
        - keywords
        - Project URL labels
        - description content types?
        - license files?
        - metadata versions?
        - "Platform" values
