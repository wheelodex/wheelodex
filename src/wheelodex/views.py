""" Flask views """

from   collections     import OrderedDict
from   functools       import wraps
import re
from   flask           import Blueprint, abort, current_app, jsonify, \
                                redirect, render_template, request, url_for
from   packaging.utils import canonicalize_name as normalize
from   sqlalchemy.sql.functions import array_agg
from   .dbutil         import rdepends_query
from   .models         import DependencyRelation, EntryPoint, EntryPointGroup, \
                                File, Module, Project, Version, Wheel, \
                                WheelData, db
from   .util           import glob2like, json_response, like_escape

web = Blueprint('web', __name__)

from . import macros  # noqa

def project_view(f):
    """
    A decorator for views that take a ``project`` parameter.  If the project
    name is not in normalized form, a 301 redirect is issued.  Otherwise, the
    `Project` object is fetched from the database and passed to the view
    function as the ``project`` parameter.
    """
    @wraps(f)
    def wrapped(project, **kwargs):
        normproj = normalize(project)
        if normproj != project:
            return redirect(
                url_for('.'+f.__name__, project=normproj, **kwargs),
                code=301,
            )
        else:
            p = Project.query.filter(Project.name == normproj).first_or_404()
            return f(project=p, **kwargs)
    return wrapped

@web.route('/index.html')
@web.route('/')
def index():
    """ The main page """
    return render_template(
        'index.html',
        proj_qty = Project.query.filter(Project.has_wheels).count(),
        whl_qty  = Wheel.query.count(),
        #data_qty = WheelData.query.count(),
    )

@web.route('/about/')
def about():
    """ The "About" page """
    return render_template('about.html')

@web.route('/json-api/')
def json_api():
    """ The "JSON API" page """
    p = Project.query.filter(Project.name == 'requests').one_or_none()
    example_wheel = p and p.best_wheel
    return render_template('json_api.html', example_wheel=example_wheel)

@web.route('/recent/')
def recent_wheels():
    """ A list of recently-analyzed wheels """
    qty = current_app.config["WHEELODEX_RECENT_WHEELS_QTY"]
    recents = db.session.query(Project, Version, Wheel, WheelData)\
                        .join(Version, Project.versions)\
                        .join(Wheel, Version.wheels)\
                        .join(WheelData, Wheel.data)\
                        .order_by(WheelData.processed.desc())\
                        .limit(qty)
    return render_template('recent_wheels.html', recents=recents)

@web.route('/rdepends-leaders/')
### TODO: Add caching
def rdepends_leaders():
    qty = current_app.config["WHEELODEX_RDEPENDS_LEADERS_QTY"]
    q = db.session.query(
        Project,
        db.func.count(DependencyRelation.source_project_id.distinct())
               .label('qty')
    ).join(DependencyRelation, Project.id == DependencyRelation.project_id)\
     .group_by(Project)\
     .order_by(db.desc('qty'))\
     .limit(qty)
    return render_template('rdepends_leaders.html', leaders=q)

@web.route('/projects/')
def project_list():
    """ A list of all projects with wheels """
    per_page = current_app.config["WHEELODEX_PROJECTS_PER_PAGE"]
    projects = Project.query.filter(Project.has_wheels)\
                            .order_by(Project.name.asc())\
                            .paginate(per_page=per_page)
    return render_template('project_list.html', projects=projects)

@web.route('/projects/<project>/')
@project_view
def project(project):
    """
    A display of the data for a given project, including its "best wheel"
    """
    rdeps_qty = rdepends_query(project).count()
    whl = project.best_wheel
    if whl is not None:
        return render_template(
            'wheel_data.html',
            whl          = whl,
            project      = project,
            rdepends_qty = rdeps_qty,
            all_wheels   = project.versions_wheels_grid(),
            subpage      = False,
        )
    else:
        return render_template(
            'project_nowheel.html',
            project      = project,
            rdepends_qty = rdeps_qty,
        )

@web.route('/projects/<project>/wheels/<wheel>/')
@project_view
def wheel_data(project, wheel):
    """
    A display of the data for a project, focused on a given wheel.  If the
    wheel is unknown, redirect to the project's main page.
    """
    whl = Wheel.query.filter(Wheel.filename == wheel).one_or_none()
    if whl is None:
        return redirect(url_for('.project', project=project.name), code=302)
    elif whl.project != project:
        abort(404)
    else:
        return render_template(
            'wheel_data.html',
            whl          = whl,
            project      = project,
            rdepends_qty = rdepends_query(project).count(),
            all_wheels   = project.versions_wheels_grid(),
            subpage      = True,
        )

@web.route('/projects/<project>/rdepends/')
@project_view
def rdepends(project):
    """ A list of reverse dependencies for a project """
    per_page = current_app.config["WHEELODEX_RDEPENDS_PER_PAGE"]
    rdeps = rdepends_query(project).order_by(Project.name.asc())\
                                   .paginate(per_page=per_page)
    return render_template(
        'rdepends.html',
        project  = project,
        rdepends = rdeps,
    )

@web.route('/entry-points/')
def entry_point_groups():
    """
    A list of all entry point groups (excluding those without any entry points)
    """
    per_page = current_app.config["WHEELODEX_ENTRY_POINT_GROUPS_PER_PAGE"]
    sortby = request.args.get('sortby', '')
    ### TODO: Use preferred wheel (Alternatively, limit to the latest
    ### data-having version of each project):
    # The point of this subquery is to weed out duplicate
    # Project-EntryPoint.name pairs before counting.  There's probably a better
    # way to do this.
    subq = db.session.query(EntryPoint.group_id)\
                     .join(WheelData).join(Wheel).join(Version).join(Project)\
                     .group_by(EntryPoint.group_id,EntryPoint.name,Project.id)\
                     .subquery()
    groups = db.session.query(
                            EntryPointGroup.name,
                            EntryPointGroup.summary,
                            db.func.count().label('qty'),
                        )\
                       .join(subq, EntryPointGroup.id == subq.c.group_id)\
                       .group_by(EntryPointGroup)
    if sortby == 'qty':
        groups = groups.order_by(db.desc('qty'))
    else:
        groups = groups.order_by(EntryPointGroup.name.asc())
    groups = groups.paginate(per_page=per_page)
    return render_template('entry_point_groups.html', groups=groups,
                           sortby=sortby)

@web.route('/entry-points/<group>/')
def entry_point(group):
    """
    A list of all entry points in a given group and the packages that define
    them
    """
    ep_group = db.session.query(EntryPointGroup)\
                         .filter(EntryPointGroup.name == group)\
                         .first_or_404()
    per_page = current_app.config["WHEELODEX_ENTRY_POINTS_PER_PAGE"]
    ### TODO: Use preferred wheel (Alternatively, limit to the latest
    ### data-having version of each project):
    project_eps = db.session.query(Project, EntryPoint.name)\
                            .join(Version).join(Wheel).join(WheelData)\
                            .join(EntryPoint)\
                            .filter(EntryPoint.group == ep_group)\
                            .group_by(Project, EntryPoint.name)\
                            .order_by(
                                Project.name.asc(), EntryPoint.name.asc()
                            ).paginate(per_page=per_page)
    return render_template(
        'entry_point.html',
        ep_group    = ep_group,
        project_eps = project_eps,
    )

@web.route('/search/projects/')
def search_projects():
    """
    Search for projects

    - When given the name of a known project (*modulo* normalization), redirect
      to that project's page

    - When given an unknown project name, search for all known project names
      that have it as a prefix

    - When given a search term with a ``*`` in it, normalize the rest of the
      search term and perform file glob matching against all known normalized
      project names
    """
    search_term = request.args.get('q', '').strip()
    if search_term:
        per_page = current_app.config["WHEELODEX_SEARCH_RESULTS_PER_PAGE"]
        normterm = re.sub(r'[-_.]+', '-', search_term.lower())
        # Only search projects that have wheels:
        q = Project.query.filter(Project.has_wheels)
        if '*' in normterm or '?' in normterm:
            q = q.filter(Project.name.like(glob2like(normterm), escape='\\'))
        elif q.filter(Project.name == normterm).one_or_none() is not None:
            return redirect(url_for('.project', project=normterm), code=307)
        else:
            q = q.filter(
                Project.name.like(like_escape(normterm) + '%', escape='\\')
            )
        results = q.order_by(Project.name.asc()).paginate(per_page=per_page)
    else:
        results = None
    return render_template(
        'search_projects.html',
        search_term = search_term,
        results     = results,
    )

@web.route('/search/files/')
def search_files():
    """ Search for wheels containing files with a given name or pattern """
    search_term = request.args.get('q', '').strip()
    if search_term:
        per_page = current_app.config["WHEELODEX_SEARCH_RESULTS_PER_PAGE"]
        files_per_wheel \
            = current_app.config["WHEELODEX_FILE_SEARCH_RESULTS_PER_WHEEL"]
        ### TODO: Limit to the latest data-having version of each project?
        q = db.session.query(Wheel, array_agg(File.path))\
                      .join(WheelData, Wheel.data)\
                      .join(File, WheelData.files)\
                      .group_by(Wheel)\
                      .order_by(Wheel.filename)
        ### TODO: Order by normalized project name before wheel filename
        if '*' in search_term or '?' in search_term:
            q = q.filter(File.path.ilike(glob2like(search_term), escape='\\'))
        else:
            q = q.filter(
                (db.func.lower(File.path) == db.func.lower(search_term))
                | (File.path.ilike('%/'+like_escape(search_term), escape='\\'))
            )
        results = q.paginate(per_page=per_page)
    else:
        results = None
    return render_template(
        'search_files.html',
        search_term     = search_term,
        results         = results,
        files_per_wheel = files_per_wheel,
    )

@web.route('/search/modules/')
def search_modules():
    """
    Search for wheels containing Python modules with a given name or pattern
    """
    search_term = request.args.get('q', '').strip()
    if search_term:
        per_page = current_app.config["WHEELODEX_SEARCH_RESULTS_PER_PAGE"]
        ### TODO: Limit to the latest data-having version of each project?
        q = db.session.query(Project, Wheel, Module)\
                      .join(Version, Project.versions)\
                      .join(Wheel, Version.wheels)\
                      .join(WheelData, Wheel.data)\
                      .join(Module, WheelData.modules)
        if '*' in search_term or '?' in search_term:
            q = q.filter(Module.name.ilike(glob2like(search_term), escape='\\'))
        else:
            q = q.filter(db.func.lower(Module.name)==db.func.lower(search_term))
        ### TODO: Order results by something?
        results = q.paginate(per_page=per_page)
    else:
        results = None
    return render_template(
        'search_modules.html',
        search_term = search_term,
        results     = results,
    )

@web.route('/search/commands/')
def search_commands():
    """ Search for wheels defining a given ``console_scripts`` command """
    search_term = request.args.get('q', '').strip()
    if search_term:
        per_page = current_app.config["WHEELODEX_SEARCH_RESULTS_PER_PAGE"]
        group = EntryPointGroup.query.filter(
            EntryPointGroup.name == 'console_scripts'
        ).first_or_404()
        ### TODO: Limit to the latest data-having version of each project?
        q = db.session.query(Project, Wheel, EntryPoint)\
                      .join(Version, Project.versions)\
                      .join(Wheel, Version.wheels)\
                      .join(WheelData, Wheel.data)\
                      .join(EntryPoint, WheelData.entry_points)\
                      .filter(EntryPoint.group_id == group.id)
        if '*' in search_term or '?' in search_term:
            q = q.filter(
                EntryPoint.name.ilike(glob2like(search_term), escape='\\')
            )
        else:
            q = q.filter(
                db.func.lower(EntryPoint.name) == db.func.lower(search_term)
            )
        results = q.order_by(EntryPoint.name.asc()).paginate(per_page=per_page)
    else:
        results = None
    return render_template(
        'search_commands.html',
        search_term = search_term,
        results     = results,
    )

@web.route('/json/projects/<project>')
@project_view
def project_json(project):
    """
    A JSON view of the names of all known wheels (with links) for the given
    project and whether they have data, organized by version
    """
    response = OrderedDict()
    for v, wheels in project.versions_wheels_grid():
        lst = []
        for w,d in wheels:
            lst.append({
                "filename": w.filename,
                "has_data": d,
                "href": url_for('.wheel_json', wheel=w.filename),
            })
        response[v] = lst
    return jsonify(response)

@web.route('/json/projects/<project>/data')
@project_view
def project_data_json(project):
    """ A JSON view of the data for a given project's best wheel """
    ### TODO: Should this use preferred_wheel instead?  The URL does say
    ### "data"...
    whl = project.best_wheel
    if whl is not None:
        return jsonify(whl.as_json())
    else:
        return json_response(
            {"message": "No wheels found for project"},
            status_code=404,
        )

@web.route('/json/projects/<project>/rdepends')
@project_view
def project_rdepends_json(project):
    """ A JSON view of the reverse dependencies for a project """
    per_page = current_app.config["WHEELODEX_RDEPENDS_PER_PAGE"]
    rdeps = rdepends_query(project).order_by(Project.name.asc())\
                                   .paginate(per_page=per_page)
    return jsonify({
        "items": [{
            "name": proj.display_name,
            "href": url_for('.project_json', project=proj.name),
        } for proj in rdeps.items],
        "total": rdeps.total,
        "links": {
            "next": url_for(
                '.project_rdepends_json',
                project = project.name,
                page    = rdeps.next_num,
            ) if rdeps.has_next else None,
            "prev": url_for(
                '.project_rdepends_json',
                project = project.name,
                page    = rdeps.prev_num,
            ) if rdeps.has_prev else None,
        },
    })

@web.route('/json/wheels/<wheel>.json')
def wheel_json(wheel):
    """ A JSON view of the data for a given wheel """
    whl = db.session.query(Wheel).filter(Wheel.filename == wheel).first_or_404()
    return jsonify(whl.as_json())
