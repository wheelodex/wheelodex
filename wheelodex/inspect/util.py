from packaging.utils import canonicalize_name as normalize

def extract_modules(filelist):
    modules = set()
    for fname in filelist:
        parts = fname.split('/')
        if not parts or not parts[-1].lower().endswith('.py'):
            continue
        parts[-1] = parts[-1][:-3]
        if not all(p.isidentifier() for p in parts):
            continue
        if parts[-1] == '__init__' and len(parts) > 1:
            parts.pop()
        modules.add('.'.join(parts))
    return sorted(modules)

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

def strfield(s):
    return None if s is None or s.strip() in ('', 'UNKNOWN') else s

def fieldnorm(s):
    return s.lower().replace('-', '_')

def unique_projects(projects):
    seen = set()
    for p in projects:
        pn = normalize(p)
        if pn not in seen:
            yield p
        seen.add(pn)
