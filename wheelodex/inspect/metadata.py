# cf. PEP 345 and <https://packaging.python.org/specifications/>
import re
import textwrap
from   headerparser           import HeaderParser
from   packaging.requirements import Requirement
from   packaging.specifiers   import SpecifierSet
from   ..flags                import Flags

def strfield(s):
    return None if s is None or s.strip() in ('', 'UNKNOWN') else s

def project_url(s):
    try:
        label, url = re.split(r'\s*,\s*', s, maxsplit=1)
    except ValueError:
        label, url = None, s
    return {"label": label, "url": url}

def requirement(s):
    req = Requirement(s)
    return {
        "name": req.name,
        "url": req.url,
        "extras": req.extras,
        "specifier": specifier_set(req.specifier),
        "marker": str(req.marker) if req.marker is not None else None,
    }

def specifier_set(specs):
    if specs is None:
        return None
    if not isinstance(specs, SpecifierSet):
        specs = SpecifierSet(specs)
    return [{"operator": s.operator, "version": s.version} for s in specs]

metaparser = HeaderParser()
metaparser.add_field('Metadata-Version', required=True)
metaparser.add_field('Name', required=True)
metaparser.add_field('Version', required=True)
metaparser.add_field('Summary', type=strfield, required=True)
metaparser.add_field('Requires-Dist', type=requirement, multiple=True)
metaparser.add_field('Requires-Python', type=specifier_set)
metaparser.add_field('Project-URL', type=project_url, multiple=True)

for field in 'Author Author-email Description Download-URL Home-page License'\
             ' Maintainer Maintainer-email Keywords'.split():
    # "Description" _should_ be in the body, but this doesn't actually seem to
    # be specified in any PEPs, so accept it in the headers instead just to be
    # sure.
    metaparser.add_field(field, type=strfield)

for field in 'Classifier Obsoletes Obsoletes-Dist Platform Provides'\
             ' Provides-Dist Provides-Extra Requires Requires-External'\
             ' Supported-Platform'.split():
    ### TODO: Don't store UNKNOWN fields in the list
    metaparser.add_field(field, type=strfield, multiple=True)

metaparser.add_additional(
    action=lambda d, name, _: d.setdefault("extra_fields", set()).add(name)
)

def parse_metadata(fp):
    """
    Returns a tuple of:

    - The metadata (including :mailheader:`Description`) as a `dict`, with
      field names lowercased (and hyphens mapped to underscores) and the names
      of unknown fields stored in a `set` under the key ``"extra_fields"``

    - a set of flags representing notable variations observed in the structure
      of the input
    """

    md = metaparser.parse_file(fp)
    metadata = {k.lower().replace('-', '_'): v for k,v in md.items()}
    ### TODO: Log extra_fields?
    ### TODO: Remove null/empty fields???
    flags = set()

    if metadata.get('keywords'):
        ## Based on how wheel handles keywords:
        #keywords = re.split(r'[\0-,]+', metadata['keywords'])

        # Based on how pydigger.com seems to handle keywords (See
        # <https://pydigger.com/keywords>):
        if ',' in metadata['keywords']:
            keywords = metadata['keywords'].split(',')
            ### TODO: Strip whitespace?  Discard empty keywords?
            flags.add(Flags.COMMA_SEPARATED_KEYWORDS)
        else:
            keywords = metadata['keywords'].split()
            flags.add(Flags.SPACE_SEPARATED_KEYWORDS)
        metadata['keywords'] = keywords

    body = strfield(md.body)
    if body is not None:
        flags.add(Flags.DESCRIPTION_IN_BODY)
    if metadata.get('description') is None:
        metadata['description'] = body
    else:
        metadata['description'] = textwrap.dedent(metadata['description'])
            # Does this dedent correctly?
        flags.add(Flags.DESCRIPTION_IN_HEADERS)
        if body is not None and metadata['description'].strip() != body.strip():
            flags.add(Flags.CONFLICTING_DESCRIPTIONS)

    return metadata, flags
