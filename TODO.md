- If the latest version of a project doesn't have any wheels, should
  `scan_pypi()` register the latest version that does?
- Write descriptions for more entry points
- Try to make `wheel_sort_key()` both more efficient and more comprehensive
- Come up with a better way of logging processing errors (e.g., so that people
  actually see them)
- Add tests for the commands
- Add more thorough tests for the views somehow
- Use eager loading to speed up various database queries
    - Use eager loading to eliminate the boolean fields in the return value of
      `Project.versions_wheels_grid()`
- `scan_changelog()`: Don't do anything for release creation events; wait for
  wheels to be uploaded for the release before bothering to create the
  `Version` object?
- Add tables & pages for reverse Obsoletes-Dist and Provides-Dist dependencies
- Should a project's display name be updated whenever it gets a new release or
  wheel?

- There are several database queries (marked with "TODO: Use preferred wheel")
  that need to be amended to only return results for one wheel (the preferred
  wheel) per project.  Figure out how to amend them and do so.

- Problem: The deletion of a release from PyPI may leave Wheelodex with no
  wheels registered for a project even though there may be lower-versioned
  releases on PyPI with wheels.  Try to keep this from happening.

- Should package yanking (PEP 592) be honored somehow?

- Commands:
    - Give `load` an option for overwriting any `WheelData` that's already in
      the database?  (This would require first fixing `Wheel.set_data()`; see
      the comment in its source.)
    - Add a command for analyzing the wheels for given projects (including an
      option for forcing reanalysis)
    - Add a command for analyzing given wheels (including an option for forcing
      reanalysis)
    - `dump`: Add an option for including processing errors/wheels with
      processing errors
    - `load`: Load "errored" state
    - Add a command (`scan-projects`?) that acts as a limited `scan-pypi`, only
      registering wheels for projects listed on the command line?
    - Add a command for setting the serial to the current value on PyPI and
      doing nothing else?
    - Give `scan-changelog` an option for ignoring projects that aren't already
      in the database?
    - At the end of `scan-pypi`, output a count of how many genuinely new
      wheels were added?
    - Give `process_queue` (the function and the command) options for limiting
      the number and/or total size of wheels to process
    - Add a `dump-entry-points` command for outputting the summaries &
      descriptions from the database
    - Give `load-entry-points` an option for deleting the summaries &
      descriptions of entry point groups not listed in the input file?
    - Add a command for purging projects that have no wheels or reverse
      dependencies?

Web Interface
-------------
- Make things look good
    - Show wheelodex version at the bottom of every page?
    - Show link to wheelodex's GitHub at the bottom of every page?
- Main page: Show how many analyzed wheels there are?
- Project/wheel data:
    - Show a message if we know there's a newer version but it doesn't have any
      wheels?
    - `METADATA` display:
        - Make each keyword into a hyperlink?
        - Make each classifier into a hyperlink?
    - Sort `RECORD` entries?
    - Display `RECORD` digests in hex?
    - Add a separate box showing dependencies, organized by extras?
    - Add a dedicated box for commands defined by the wheel?
    - Add a dedicated box for Python packages defined by the wheel?
    - Include (at least some) reverse dependencies on the page itself
    - Show human-readable descriptions of the tags in a wheel's filename?
    - Don't list wheels for versions that would be deleted by an immediate call
      to `purge_old_versions()`?
- Entry point groups:
    - Add a search box for limiting the list to just those matching a pattern
- Entry points:
    - Add options for sorting by either project or entry point name, ascending
      or descending
    - Include project summaries in entry point lists?
- Provide a download of a database export made periodically with `dump`
- Do something with the keywords table
- `project_json`: Add links to `/data` and `/rdepends`?
- Should `search_commands` do a prefix-matching search for globless input?
- Should `search_modules` do a prefix-matching search (limited using regexes to
  not match additional `.`) for globless input?
- Provide a clear way for users to view reverse dependencies of projects that
  don't have wheels

- Add search options:
    - search entry points other than `console_scripts`
    - search/browse by keywords, classifiers, etc.?
    - search for wheels that define given metadata fields?
    - search by contents of arbitrary metadata fields?
    - search by namespace package?

- Add pages of various statistics:
    - wheel generators
    - keywords
    - Project URL labels
    - description content types?
    - license files?
    - metadata versions?
    - "Platform" values


Optimization
------------
- Try to speed up file search queries with:

        CREATE EXTENSION pg_trgm;
            -- ^^ Must be run inside the database by a superuser
        CREATE INDEX files_path_idx ON files USING GIN (path gin_trgm_ops);

    and likewise for other columns queried with `LIKE`/`ILIKE`?

    The SQLAlchemy equivalent of the latter statement appears to be:

        Index(
            'files_path_idx',
            File.path,
            postgresql_using='gin',
            postgresql_opts={'path': 'gin_trgm_ops'},
        )
