from .views import web

@web.app_template_filter()
def flatten_metadata(metadata):
    metadata = metadata.copy()
    for field in '''
        metadata_version name version summary
        author author_email maintainer maintainer_email
        home_page download_url project_url
        license
        keywords
        classifier
        platform supported_platform
        requires_python
        requires_dist
        provides_extra
        description_content_type
        obsoletes obsoletes_dist
        provides provides_dist
        requires requires_external
    '''.split():
        value = metadata.pop(field, None)
        if value is None:
            continue
        fieldname = field.replace('_', '-').title()
        if field == 'requires_dist':
            for req in value:
                s = req["name"]
                if req["extras"]:
                    s += '[{}]'.format(','.join(req["extras"]))
                if req["url"] is not None:
                    s += ' @ ' + req["url"]
                if req["specifier"] is not None:
                    s += ' ({})'.format(req["specifier"])
                if req["marker"] is not None:
                    if req["url"] is not None and req["specifier"] is None:
                        s += ' '
                    s += '; ' + req["marker"]
                yield (fieldname, s)
        elif field == 'project_url':
            for purl in value:
                if purl["label"] is None:
                    yield (fieldname, purl["url"])
                else:
                    yield (fieldname, '{label}, {url}'.format_map(purl))
        elif isinstance(value, list):
            for v in value:
                yield (fieldname, v)
        else:
            yield (fieldname, value)
    metadata.pop("description", None)  # Caller must handle this separately
    for field, value in sorted(metadata.items()):
        if value is None:
            continue
        fieldname = field.replace('_', '-').title()
        if isinstance(value, list):
            for v in value:
                yield (fieldname, v)
        else:
            yield (fieldname, value)
