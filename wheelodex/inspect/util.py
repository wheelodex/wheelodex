def extract_dependencies(requires_dist):
    """
    Given a list of :mailheader:`Requires-Dist` field values, return a list of
    the names of all packages specified as dependencies therein (whether
    conditional or required), sorted and with duplicates removed
    """
    raise NotImplementedError

def extract_modules(filelist):
    raise NotImplementedError

def split_keywords(kwstr):
    # cf. `format_tags()` in Warehouse <https://git.io/fA1AT>, which seems to
    # be the part of PyPI responsible for splitting keywords up for display

    # cf. how wheel handles keywords:
    #keywords = re.split(r'[\0-,]+', kwstr)

    # Based on how pydigger.com seems to handle keywords (See
    # <https://pydigger.com/keywords>):
    if ',' in kwstr:
        return (kwstr.split(','), ',')
        ### TODO: Strip whitespace?  Discard empty keywords?
    else:
        return (kwstr.split(), ' ')
