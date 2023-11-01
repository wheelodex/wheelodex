.. image:: https://www.repostatus.org/badges/latest/active.svg
    :target: https://www.repostatus.org/#active
    :alt: Project Status: Active — The project has reached a stable, usable
          state and is being actively developed.

.. image:: https://github.com/wheelodex/wheelodex/actions/workflows/test.yml/badge.svg
    :target: https://github.com/wheelodex/wheelodex/actions/workflows/test.yml
    :alt: CI Status

.. image:: https://codecov.io/gh/wheelodex/wheelodex/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/wheelodex/wheelodex

.. image:: https://img.shields.io/github/license/wheelodex/wheelodex.svg
    :target: https://opensource.org/licenses/MIT
    :alt: MIT License

`Site <https://www.wheelodex.org>`_
| `GitHub <https://github.com/wheelodex/wheelodex>`_
| `Issues <https://github.com/wheelodex/wheelodex/issues>`_
| `Changelog <https://github.com/wheelodex/wheelodex/blob/master/CHANGELOG.md>`_

Packaged projects for the `Python <https://www.python.org>`_ programming
language are distributed in two main formats: *sdists* (archives of code and
other files that require processing before they can be installed) and *wheels*
(zipfiles of code ready for immediate installation).  A project's wheel
contains the complete information about what modules, files, & commands the
project installs, along with information about what other projects the project
depends on, but `the Python Package Index (PyPI) <https://pypi.org>`_ (where
wheels are distributed) doesn't expose any of this information!  This is the
problem that `Wheelodex <https://www.wheelodex.org>`_ is here to solve.

Wheelodex scans PyPI for wheel files, analyzes them, and stores & displays the
results.  The site allows users to view the complete metadata inside wheels,
search for wheels containing a given Python module or file, browse or search
for wheels that define a given command or other entry point, and even find out
projects' reverse dependencies.

Note that, in order to save disk space, Wheelodex only records data on wheels
from the latest version of each PyPI project; wheels from older versions are
periodically purged from the database.  Projects' long descriptions aren't even
recorded at all.

Suggestions and pull requests are welcome.
