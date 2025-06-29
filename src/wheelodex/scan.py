"""Functions for scanning PyPI for wheels to register"""

from __future__ import annotations
from datetime import datetime, timezone
import logging
from .app import emit_json_log
from .changelog import (
    FileCreated,
    FileRemoved,
    ProjectCreated,
    ProjectRemoved,
    VersionCreated,
    VersionRemoved,
)
from .dbutil import remove_wheel
from .models import OrphanWheel, Project, PyPISerial
from .pypi_api import PyPIAPI
from .util import latest_version

log = logging.getLogger(__name__)


def scan_pypi() -> None:
    """
    Use PyPI's XML-RPC and JSON APIs to find & register all wheels for the
    latest version of every project on PyPI.  The database's serial ID is also
    set to PyPI's current value as of the start of the function.

    This function requires a Flask application context with a database
    connection to be in effect.

    .. warning::

        There is a potential for Wheelodex's database to get out of sync with
        PyPI if `scan_pypi()` is run when one or more "remove" actions have
        transpired on PyPI since the last-seen changelog event.  It is
        recommended to only call this function either when no calls to
        `scan_pypi()` or `scan_changelog()` have been made yet or immediately
        after a call to `scan_changelog()`.
    """
    log.info("BEGIN scan_pypi")
    start_time = datetime.now(timezone.utc)
    total_queued = 0
    pypi = PyPIAPI()
    try:
        serial = pypi.changelog_last_serial()
        log.info("changlog_last_serial() = %d", serial)
        PyPISerial.set(serial)
        for pkg in pypi.list_packages():
            log.info("Adding wheels for project %r", pkg)
            project = Project.ensure(pkg)
            data = pypi.project_data(pkg)
            if data is None or not data.releases:
                log.info("Project has no releases")
                continue
            versions = list(data.releases.keys())
            log.debug("Available versions: %r", versions)
            latest = latest_version(versions)
            assert latest is not None
            log.info("Using latest version: %r", latest)
            qty_queued = 0
            vobj = project.ensure_version(latest)
            for asset in data.releases[latest]:
                if not asset.filename.lower().endswith(".whl"):
                    log.debug("Asset %s: not a wheel; skipping", asset.filename)
                else:
                    log.debug("Asset %s: adding", asset.filename)
                    qty_queued += 1
                    total_queued += 1
                    vobj.ensure_wheel(
                        filename=asset.filename,
                        url=asset.url,
                        size=asset.size,
                        md5=asset.digests.md5,
                        sha256=asset.digests.sha256,
                        uploaded=asset.upload_time,
                    )
            log.info("%s: %d wheels added", pkg, qty_queued)
    except Exception:
        ok = False
        raise
    else:
        ok = True
    finally:
        end_time = datetime.now(timezone.utc)
        ### TODO: Also log projects and versions added?
        ### TODO: Distinguish between actually new wheels and wheels that were
        ### already in the system?
        emit_json_log(
            "scan_pypi.log",
            {
                "op": "scan_pypi",
                "start": str(start_time),
                "end": str(end_time),
                "duration": str(end_time - start_time),
                "wheels_added": total_queued,
                "success": ok,
            },
        )
        log.info("END scan_pypi")


def scan_changelog(since: int) -> None:
    """
    Use PyPI's XML-RPC and JSON APIs to update the wheel registry based on all
    events that have happened on PyPI since serial ID ``since``.  The
    database's serial ID is also set to PyPI's current value as of the start of
    the function.

    This function requires a Flask application context with a database
    connection to be in effect.
    """
    log.info("BEGIN scan_changelog(%d)", since)
    start_time = datetime.now(timezone.utc)
    pypi = PyPIAPI()
    ### TODO: Distinguish between objects that are actually being added/removed
    ### and those that were already present/absent from the system?
    ### TODO: Don't count objects (including orphan wheels) added that are then
    ### removed by the end of the run?
    wheels_added = 0
    orphans_added = 0
    wheels_removed = 0
    projects_added = 0
    projects_removed = 0
    versions_added = 0
    versions_removed = 0

    try:
        ps = PyPISerial.ensure(since)
        for event in pypi.changelog_since_serial(since):
            log.debug("Got event from changelog: %r", event)
            ps.serial = max(ps.serial, event.serial)
            match event:
                case FileCreated() if event.is_wheel():
                    log.info("Event %s: wheel %s added", event.id, event.filename)
                    # New wheels should more often than not belong to the latest
                    # version of the project, and if they don't, they can be pruned
                    # out later.  There's likely little to nothing to be gained by
                    # comparing `rel` to the latest version in the database at this
                    # point.
                    assert event.version is not None
                    v = Project.ensure(event.project).ensure_version(event.version)
                    data = pypi.asset_data(event.project, event.version, event.filename)
                    if data is not None:
                        log.info("Asset %s: adding", event.filename)
                        v.ensure_wheel(
                            filename=data.filename,
                            url=data.url,
                            size=data.size,
                            md5=data.digests.md5,
                            sha256=data.digests.sha256,
                            uploaded=data.upload_time,
                        )
                        wheels_added += 1
                    else:
                        log.info(
                            "Asset %s not found in JSON API; will check later",
                            event.filename,
                        )
                        OrphanWheel.register(v, event.filename, event.timestamp)
                        orphans_added += 1

                case FileRemoved() if event.is_wheel():
                    log.info("Event %s: wheel %s removed", event.id, event.filename)
                    remove_wheel(event.filename)
                    wheels_removed += 1

                case ProjectCreated():
                    log.info("Event %s: project %r created", event.id, event.project)
                    Project.ensure(event.project)
                    projects_added += 1

                case ProjectRemoved():
                    log.info("Event %s: project %r removed", event.id, event.project)
                    if (p := Project.get_or_none(event.project)) is not None:
                        p.remove()
                    projects_removed += 1

                case VersionCreated():
                    assert event.version is not None
                    log.info(
                        "Event %s: version %r of project %r released",
                        event.id,
                        event.version,
                        event.project,
                    )
                    Project.ensure(event.project).ensure_version(event.version)
                    versions_added += 1

                case VersionRemoved():
                    assert event.version is not None
                    log.info(
                        "Event %s: version %r of project %r removed",
                        event.id,
                        event.version,
                        event.project,
                    )
                    if (p := Project.get_or_none(event.project)) is not None:
                        p.remove_version(event.version)
                    versions_removed += 1

                case _:
                    log.debug("Event %s: %r: ignoring", event.id, event.action)

    except Exception:
        ok = False
        raise
    else:
        ok = True
    finally:
        end_time = datetime.now(timezone.utc)
        emit_json_log(
            "scan_changelog.log",
            {
                "op": "scan_changelog",
                "start": str(start_time),
                "end": str(end_time),
                "duration": str(end_time - start_time),
                "projects_added": projects_added,
                "projects_removed": projects_removed,
                "versions_added": versions_added,
                "versions_removed": versions_removed,
                "wheels_added": wheels_added,
                "wheels_removed": wheels_removed,
                "orphans_added": orphans_added,
                "success": ok,
            },
        )
        log.info("END scan_changelog")
