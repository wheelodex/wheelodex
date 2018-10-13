""" Flask views """

from   collections     import OrderedDict
from   functools       import wraps
import re
from   flask           import Blueprint, current_app, jsonify, redirect, \
                                render_template, request, url_for
from   packaging.utils import canonicalize_name as normalize
from   .dbutil         import rdepends_query
from   .models         import EntryPoint, EntryPointGroup, File, Project, \
                                Version, Wheel, WheelData, db
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

@web.route('/')
@web.route('/index.html')
def index():
    """ The main page """
    proj_qty = db.session.query(db.func.count(Project.id.distinct()))\
                         .join(Version).join(Wheel).join(WheelData).scalar()
    whl_qty = db.session.query(WheelData).count()
    ### TODO: Don't count entry point groups without entry points:
    epg_qty = db.session.query(EntryPointGroup).count()
    return render_template(
        'index.html',
        proj_qty = proj_qty,
        whl_qty  = whl_qty,
        epg_qty  = epg_qty,
    )

@web.route('/projects/')
def project_list():
    """
    A list of all projects with wheels with data, along with summaries
    extracted from those wheels
    """
    per_page = current_app.config["WHEELODEX_PROJECTS_PER_PAGE"]
    ### TODO: Speed up this query!
    subq = db.session.query(
        Project.name,
        Project.display_name,
        WheelData.summary,
        db.func.ROW_NUMBER().over(
            partition_by=Project.id,
            order_by=(Version.ordering.desc(), Wheel.ordering.desc()),
        ).label('rownum'),
    ).join(Version).join(Wheel).join(WheelData)\
     .order_by(Project.name.asc())\
     .cte()
    # The query needs to be converted to a CTE with the ORDER BY on the inside
    # and paginate's LIMIT on the outside; otherwise, PostgreSQL's notorious
    # optimization problems with ORDER BY + LIMIT will kick in, and the query
    # will take two and a half minutes to run.
    projects = db.session.query(subq.c.name,subq.c.display_name,subq.c.summary)\
                         .filter(subq.c.rownum == 1)\
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
    return render_template(
        'wheel_data.html',
        whl          = whl,
        project      = project,
        rdepends_qty = rdepends_query(project).count(),
        all_wheels   = project.versions_wheels_grid(),
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
        project  = project.display_name,
        rdepends = rdeps,
    )

@web.route('/entry-points/')
def entry_point_groups():
    """
    A list of all entry point groups (excluding those without any entry points)
    """
    per_page = current_app.config["WHEELODEX_ENTRY_POINT_GROUPS_PER_PAGE"]
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
                            db.func.count(),
                        )\
                       .join(subq, EntryPointGroup.id == subq.c.group_id)\
                       .group_by(EntryPointGroup)\
                       .order_by(EntryPointGroup.name.asc())\
                       .paginate(per_page=per_page)
    return render_template('entry_point_groups.html', groups=groups)

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

@web.route('/search/projects')
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
    search_term = request.args.get('q', '')
    if search_term:
        per_page = current_app.config["WHEELODEX_SEARCH_RESULTS_PER_PAGE"]
        normterm = re.sub(r'[-_.]+', '-', search_term.lower())
        if '*' in normterm or '?' in normterm:
            q = Project.query.filter(Project.name.like(glob2like(normterm)))
        else:
            p = Project.query.filter(Project.name == normterm).one_or_none()
            if p is not None:
                return redirect(url_for('.project', project=normterm), code=307)
            else:
                q = Project.query.filter(
                    Project.name.like(like_escape(normterm) + '%')
                )
        results = q.order_by(Project.name.asc()).paginate(per_page=per_page)
    else:
        results = None
    return render_template(
        'search_projects.html',
        search_term = search_term,
        results     = results,
    )

@web.route('/search/files')
def search_files():
    """ Search for wheels containing files with a given name or pattern """
    search_term = request.args.get('q', '')
    if search_term:
        per_page = current_app.config["WHEELODEX_SEARCH_RESULTS_PER_PAGE"]
        q = db.session.query(Project, Wheel, File)\
                      .join(Version).join(Wheel).join(WheelData).join(File)
        if '*' in search_term or '?' in search_term:
            q = q.filter(File.path.ilike(glob2like(search_term)))
        else:
            q = q.filter(
                (File.path == search_term)
                | (File.path.ilike('%/' + like_escape(search_term)))
            )
        ### TODO: Order results by something?
        results = q.paginate(per_page=per_page)
    else:
        results = None
    return render_template(
        'search_files.html',
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
