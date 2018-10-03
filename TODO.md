- Add docstrings
    - Add `help` strings to commands & their options
- Add a column to `WheelData` for storing the revision of `SCHEMA` that
  `raw_data` conforms to?
    - Alternatively, store the revision of the wheel inspection code used?
        - Split `wheelodex.inspect` into a separate project?
- Upgrade `SCHEMA` to a more recent JSON Schema draft
- If the latest version of a project doesn't have any wheels, should
  `iterqueue()` return the wheels for the next latest version that does?
- Replace `WheelData.update_structure()` with Alembic
- Eliminate `WheelDatabase` and make its methods into functions that operate on
  the app's `db` object?
    - Replace `WheelDatabase`'s constructor with a context manager that calls
      `db.create_all()`, yields `db.session`, and commits or rolls back as
      appropriate?
    - Make `add_wheel_data()` and `add_wheel_error()` into methods of `Wheel`?
- Register large wheels but don't return them from `iterqueue()`?
- Rename `process_queue` (the function and the command) and `iterqueue()`
- Add a means for setting descriptions for entry points to display in the web
  interface
    - Where possible, write a description of each entry point, including what
      project consumes it
- Try to make `wheel_sort_key()` both more efficient and more comprehensive

- There are several database queries (marked with "TODO: Use preferred wheel")
  that need to be amended to only return results for one wheel (the preferred
  wheel) per project.  Figure out how to amend them and do so.

- Problem: The deletion of a release from PyPI may leave Wheelodex with no
  wheels registered for a project even though there may be lower-versioned
  releases on PyPI with wheels.  Try to keep this from happening.

- Problem: PyPI's JSON API doesn't update automatically (probably due to
  caching), causing some wheels to fall through the cracks when scanning the
  changelog.  Deal with this.

- Commands:
    - Give `load` an option for overwriting any `WheelData` that's already in
      the database?  (This would require first fixing `add_wheel_data()`; see
      the comment in its source.)
    - Add a command for analyzing the wheels for given projects (including an
      option for forcing reanalysis)
    - Add a command for analyzing given wheels (including an option for forcing
      reanalysis)
    - `dump`: Add an option for including processing errors/wheels with
      processing errors
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

Wheel Inspection
----------------
- Parse `Description-Content-Type` into a structured `dict`?
- Should flat modules inside packages be discarded from `.derived.modules`?
- Divide `.derived.modules` into a list of packages and a list of flat modules
  (or otherwise somehow indicate which is which)?
- Compare `extract_modules()` with <https://github.com/takluyver/wheeldex>
- Does `extract_modules()` need to take compiled library files into account?
- Determine namespace packages other than those listed in
  `namespace_packages.txt`?  (cf. wheeldex?)
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
- Give `inspect_wheel()` an option for whether to keep long descriptions?
- Show more detailed (and machine readable) information on verification errors

Web Interface
-------------
- Make things look good
    - Add breadcrumbs to pages
    - Improve page `<title>`s
- Get rid of the wheel list; it's just for testing
- Main page: Show statistics on wheels registered, wheels analyzed, and
  projects known (or something like that)
- Wheel data:
    - If there were errors processing the wheel, show some indication of this
    - Include whether the wheel was verified
    - Include TOC-like links at the top linking to each section on the page
    - `METADATA` display:
        - Obfuscate e-mail addresses
        - Make each keyword into a hyperlink?
        - Make each classifier into a hyperlink?
    - Insert a blank line between entry point groups
    - Sort `RECORD` entries?
    - Display `RECORD` digests in hex?
    - Add a separate box showing dependencies, organized by extras?
    - Add a dedicated box for commands defined by the wheel?
    - Add a dedicated box for Python packages defined by the wheel?
    - Include (at least some) reverse dependencies on the page itself
    - Eliminate the dedicated wheel data pages and merge them into project
      pages
- Project page:
    - Show some sort of informative boilerplate if no project by the given name
      is found
        - Include a link to the project's PyPI page
    - If no wheel data is available, show information on latest available
      wheels
    - If there are versions but none of them have wheels, show a message to
      that effect
    - Show a list of links to known wheels for the project, organized by
      version, highlighted based on whether they have data
- Entry point groups:
    - Add an option for sorting by quantity?
    - Give entry points groups short descriptions to show next to them in the
      entry point group list?
- Entry points:
    - Add options for sorting by either project or entry point name, ascending
      or descending
    - Include project summaries in entry point lists?
- Include project summaries in reverse dependency lists
- Make all URLs with project names in them redirect to canonical URLs that use
  the normalized spellings
- Provide a download of a database export made periodically with `dump`
- Add a paginated list of projects that have data?

- Add "API" endpoints for just retrieving JSON:
    - `/json/projects/<project>` — returns a list of all known wheels (with
      links) for a project and whether they have data
        - organize by version like in PyPI's JSON API?
    - `/json/projects/<project>/data` — returns the data for the preferred
      wheel for a project
    - `/json/projects/<project>/rdepends` — reverse dependencies
    - `/json/wheels/<filename>.whl.json` — individual wheel data

- Add search options:
    - search by project name
    - searching for wheels that contain a given module
    - searching for wheels that contain a given file, with glob support
    - search for wheels that define a given command or other entry point?
    - search/browse by keywords, classifiers, etc.?
    - search for wheels that define given metadata fields?
    - search by contents of arbitrary metadata fields?

- Add pages of various statistics:
   - wheel generators
   - keywords
   - Project URL labels
   - description content types?
   - license files?
   - metadata versions?
   - "Platform" values
