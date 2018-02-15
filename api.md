/api/projects/<project> [?v=<VERSION_SPEC>&pre=<BOOL>]
    list of versions (optionally filtered by the given version spec)
    Support filtering by Python version and other wheel compatibility tags?
    Include a list of wheels for each version?
    Be canonicalization-agnostic for project names
    Don't support === in version specs?

    /latest - redirect to highest-numbered non-prerelease version

    /<version>
        list of wheels (including tags and Requires-Python field)
        Support filtering by Python version and other wheel compatibility tags?
        Redirect to the normalized version string if necessary

        /<wheel_filename>
            {
                package:  # normalized?
                version:  # normalized
                filename: <str>
                scanned: <timestamp>  # date added to this database

                _links:
                    package
                    version

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

                # list of all files in wheel

                # list of all module names?

                # Various statistics about irregularities etc. that cannot be
                # (easily) derived from the other fields:
                # - JSON `metadata_version`?
                # - fields present in JSON metadata?
                # - whether signed
                # - whether tags (and name & version?) in filename match those
                #   in WHEEL
                # - whether keywords are space- or comma-separated
                # - whether Description is a header field or the body
                # - whether the README renders properly
                # - types of namespace packages used
            }

            /pydist.json - On-demand creation of metadata 3.0 file ???


/api/search
    # Search by top level packages
    # Search by reverse dependencies
    # Search by all module names?
    # Search by namespace packages?
    # Search by keywords, classifiers, etc.?
    # Search by files (outside or inside dist-info), with glob support
    # Search by wheels that define certain metadata fields or have certain tags?
    # Search by contents of various metadata fields? (Metadata-Version,
    #    Wheel-Version, Generator, everything???)

    # Give all of these parameters for restricting by wheel tag?
    # Add sorting options?
    /entry_points?name=<NAME>&type=<console_scripts|...>
        # at least one of `name` and `type` must be supplied
    /keywords?kw=<query array>
        # Returns wheels with all of the given keywords

    # Give each /search subpage a /qty subpage that just returns the numbers of
    # matching projects, versions, and wheels?
