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

        /<wheel_filename> - See wheel-schema.txt
            ### Add an endpoint for getting just PEP 566-compatible JSON metadata?


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
