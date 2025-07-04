In Development
--------------
- Emit "BEGIN" and "END" log messages for `process-queue`
- Adjust stats log entries:
    - Emit entries for failed tasks
    - Add a `"success"` field for whether the task succeeded
    - Add a `"duration"` field
    - `purge-old-versions`: Add a `"multiversion_kept"` field
- Send more journal lines in failure e-mails

v2025.5.12
----------
- Serve a `robots.txt` file disallowing access to almost all pages
- Deployment: Only run `register-wheels` twice a day, down from three times

v2025.2.2
---------
- Migrated from setuptools to hatch
- Support Python 3.13
- Deployment: Install pip & virtualenv via apt for compatibility with
  externally-managed Python environments
- Deployment: Configure sshd via .d directory

v2023.11.14
-----------
- Fixed broken pagination of certain queries
- Moved to wheelodex organization

v2023.10.16
-----------
- Always open text files in UTF-8
- Support Python 3.12
- Drop support for Python 3.7, 3.8, and 3.9
- Add type annotations
- Speed up `purge_old_versions()` again
- `purge_old_versions()`: Delete a project's latest version if has neither
  wheels nor orphan wheels
- Use pydantic to validate responses from PyPI's JSON API and wheel information
  loaded from JSON
- Update deployment playbook for Ansible 8.5
- Dependencies:
    - Drop pyRFC3339 dependency
    - Drop requests-download dependency
    - Drop SQLAlchemy-Utils
    - Update SQLAlchemy to 2.x
    - Update Flask to 3.x
    - Update Flask-Migrate to 4.x
    - Update Flask-SQLAlchemy to ~=3.1
    - Update pypi-simple to 1.x
    - Unpin cmarkgfm version
    - Replace psycopg2-binary with psycopg

v2023.6.11
----------
- When interacting with PyPI's Simple or JSON APIs, retry requests on general
  communication errors
- Drop support for Python 3.6

v2022.2.20
----------
- `scan-changelog` log entries are now in JSON Lines format

v2022.2.19
----------
- Deployment:
    - Configure systemd's journaling to only retain the last 180 days of logs
    - Adjust wheel registration times by two hours
- Support Python 3.10
- Log entries written to the `WHEELODEX_STATS_LOG_DIR` are now in JSON Lines
  format and display timestamps in ISO 8601(-ish) format
- Update links in entry point descriptions
- Use `importlib.resources` on Python 3.9+
- Dependencies:
    - Update cmarkgfm to 0.7.0
    - Update to Flask 2.0 and Click 8.0
    - Update Flask-Migrate to 3.0
    - Switch from retrying to tenacity

v2021.9.19
----------
- Update links in entry point descriptions

v2021.3.22
----------
- Fix a bug in `remove_wheel()`

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
