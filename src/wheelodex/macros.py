""" Custom Jinja filters """

import heapq
import re
from   cmarkgfm        import markdown_to_html
from   flask           import url_for
from   jinja2          import Markup
from   packaging.utils import canonicalize_name as normalize
from   .views          import web

@web.app_template_filter()
def flatten_metadata(metadata):
    """
    Convert a `dict` representation of a ``METADATA`` file as returned by
    `inspect_wheel()` to a sequence of ``(fieldname, value)`` pairs in which
    both elements are ready for display in HTML.

    Known fields are listed in an opinionated order.  Unknown fields are listed
    at the end in lexicographic order.  The ``description`` field is omitted;
    the caller must render it separately.
    """
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
                s = Markup(
                    '<a href="{}">{}</a>'.format(
                        url_for('.project', project=normalize(req["name"])),
                        req["name"],
                    )
                )
                if req["extras"]:
                    s += '[{}]'.format(','.join(req["extras"]))
                if req["url"] is not None:
                    s += ' @ ' + extlink(req["url"])
                if req["specifier"]:
                    s += ' ({})'.format(req["specifier"])
                if req["marker"] is not None:
                    if req["url"] is not None and req["specifier"] is None:
                        s += ' '
                    s += '; ' + req["marker"]
                yield (fieldname, s)
        elif field == 'project_url':
            for purl in value:
                if purl["label"] is None:
                    yield (fieldname, extlink(purl["url"]))
                else:
                    yield (
                        fieldname,
                        purl["label"] + ', ' + extlink(purl["url"]),
                    )
        elif field in ('home_page', 'download_url'):
            yield (fieldname, extlink(value))
        elif field in ('author_email', 'maintainer_email'):
            value = Markup('<span class="at">[at]</span>')\
                    .join(map(Markup.escape, value.split('@')))
            yield (fieldname, value)
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

@web.app_template_filter()
def flatten_wheel_info(wheel_info):
    """
    Convert a `dict` representation of a ``WHEEL`` file as returned by
    `inspect_wheel()` to a sequence of ``(fieldname, value)`` pairs in which
    both elements are ready for display in HTML.

    Known fields are listed in an opinionated order.  Unknown fields are listed
    at the end in lexicographic order.  The ``BODY`` field is omitted; the
    caller must render it separately.
    """
    wheel_info = wheel_info.copy()
    for field in 'wheel_version generator root_is_purelib tag build'.split():
        value = wheel_info.pop(field, None)
        if value is None:
            continue
        fieldname = field.replace('_', '-').title()
        if isinstance(value, list):
            for v in value:
                yield (fieldname, v)
        elif isinstance(value, bool):
            yield (fieldname, str(value).lower())
        else:
            yield (fieldname, value)
    wheel_info.pop("BODY", None)  # Caller must handle this separately
    for field, value in sorted(wheel_info.items()):
        if value is None:
            continue
        fieldname = field.replace('_', '-').title()
        if isinstance(value, list):
            for v in value:
                yield (fieldname, v)
        else:
            yield (fieldname, value)

@web.app_template_filter()
def extlink(url):
    """ Convert a URL to a hyperlink with ``rel="nofollow"`` """
    return Markup(
        '<a href="{0}" rel="nofollow">{0}</a>'.format(Markup.escape(url))
    )

@web.app_template_filter()
def markdown(src):
    """ Render Markdown text """
    return Markup(markdown_to_html(src))

@web.app_template_filter()
def markdown_inline(src):
    """
    Render Markdown text for inline display, with outer ``<p> ... </p>`` tags
    removed
    """
    return Markup(re.sub(r'^<p>|</p>$', '', markdown_to_html(src)))

@web.app_template_filter()
def nsmallest(iterable, n):
    return heapq.nsmallest(n, iterable)
