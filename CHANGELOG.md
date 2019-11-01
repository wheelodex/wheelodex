In Development
--------------
- Prevent line-breaking on hyphens in timestamps

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
