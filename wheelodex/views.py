from   collections     import OrderedDict
from   flask           import Blueprint, current_app, jsonify, \
                                render_template, url_for
from   packaging.utils import canonicalize_name as normalize
import sqlalchemy as S
from   .models         import EntryPoint, EntryPointGroup, Project, Version, \
                                Wheel, WheelData, db, dependency_tbl
from   .util           import json_response

web = Blueprint('web', __name__)

from . import macros  # noqa

@web.route('/')
@web.route('/index.html')
def index():
    proj_qty = db.session.query(db.func.count(Project.id.distinct()))\
                         .join(Version).join(Wheel).join(WheelData).scalar()
    whl_qty = db.session.query(WheelData).count()
    epg_qty = db.session.query(EntryPointGroup).count()
    return render_template(
        'index.html',
        proj_qty = proj_qty,
        whl_qty  = whl_qty,
        epg_qty  = epg_qty,
    )

@web.route('/wheels.html')
def wheel_list():
    per_page = current_app.config["WHEELODEX_WHEELS_PER_PAGE"]
    wheels = db.session.query(Wheel).join(Version).join(Project)\
                       .filter(Wheel.data.has())\
                       .order_by(
                            Project.name.asc(),
                            Version.ordering.asc(),
                            Wheel.ordering.desc(),
                       ).paginate(per_page=per_page)
    return render_template('wheel_list.html', wheels=wheels)

@web.route('/<wheel>.html')
def wheel_data(wheel):
    whl = db.session.query(Wheel).filter(Wheel.filename == wheel + '.whl')\
                    .first_or_404()
    return render_template('wheel_data.html', whl=whl)

@web.route('/projects/')
def project_list():
    per_page = current_app.config["WHEELODEX_PROJECTS_PER_PAGE"]
    subq1 = db.session.query(
        Version.id,
        Version.project_id,
        Version.ordering,
        db.func.max(Wheel.ordering).label('max_wheel'),
    ).join(Wheel).join(WheelData).group_by(Version.id).subquery()
    subq2 = db.session.query(
        subq1.c.project_id,
        db.func.max(subq1.c.ordering).label('max_version'),
    ).group_by(subq1.c.project_id).subquery()
    q = db.session.query(Project.name, Project.display_name, WheelData.summary)\
                  .join(Version)\
                  .join(subq2, (Project.id == subq2.c.project_id)
                         & (Version.ordering == subq2.c.max_version))\
                  .join(Wheel)\
                  .join(subq1, (Version.id == subq1.c.id)
                         & (Wheel.ordering == subq1.c.max_wheel))\
                  .join(WheelData)\
                  .order_by(Project.name.asc())\
                  .cte()
    # The query needs to be converted to a CTE with the ORDER BY on the inside
    # and paginate's LIMIT on the outside; otherwise, PostgreSQL's notorious
    # optimization problems with ORDER BY + LIMIT will kick in, and the query
    # will take two and a half minutes to run.
    projects = db.session.query(q).paginate(per_page=per_page)
    return render_template('project_list.html', projects=projects)

@web.route('/projects/<name>/')
def project(name):
    p = db.session.query(Project).filter(Project.name == normalize(name))\
                  .first_or_404()
    whl = p.best_wheel
    if whl is not None:
        return render_template(
            'wheel_data.html',
            whl        = whl,
            all_wheels = p.versions_wheels_grid(),
        )
    else:
        return render_template('project_nowheel.html', project=p)

@web.route('/projects/<name>/rdepends/')
def rdepends(name):
    per_page = current_app.config["WHEELODEX_RDEPENDS_PER_PAGE"]
    p = db.session.query(Project).filter(Project.name == normalize(name))\
                  .first_or_404()
    subq = db.session.query(WheelData).join(dependency_tbl).join(Project)\
                     .filter(Project.id == p.id).subquery()
    ### TODO: Use preferred wheel:
    rdeps = db.session.query(Project).join(Version).join(Wheel).join(subq)\
                      .group_by(Project)\
                      .order_by(Project.name.asc())\
                      .paginate(per_page=per_page)
    return render_template(
        'rdepends.html',
        project  = p.display_name,
        rdepends = rdeps,
    )

@web.route('/entry-points/')
def entry_point_list():
    per_page = current_app.config["WHEELODEX_ENTRY_POINT_GROUPS_PER_PAGE"]
    # Omission of groups for which no entry points are defined is intentional.
    ### TODO: Use preferred wheel:
    groups = db.session.query(EntryPointGroup.name,S.func.COUNT(EntryPoint.id))\
                       .join(EntryPoint)\
                       .group_by(EntryPointGroup)\
                       .order_by(EntryPointGroup.name.asc())\
                       .paginate(per_page=per_page)
    return render_template('entry_point_list.html', groups=groups)

@web.route('/entry-points/<group>/')
def entry_point(group):
    ep_group = db.session.query(EntryPointGroup)\
                         .filter(EntryPointGroup.name == group)\
                         .first_or_404()
    per_page = current_app.config["WHEELODEX_ENTRY_POINTS_PER_PAGE"]
    ### TODO: Use preferred wheel:
    project_eps = db.session.query(Project.display_name, EntryPoint.name)\
                            .join(Version).join(Wheel).join(WheelData)\
                            .join(EntryPoint)\
                            .filter(EntryPoint.group == ep_group)\
                            .order_by(
                                Project.name.asc(), EntryPoint.name.asc()
                            ).paginate(per_page=per_page)
    return render_template(
        'entry_point.html',
        ep_group    = ep_group,
        project_eps = project_eps,
    )

@web.route('/json/projects/<project>')
def project_json(project):
    """
    Returns the names of all known wheels (with links) for the given project
    and whether they have data, organized by version
    """
    p = db.session.query(Project).filter(Project.name == normalize(project))\
                  .first_or_404()
    response = OrderedDict()
    for v, wheels in p.versions_wheels_grid():
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
def project_data_json(project):
    """ Returns the JSON representation of the given project's best wheel """
    p = db.session.query(Project).filter(Project.name == normalize(project))\
                  .first_or_404()
    ### TODO: Should this use preferred_wheel instead?  The URL does say
    ### "data"...
    whl = p.best_wheel
    if whl is not None:
        return jsonify(whl.as_json())
    else:
        return json_response(
            {"message": "No wheels found for project"},
            status_code=404,
        )

@web.route('/json/wheels/<wheel>.json')
def wheel_json(wheel):
    whl = db.session.query(Wheel).filter(Wheel.filename == wheel).first_or_404()
    return jsonify(whl.as_json())
