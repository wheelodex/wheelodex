from   flask           import Blueprint, current_app, jsonify, render_template
from   packaging.utils import canonicalize_name as normalize
import sqlalchemy as S
from   .models         import EntryPoint, EntryPointGroup, Project, Version, \
                                Wheel, WheelData, db, dependency_tbl

web = Blueprint('web', __name__)

from . import macros  # noqa

@web.route('/')
@web.route('/index.html')
def index():
    whl_qty = db.session.query(WheelData).count()
    epg_qty = db.session.query(EntryPointGroup).count()
    return render_template('index.html', whl_qty=whl_qty, epg_qty=epg_qty)

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

@web.route('/json/wheels/<wheel>.json')
def wheel_json(wheel):
    whl = db.session.query(Wheel).filter(Wheel.filename == wheel).first_or_404()
    return jsonify(whl.as_json())

@web.route('/<wheel>.html')
def wheel_data(wheel):
    whl = db.session.query(Wheel).filter(Wheel.filename == wheel + '.whl')\
                    .first_or_404()
    return render_template('wheel_data.html', whl=whl)

@web.route('/projects/<name>/')
def project(name):
    p = db.session.query(Project).filter(Project.name == normalize(name))\
                  .first_or_404()
    whl = p.preferred_wheel
    if whl is not None:
        return render_template('wheel_data.html', whl=whl)
    else:
        return 'No data available'

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
