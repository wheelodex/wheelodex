"""Flask views"""

from __future__ import annotations
import re
from typing import TypeAlias
from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from packaging.utils import canonicalize_name as normalize
from sqlalchemy.sql.functions import array_agg
from werkzeug.exceptions import HTTPException
from werkzeug.sansio.response import Response
from .models import (
    DependencyRelation,
    EntryPoint,
    EntryPointGroup,
    File,
    Module,
    Project,
    Version,
    Wheel,
    WheelData,
    db,
)
from .paginate_rows import paginate_rows
from .util import glob2like, like_escape

web = Blueprint("web", __name__)

from . import macros  # noqa

ResponseValue: TypeAlias = Response | str | tuple[Response, int]


def resolve_project(project: str) -> Project:
    normproj = normalize(project)
    if normproj != project:
        view_args = request.view_args or {}
        view_args["project"] = normproj
        assert request.endpoint is not None
        raise HTTPException(
            response=redirect(url_for(request.endpoint, **view_args), code=301)
        )
    else:
        p = db.first_or_404(db.select(Project).filter_by(name=normproj))
        assert isinstance(p, Project)
        return p


@web.route("/index.html")
@web.route("/")
def index() -> ResponseValue:
    """The main page"""
    return render_template(
        "index.html",
        proj_qty=db.session.scalar(
            db.select(db.func.count(Project.id)).filter(Project.has_wheels)
        ),
        whl_qty=db.session.scalar(db.select(db.func.count(Wheel.id))),
        # data_qty=db.session.scalar(db.select(db.func.count(WheelData.id))),
    )


@web.route("/robots.txt")
def robots_txt() -> ResponseValue:
    return make_response(
        (
            "User-agent: *\n"
            "Disallow: /entry-points/\n"
            "Disallow: /json/\n"
            "Disallow: /projects/\n"
            "Disallow: /rdepends-leaders/\n"
            "Disallow: /recent/\n"
            "Disallow: /search/\n"
        ),
        {"Content-Type": "text/plain; charset=utf-8"},
    )


@web.route("/about/")
def about() -> ResponseValue:
    """The "About" page"""
    return render_template("about.html")


@web.route("/json-api/")
def json_api() -> ResponseValue:
    """The "JSON API" page"""
    p = db.session.scalars(db.select(Project).filter_by(name="requests")).one_or_none()
    example_wheel = p and p.best_wheel
    return render_template("json_api.html", example_wheel=example_wheel)


@web.route("/random/")
def random_project() -> ResponseValue:
    """Redirect to a random project with wheels"""
    project = db.session.scalar(
        db.select(Project.name)
        .filter(Project.has_wheels)
        .order_by(db.func.random())
        .limit(1)
    )
    return redirect(url_for(".project", project=project), code=302)


@web.route("/recent/")
def recent_wheels() -> ResponseValue:
    """A list of recently-analyzed wheels"""
    qty = current_app.config["WHEELODEX_RECENT_WHEELS_QTY"]
    recents = db.session.execute(
        db.select(Project, Version, Wheel, WheelData)
        .join(Version, Project.versions)
        .join(Wheel, Version.wheels)
        .join(WheelData, Wheel.data)
        .order_by(WheelData.processed.desc())
        .limit(qty)
    )
    return render_template("recent_wheels.html", recents=recents)


@web.route("/rdepends-leaders/")
### TODO: Add caching
def rdepends_leaders() -> ResponseValue:
    qty = current_app.config["WHEELODEX_RDEPENDS_LEADERS_QTY"]
    q = db.session.execute(
        db.select(
            Project,
            db.func.count(DependencyRelation.source_project_id.distinct()).label("qty"),
        )
        .join(DependencyRelation, Project.id == DependencyRelation.project_id)
        .group_by(Project)
        .order_by(db.desc("qty"))
        .limit(qty)
    )
    return render_template("rdepends_leaders.html", leaders=q)


@web.route("/projects/")
def project_list() -> ResponseValue:
    """A list of all projects with wheels"""
    per_page = current_app.config["WHEELODEX_PROJECTS_PER_PAGE"]
    projects = db.paginate(
        db.select(Project).filter(Project.has_wheels).order_by(Project.name.asc()),
        per_page=per_page,
    )
    return render_template("project_list.html", projects=projects)


@web.route("/projects/<project>/")
def project(project: str) -> ResponseValue:
    """
    A display of the data for a given project, including its "best wheel"
    """
    p = resolve_project(project)
    rdeps_qty = p.rdepends_count()
    whl = p.best_wheel
    if whl is not None:
        return render_template(
            "wheel_data.html",
            whl=whl,
            project=p,
            rdepends_qty=rdeps_qty,
            all_wheels=p.versions_wheels_grid(),
            subpage=False,
        )
    else:
        return render_template(
            "project_nowheel.html", project=p, rdepends_qty=rdeps_qty
        )


@web.route("/projects/<project>/wheels/<wheel>/")
def wheel_data(project: str, wheel: str) -> ResponseValue:
    """
    A display of the data for a project, focused on a given wheel.  If the
    wheel is unknown, redirect to the project's main page.
    """
    p = resolve_project(project)
    whl = db.session.scalars(db.select(Wheel).filter_by(filename=wheel)).one_or_none()
    if whl is None:
        return redirect(url_for(".project", project=p.name), code=302)
    elif whl.project != p:
        abort(404)
    else:
        return render_template(
            "wheel_data.html",
            whl=whl,
            project=p,
            rdepends_qty=p.rdepends_count(),
            all_wheels=p.versions_wheels_grid(),
            subpage=True,
        )


@web.route("/projects/<project>/rdepends/")
def rdepends(project: str) -> ResponseValue:
    """A list of reverse dependencies for a project"""
    p = resolve_project(project)
    per_page = current_app.config["WHEELODEX_RDEPENDS_PER_PAGE"]
    rdeps = db.paginate(p.rdepends_query(), per_page=per_page)
    return render_template("rdepends.html", project=p, rdepends=rdeps)


@web.route("/entry-points/")
def entry_point_groups() -> ResponseValue:
    """
    A list of all entry point groups (excluding those without any entry points)
    """
    per_page = current_app.config["WHEELODEX_ENTRY_POINT_GROUPS_PER_PAGE"]
    sortby = request.args.get("sortby", "")
    ### TODO: Use preferred wheel (Alternatively, limit to the latest
    ### data-having version of each project):
    # The point of this subquery is to weed out duplicate
    # Project-EntryPoint.name pairs before counting.  There's probably a better
    # way to do this.
    subq = (
        db.select(EntryPoint.group_id)
        .join(WheelData)
        .join(Wheel)
        .join(Version)
        .join(Project)
        .group_by(EntryPoint.group_id, EntryPoint.name, Project.id)
        .subquery()
    )
    groups = (
        db.select(
            EntryPointGroup.name,
            EntryPointGroup.summary,
            db.func.count().label("qty"),
        )
        .join(subq, EntryPointGroup.id == subq.c.group_id)
        .group_by(EntryPointGroup)
    )
    if sortby == "qty":
        groups = groups.order_by(db.desc("qty"))
    else:
        groups = groups.order_by(EntryPointGroup.name.asc())
    groups = paginate_rows(groups, per_page=per_page)
    return render_template("entry_point_groups.html", groups=groups, sortby=sortby)


@web.route("/entry-points/<group>/")
def entry_point(group: str) -> ResponseValue:
    """
    A list of all entry points in a given group and the packages that define
    them
    """
    ep_group = db.first_or_404(db.select(EntryPointGroup).filter_by(name=group))
    per_page = current_app.config["WHEELODEX_ENTRY_POINTS_PER_PAGE"]
    ### TODO: Use preferred wheel (Alternatively, limit to the latest
    ### data-having version of each project):
    project_eps = paginate_rows(
        db.select(Project, EntryPoint.name)
        .join(Version)
        .join(Wheel)
        .join(WheelData)
        .join(EntryPoint)
        .filter(EntryPoint.group == ep_group)
        .group_by(Project, EntryPoint.name)
        .order_by(Project.name.asc(), EntryPoint.name.asc()),
        per_page=per_page,
    )
    return render_template(
        "entry_point.html",
        ep_group=ep_group,
        project_eps=project_eps,
    )


@web.route("/search/projects/")
def search_projects() -> ResponseValue:
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
    search_term = request.args.get("q", "").strip()
    if search_term:
        per_page = current_app.config["WHEELODEX_SEARCH_RESULTS_PER_PAGE"]
        normterm = re.sub(r"[-_.]+", "-", search_term.lower())
        # Only search projects that have wheels:
        q = db.select(Project).filter(Project.has_wheels)
        if "*" in normterm or "?" in normterm:
            q = q.filter(Project.name.like(glob2like(normterm), escape="\\"))
        elif db.session.scalars(q.filter_by(name=normterm)).one_or_none() is not None:
            return redirect(url_for(".project", project=normterm), code=307)
        else:
            q = q.filter(Project.name.like(like_escape(normterm) + "%", escape="\\"))
        results = db.paginate(q.order_by(Project.name.asc()), per_page=per_page)
    else:
        results = None
    return render_template(
        "search_projects.html",
        search_term=search_term,
        results=results,
    )


@web.route("/search/files/")
def search_files() -> ResponseValue:
    """Search for wheels containing files with a given name or pattern"""
    search_term = request.args.get("q", "").strip()
    if search_term:
        per_page = current_app.config["WHEELODEX_SEARCH_RESULTS_PER_PAGE"]
        files_per_wheel = current_app.config["WHEELODEX_FILE_SEARCH_RESULTS_PER_WHEEL"]
        ### TODO: Limit to the latest data-having version of each project?
        q = (
            db.select(Wheel, array_agg(File.path))
            .join(WheelData, Wheel.data)
            .join(File, WheelData.files)
            .group_by(Wheel)
            .order_by(Wheel.filename)
        )
        ### TODO: Order by normalized project name before wheel filename
        if "*" in search_term or "?" in search_term:
            q = q.filter(File.path.ilike(glob2like(search_term), escape="\\"))
        else:
            q = q.filter(
                (db.func.lower(File.path) == db.func.lower(search_term))
                | (File.path.ilike("%/" + like_escape(search_term), escape="\\"))
            )
        results = paginate_rows(q, per_page=per_page)
    else:
        results = None
    return render_template(
        "search_files.html",
        search_term=search_term,
        results=results,
        files_per_wheel=files_per_wheel,
    )


@web.route("/search/modules/")
def search_modules() -> ResponseValue:
    """
    Search for wheels containing Python modules with a given name or pattern
    """
    search_term = request.args.get("q", "").strip()
    if search_term:
        per_page = current_app.config["WHEELODEX_SEARCH_RESULTS_PER_PAGE"]
        ### TODO: Limit to the latest data-having version of each project?
        q = (
            db.select(Project, Wheel, Module)
            .join(Version, Project.versions)
            .join(Wheel, Version.wheels)
            .join(WheelData, Wheel.data)
            .join(Module, WheelData.modules)
        )
        if "*" in search_term or "?" in search_term:
            q = q.filter(Module.name.ilike(glob2like(search_term), escape="\\"))
        else:
            q = q.filter(db.func.lower(Module.name) == db.func.lower(search_term))
        ### TODO: Order results by something?
        results = paginate_rows(q, per_page=per_page)
    else:
        results = None
    return render_template(
        "search_modules.html",
        search_term=search_term,
        results=results,
    )


@web.route("/search/commands/")
def search_commands() -> ResponseValue:
    """Search for wheels defining a given ``console_scripts`` command"""
    search_term = request.args.get("q", "").strip()
    if search_term:
        per_page = current_app.config["WHEELODEX_SEARCH_RESULTS_PER_PAGE"]
        group = db.first_or_404(
            db.select(EntryPointGroup).filter_by(name="console_scripts")
        )
        ### TODO: Limit to the latest data-having version of each project?
        q = (
            db.select(Project, Wheel, EntryPoint)
            .join(Version, Project.versions)
            .join(Wheel, Version.wheels)
            .join(WheelData, Wheel.data)
            .join(EntryPoint, WheelData.entry_points)
            .filter(EntryPoint.group_id == group.id)
        )
        if "*" in search_term or "?" in search_term:
            q = q.filter(EntryPoint.name.ilike(glob2like(search_term), escape="\\"))
        else:
            q = q.filter(db.func.lower(EntryPoint.name) == db.func.lower(search_term))
        results = paginate_rows(q.order_by(EntryPoint.name.asc()), per_page=per_page)
    else:
        results = None
    return render_template(
        "search_commands.html",
        search_term=search_term,
        results=results,
    )


@web.route("/json/projects/<project>")
def project_json(project: str) -> ResponseValue:
    """
    A JSON view of the names of all known wheels (with links) for the given
    project and whether they have data, organized by version
    """
    p = resolve_project(project)
    response = {}
    for v, wheels in p.versions_wheels_grid():
        lst = []
        for w, d in wheels:
            lst.append(
                {
                    "filename": w.filename,
                    "has_data": d,
                    "href": url_for(".wheel_json", wheel=w.filename),
                }
            )
        response[v] = lst
    return jsonify(response)


@web.route("/json/projects/<project>/data")
def project_data_json(project: str) -> ResponseValue:
    """A JSON view of the data for a given project's best wheel"""
    ### TODO: Should this use preferred_wheel instead?  The URL does say
    ### "data"...
    p = resolve_project(project)
    whl = p.best_wheel
    if whl is not None:
        return jsonify(whl.as_json())
    else:
        return (jsonify({"message": "No wheels found for project"}), 404)


@web.route("/json/projects/<project>/rdepends")
def project_rdepends_json(project: str) -> ResponseValue:
    """A JSON view of the reverse dependencies for a project"""
    p = resolve_project(project)
    per_page = current_app.config["WHEELODEX_RDEPENDS_PER_PAGE"]
    rdeps = db.paginate(p.rdepends_query(), per_page=per_page)
    return jsonify(
        {
            "items": [
                {
                    "name": proj.display_name,
                    "href": url_for(".project_json", project=proj.name),
                }
                for proj in rdeps.items
            ],
            "total": rdeps.total,
            "links": {
                "next": (
                    url_for(
                        ".project_rdepends_json",
                        project=p.name,
                        page=rdeps.next_num,
                    )
                    if rdeps.has_next
                    else None
                ),
                "prev": (
                    url_for(
                        ".project_rdepends_json",
                        project=p.name,
                        page=rdeps.prev_num,
                    )
                    if rdeps.has_prev
                    else None
                ),
            },
        }
    )


@web.route("/json/wheels/<wheel>.json")
def wheel_json(wheel: str) -> ResponseValue:
    """A JSON view of the data for a given wheel"""
    whl = db.first_or_404(db.select(Wheel).filter_by(filename=wheel))
    return jsonify(whl.as_json())
