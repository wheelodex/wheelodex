/api/projects/<project> [?v=<VERSION_SPEC>&pre=<BOOL>]
    list of versions (optionally filtered by the given version spec)
    Support filtering by Python version and other wheel compatibility tags?
    Include a list of wheels for each version?
    Be canonicalization-agnostic for project names
    Don't support === in version specs?

    /latest - redirect to highest-numbered non-prerelease version

    /<version>
        list of wheels (including Requires-Python field)
        Support filtering by Python version and other wheel compatibility tags?
        Redirect to the normalized version string if necessary

        /<wheel_filename>
            {
                package:  # normalized?
                version:  # normalized
                wheel_name:  # filename

                file:
                    url:
                    size:
                    hashes:  # Taken from PyPI?
                        md5:
                        sha1:
                    uploaded: <timestamp>
                    signature: ?

                metadata:
                    # Straight JSONification of METADATA
                    # Include long description?
                    # Include list of unknown fields (here?)

                wheel:
                    # broken-out compatibility tags from filename/WHEEL
                    # wheel signatures?
                    # other information from WHEEL?
                    is_purelib: BOOL

                entry_points:
                    console_scripts: [str]

                # dist-info files copied from egg-info
                # <https://setuptools.readthedocs.io/en/latest/formats.html>:
                top_level: [str]
                namespace_packages: ???
                    # include the namespace package type/mechanism?
                dependency_links: ???

                # metadata.json ???

                # list of all module names?
                # list of all files outside dist-info / parsed RECORD ?

                scanned: <timestamp>  # date added to this database

                # Various statistics for determining what to support etc.:
                # - list of files in dist-info
                # - whether metadata.json/pydist.json is present
                # - JSON `metadata_version`?
                # - whether signed
                # - whether tags (and name & version?) in filename match those
                #   in WHEEL
                # - whether certain obscure metadata fields are set?
                #   (Requires-Python, Description-Content-Type, Project-URL,
                #   etc.)
                # - fields present in JSON metadata?
                # - whether keywords are space- or comma-separated
                # - whether Description is a header field or the body
                # - types of namespace packages used
                # - whether there's a license file in dist-info?
            }

            /pydist.json - On-demand creation of metadata 3.0 file ???

            /dist-info/METADATA
            /dist-info/WHEEL
            /dist-info/RECORD
            /dist-info/top_level.txt
            /dist-info/metadata.json
            /dist-info/DESCRIPTION.rst
            /dist-info/entry_points.txt
            /dist-info/LICENSE.txt  # ?
            # etc.


/api/search
    # Search by top level packages
    # Search by reverse dependencies
    # Search by all module names?
    # Search by namespace packages?
    # Search by keywords, classifiers, etc.?
    # Search by files outside dist-info
    # Search by wheels that define certain metadata fields or have certain tags?

    /entry_points?name=<NAME>&type<console_scripts|...>
        # at least one of `name` and `type` must be supplied
