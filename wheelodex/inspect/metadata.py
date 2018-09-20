# cf. PEP 345 and <https://packaging.python.org/specifications/>
import re
from   headerparser           import HeaderParser
from   packaging.requirements import Requirement
from   .util                  import fieldnorm, strfield

def requirement(s):
    req = Requirement(s)
    return {
        "name": req.name,
        "url": req.url,
        "extras": sorted(req.extras),
        "specifier": str(req.specifier),
        "marker": str(req.marker) if req.marker is not None else None,
    }

def project_url(s):
    try:
        label, url = re.split(r'\s*,\s*', s, maxsplit=1)
    except ValueError:
        label, url = None, s
    return {"label": label, "url": url}

metaparser = HeaderParser(normalizer=fieldnorm)
metaparser.add_field('Metadata-Version')
metaparser.add_field('Name')
metaparser.add_field('Version')
metaparser.add_field('Summary', type=strfield)
metaparser.add_field('Requires-Dist', type=requirement, multiple=True)
metaparser.add_field('Requires-Python')
metaparser.add_field('Project-URL', type=project_url, multiple=True)

for field in 'Author Author-email Description Download-URL Home-page License'\
             ' Maintainer Maintainer-email Keywords Description-Content-Type'\
             .split():
    ### TODO: Dedent Description (et alii?)?
    metaparser.add_field(field, type=strfield)

for field in 'Classifier Obsoletes Obsoletes-Dist Platform Provides'\
             ' Provides-Dist Provides-Extra Requires Requires-External'\
             ' Supported-Platform'.split():
    metaparser.add_field(field, type=strfield, multiple=True)

metaparser.add_additional(multiple=True, type=strfield)

def parse_metadata(fp):
    md = metaparser.parse_file(fp)
    metadata = md.normalized_dict()
    for k,v in metadata.items():
        if isinstance(v, list):
            metadata[k] = [u for u in v if u is not None]
    if md.body is not None:
        metadata["BODY"] = strfield(md.body)
    return metadata
