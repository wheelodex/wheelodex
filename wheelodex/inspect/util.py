def extract_dependencies(requires_dist):
    """
    Given a list of :mailheader:`Requires-Dist` field values, return a list of
    the names of all packages specified as dependencies therein (whether
    conditional or required), sorted and with duplicates removed
    """
    raise NotImplementedError
