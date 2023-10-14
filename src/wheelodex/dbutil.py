"""
Utility functions for working with the database.

All of these functions require a Flask application context with a database
connection to be in effect.
"""

from __future__ import annotations
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import logging
from os.path import join
from typing import cast
from flask import current_app
from flask_sqlalchemy.session import Session
from packaging.utils import canonicalize_name as normalize
from packaging.utils import canonicalize_version as normversion
import sqlalchemy as sa
from sqlalchemy.orm import scoped_session, with_parent
from .models import (
    DependencyRelation,
    OrphanWheel,
    Project,
    PyPISerial,
    Version,
    Wheel,
    WheelData,
    db,
)
from .util import parse_timestamp, version_sort_key
from .wheel_sort import wheel_sort_key

log = logging.getLogger(__name__)


@contextmanager
def dbcontext() -> Iterator[scoped_session[Session]]:
    """
    A context manager that yields the current application's database session,
    commits on success, and rolls back on error
    """
    try:
        yield db.session
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    finally:
        db.session.close()


def get_serial() -> int | None:
    """Returns the serial ID of the last seen PyPI event"""
    ps = db.session.scalars(db.select(PyPISerial)).one_or_none()
    return ps and ps.serial


def set_serial(value: int) -> None:
    """
    Advances the serial ID of the last seen PyPI event to ``value``.  If
    ``value`` is less than the currently-stored serial, no change is made.
    """
    ps = db.session.scalars(db.select(PyPISerial)).one_or_none()
    if ps is None:
        db.session.add(PyPISerial(serial=value))
    else:
        ps.serial = max(ps.serial, value)


def add_wheel(
    version: Version,
    filename: str,
    url: str,
    size: int,
    md5: str | None,
    sha256: str | None,
    uploaded: str,
) -> Wheel:
    """
    Registers a wheel for the given `Version` and updates the ``ordering``
    values for the `Version`'s `Wheel`\\s.  The new `Wheel` object is returned.
    If a wheel with the given filename is already registered, no change is made
    to the database, and the already-registered wheel is returned.
    """
    whl = db.session.scalars(
        db.select(Wheel).filter_by(filename=filename)
    ).one_or_none()
    if whl is None:
        whl = Wheel(
            version=version,
            filename=filename,
            url=url,
            size=size,
            md5=md5,
            sha256=sha256,
            uploaded=parse_timestamp(uploaded),
        )
        db.session.add(whl)
        for i, w in enumerate(
            ### TODO: Is `version.wheels` safe to use when some of its elements
            ### may have been deleted earlier in the transaction?
            sorted(version.wheels, key=lambda x: wheel_sort_key(x.filename))
        ):
            w.ordering = i
        version.project.has_wheels = True
    return whl


def add_wheel_from_json(about: dict) -> None:
    """
    Add a wheel (possibly with data) from a structure produced by
    `Wheel.as_json()`
    """
    version = add_version(
        about["pypi"].pop("project"),
        about["pypi"].pop("version"),
    )
    whl = add_wheel(version, **about["pypi"])
    if "data" in about and whl.data is None:
        whl.set_data(about["data"])
        assert whl.data is not None
        whl.data.processed = parse_timestamp(about["wheelodex"]["processed"])  # type: ignore[unreachable]
        whl.data.wheel_inspect_version = about["wheelodex"]["wheel_inspect_version"]


def iterqueue(max_wheel_size: int | None = None) -> Sequence[Wheel]:
    """
    Returns the "queue" of wheels to process: a list of all wheels with neither
    data nor errors for the latest nonempty (i.e., having wheels) version of
    each project

    :param int max_wheel_size: If set, only wheels this size or smaller are
        returned
    """
    subq = (
        db.select(Project.id, db.func.max(Version.ordering).label("max_order"))
        .join(Version)
        .join(Wheel)
        .group_by(Project.id)
        .subquery()
    )
    q = (
        db.select(Wheel)
        .join(Version)
        .join(Project)
        .join(subq, (Project.id == subq.c.id) & (Version.ordering == subq.c.max_order))
        .filter(~Wheel.data.has())
        .filter(~Wheel.errors.any())
    )
    if max_wheel_size is not None:
        q = q.filter(Wheel.size <= max_wheel_size)
    ### TODO: Would leaving off the ".all()" give an iterable that plays well
    ### with wheels being given data concurrently?
    return db.session.scalars(q).all()


def remove_wheel(filename: str) -> None:
    """
    Delete all `Wheel`\\s and `OrphanWheel`\\s with the given filename from the
    database
    """
    db.session.execute(db.delete(Wheel).where(Wheel.filename == filename))
    db.session.execute(db.delete(OrphanWheel).where(OrphanWheel.filename == filename))
    p = get_project(filename.split("-")[0])
    if p is not None:
        update_has_wheels(p)


def add_project(name: str) -> Project:
    """
    Create a `Project` with the given name and return it.  If there already
    exists a project with the same name (after normalization), do nothing and
    return that instead.
    """
    return Project.from_name(name)


def get_project(name: str) -> Project | None:
    """
    Return the `Project` with the given name (*modulo* normalization), or
    `None` if there is no such project
    """
    return db.session.scalars(
        db.select(Project).filter_by(name=normalize(name))
    ).one_or_none()


def remove_project(project: str) -> None:
    """
    Delete all `Version`\\s (and `Wheel`\\s etc.) for the `Project` with the
    given name (*modulo* normalization).  The `Project` entry itself is
    retained in case it's still referenced as a dependency of other projects.
    """
    # Note that this filters by PyPI project, not by wheel filename project, as
    # this method is meant to be called in response to "remove" events in the
    # PyPI changelog.
    p = get_project(project)
    if p is not None:
        db.session.execute(db.delete(Version).where(Version.project == p))
        p.has_wheels = False


def add_version(project: str | Project, version: str) -> Version:
    """
    Create a `Version` with the given project & version string and return it;
    the ``ordering`` values for the project's `Version`\\s are updated as well.
    If there already exists a version with the same details, do nothing and
    return that instead.
    """
    if isinstance(project, str):
        project = add_project(project)
    vnorm = normversion(version)
    v = db.session.scalars(
        db.select(Version).filter_by(project=project, name=vnorm)
    ).one_or_none()
    if v is None:
        v = Version(project=project, name=vnorm, display_name=version)
        db.session.add(v)
        for i, u in enumerate(
            ### TODO: Is `project.versions` safe to use when some of its
            ### elements may have been deleted earlier in the transaction?
            sorted(project.versions, key=lambda x: version_sort_key(x.name))
        ):
            u.ordering = i
    return v


def get_version(project: str | Project, version: str) -> Version | None:
    """
    Return the `Version` with the given project and version string (*modulo*
    canonicalization), or `None` if there is no such version
    """
    if isinstance(project, str):
        p = get_project(project)
    else:
        p = project
    if p is None:
        return None
    return db.session.scalars(
        db.select(Version).filter_by(project=p, name=normversion(version))
    ).one_or_none()


def remove_version(project: str, version: str) -> None:
    """
    Delete the `Version` (and `Wheel`\\s etc.) for the given project and
    version string
    """
    # Note that this filters by PyPI project & version, not by wheel filename
    # project & version, as this method is meant to be called in response to
    # "remove" events in the PyPI changelog.
    p = get_project(project)
    if p is not None:
        db.session.execute(
            db.delete(Version)
            .where(Version.project == p)
            .where(Version.name == normversion(version))
        )
        update_has_wheels(p)


def purge_old_versions() -> None:
    """
    For each project, keep (a) the latest version, (b) the latest version with
    wheels registered, and (c) the latest version with wheel data, and delete
    all other versions.
    """
    log.info("BEGIN purge_old_versions")
    start_time = datetime.now(timezone.utc)
    purged = 0
    for p in db.session.scalars(
        db.select(Project)
        .join(Version)
        .group_by(Project)
        .having(db.func.count(Version.id) > 1)
    ):
        latest = latest_wheel = latest_data = None
        for v, vwheels, vdata in db.session.execute(
            # This queries the versions of project `p`, along with the number
            # of wheels each version has and the number of wheels with data
            # each has:
            db.select(
                Version,
                db.func.count(Wheel.id),
                db.func.count(WheelData.id),
            )
            .join_from(Version, Wheel, isouter=True)
            .join_from(Wheel, WheelData, isouter=True)
            .where(with_parent(p, Project.versions))
            .group_by(Version)
            .order_by(Version.ordering.desc())
        ):
            keep = False
            if latest is None:
                log.debug(
                    "Project %s: keeping latest version: %s",
                    p.display_name,
                    v.display_name,
                )
                latest = v
                keep = True
            if vwheels and latest_wheel is None:
                log.debug(
                    "Project %s: keeping latest version with wheels: %s",
                    p.display_name,
                    v.display_name,
                )
                latest_wheel = v
                keep = True
            if vdata and latest_data is None:
                log.debug(
                    "Project %s: keeping latest version with data: %s",
                    p.display_name,
                    v.display_name,
                )
                latest_data = v
                keep = True
            if not keep:
                log.info(
                    "Project %s: deleting version %s", p.display_name, v.display_name
                )
                db.session.delete(v)
                purged += 1
    end_time = datetime.now(timezone.utc)
    log_dir = current_app.config.get("WHEELODEX_STATS_LOG_DIR")
    if log_dir is not None:
        with open(join(log_dir, "purge_old_versions.log"), "a", encoding="utf-8") as fp:
            print(
                json.dumps(
                    {
                        "op": "purge_old_versions",
                        "start": str(start_time),
                        "end": str(end_time),
                        "purged": purged,
                    }
                ),
                file=fp,
            )
    log.info("END purge_old_versions")


def add_orphan_wheel(version: Version, filename: str, uploaded_epoch: int) -> None:
    """
    Register an `OrphanWheel` for the given version, with the given filename,
    uploaded at ``uploaded_epoch`` seconds after the Unix epoch.  If an orphan
    wheel with the given filename has already been registered, update its
    ``uploaded`` timestamp and do nothing else.
    """
    uploaded = datetime.fromtimestamp(uploaded_epoch, timezone.utc)
    whl = db.session.scalars(
        db.select(OrphanWheel).filter_by(filename=filename)
    ).one_or_none()
    if whl is None:
        whl = OrphanWheel(version=version, filename=filename, uploaded=uploaded)
        db.session.add(whl)
    else:
        # If they keep uploading the wheel, keep checking the JSON API for it.
        whl.uploaded = uploaded


def rdepends_query(project: Project) -> sa.Select:
    """
    Returns a query object that returns all `Project`\\s that depend on the
    given `Project`, ordered by name.
    """
    ### TODO: Use preferred wheel?
    return cast(
        sa.Select,
        db.select(Project)
        .filter(
            db.exists()
            .where(Project.id == DependencyRelation.source_project_id)
            .where(DependencyRelation.project_id == project.id)
            .select()
            .scalar_subquery()
        )
        .order_by(Project.name.asc()),
    )


def rdepends_count(project: Project) -> int:
    """
    Returns the number of `Project`\\s that depend on the given `Project`
    """
    ### TODO: Use preferred wheel?
    r = db.session.scalar(
        db.select(db.func.count(Project.id)).filter(
            db.exists()
            .where(Project.id == DependencyRelation.source_project_id)
            .where(DependencyRelation.project_id == project.id)
            .select()
            .scalar_subquery()
        )
    )
    assert isinstance(r, int)
    return r


def update_has_wheels(project: Project) -> None:
    """Update the value of the given `Project`'s ``has_wheels`` attribute"""
    project.has_wheels = db.session.execute(
        db.exists()
        .where(Version.project_id == project.id)
        .where(Wheel.version_id == Version.id)
        .select()
    ).scalar()
