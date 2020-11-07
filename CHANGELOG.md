v2020.11.7
----------
- Use version 0.7.0 of `pypi-simple`
- Drop support for Python 3.5
- Support Python 3.9
- Use version 1.7.0 of `wheel-inspect`

v2020.6.22
----------
- Strip leading & trailing whitespace from search terms before searching
- Use version 1.5.0 of `wheel-inspect`
- Internal changes:
    - Define an index on `WheelData.processed` in order to speed up the
      "Recently-Analyzed Wheels" page
    - Added a `has_wheels` column to `Project` in order to speed up some
      queries
    - Run Ansible deployment tasks under Python 3

v2020.3.29
----------
- Added a page listing the most depended-on projects
- Added a description for the `flake8_import_order.styles` entry point group
- Lower the logging level of most messages from `purge-old-versions`
- File search results are now displayed as 50 wheels per page, each with up to
  5 files listed under them
- Internal changes:
    - Added a `source_project_id` column to `dependency_tbl`, changing it to an
      association object, in order to speed up the query behind the "most
      depended-on projects" page
- Deployment changes:
    - Updated `ssl_protocols` setting in Nginx
    - Log slow database queries

v2020.3.18
----------
- Added a description of the wheel data schema to the JSON API page
- Internal changes:
    - Replace the uses of `pkg_resources` with `importlib-metadata` and
      `importlib-resources`
- Deployment changes:
    - Increase wheel processing size limit to 5 MiB

v2020.2.14
----------
- Properly sort `py_version_nodot` strings containing underscores (e.g.,
  `3_10`)
- Use version 1.4.0 of `wheel-inspect`
- Internal changes:
    - Trim whitespace from keywords and delete empty keywords in database

v2019.11.14
-----------
- Prevent line-breaking on hyphens in timestamps
- Internal changes:
    - Record the `wheel-inspect` version whenever a wheel processing error
      occurs
    - Greatly speed up `purge_old_versions()`

v2019.10.30
-----------
- Highlight alternate rows of RECORD tables
- Internal changes:
    - Added a uniqueness constraint to the keywords table
    - Convert `wheels.uploaded` to a timestamp type
    - Use the JSON API's new `"upload_time_iso_8601"` field instead of
      `"upload_time"`
- Support Python 3.8

v2019.5.9
---------
- Use version 1.3.0 of `wheel-inspect`

v2019.4.21
----------
- Fix a typo in the "Down for Maintenance" message
- Fix a bug in handling of "orphan" wheels

v2019.4.20
----------
- Use version 1.2.0 of `wheel-inspect`
- Gave the scheduled commands provisions for logging statistics to files

v2018.11.14
-----------
- "Recently-Analyzed Wheels" page: Use `%z` instead of `%Z` for timestamp
  timezones
- Added descriptions for the `pygments.*` and `pytest11` entry point groups
- Support listing entry point groups by entry point quantity

v2018.10.28
-----------
- Show "[empty]" for empty dist-info files (other than
  `zip-safe`/`not-zip-safe`)
- Added a "Search Projects" box at the top of most pages
- Use version 1.1.0 of `wheel-inspect`

v2018.10.17
-----------
Initial public release
