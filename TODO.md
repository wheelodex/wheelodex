- `config.ini`: Either use the `long_descriptions` and `[pypi.urls]` options or
  get rid of them
    - Give `inspect_wheel()` an option for whether to keep long descriptions?
- Add docstrings
    - Add `help` strings to commands & their options
- Add a column to `WheelData` for storing the revision of
  `wheel-data.schema.json` that `raw_data` conforms to?
    - Alternatively, store the revision of the wheel inspection code used?
        - Split `wheelodex.inspect` into a separate project? (and move
          `wheel-data.schema.json` into it)
- Upgrade `wheel-data.schema.json` to a more recent JSON Schema draft
- `iterqueue()`: Only return wheels for the latest version of each project
- Give `process_queue` (the function and the command) options for limiting the
  number and/or total size of wheels to process
- Replace `WheelData.update_structure()` with Alembic

- Commands:
    - Give `load` an option for overwriting any `WheelData` that's already in
      the database?  (This would require first fixing `add_wheel_data()`; see
      the comment in its source.)
    - Add a command for analyzing the wheels for given projects
    - Add a command for analyzing given wheels
    - `load` and `dump`: Add a means for including the PyPI changelog serial
    - `dump`: Add an option for including processing errors/wheels with
      processing errors
    - Add a command & function for pruning old project versions

Wheel Inspection
----------------
- Parse `Description-Content-Type` into a structured `dict`?
- Should flat modules inside packages be discarded from `.derived.modules`?
- Divide `.derived.modules` into a list of packages and a list of flat modules
  (or otherwise somehow indicate which is which)?
- Compare `extract_modules()` with <https://github.com/takluyver/wheeldex>
- Does `extract_modules()` need to take compiled library files into account?
- Include the results of testing manylinux1 wheels with `auditwheel`?
- Should (rarely used) fields similar to `Requires-Dist` be parsed into
  structured `dict`s?
    - `Obsoletes` - no longer supposed to exist?
    - `Obsoletes-Dist` - same format as `Requires-Dist`?
    - `Provides` - no longer supposed to exist?
    - `Provides-Dist` - same as `Requires-Dist` but with a single version
      number instead of a version specifier?
    - `Requires` - no longer supposed to exist?
    - `Requires-External` - same as `Requires-Dist` but with looser version
      string requirements?
- Move `.derived.readme_renders` to inside the
  `.dist_info.metadata.description` object?
    - Do likewise for the `.derived.description_in_*` fields?
- Eliminate the `"derived"` subobject and only store the data within as
  structured fields in the database?
- Add a `.derived.signed` field?
- Add a `.derived.type_checked`(?) field for whether `py.typed` is present?
  (See PEP 561)
- Remove duplicates from `.derived.keywords`?

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
        - list of modules in the wheel (top-level and packages only?)
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
