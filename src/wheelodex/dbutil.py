"""
Utility functions for working with the database.

All of these functions require a Flask application context with a database
connection to be in effect.
"""

from __future__ import annotations
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
import logging
from flask_sqlalchemy.session import Session
from sqlalchemy.orm import scoped_session, with_parent
from .app import emit_json_log
from .models import OrphanWheel, Project, Version, Wheel, WheelData, db

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


def remove_wheel(filename: str) -> None:
    """
    Delete all `Wheel`\\s and `OrphanWheel`\\s with the given filename from the
    database
    """
    db.session.execute(db.delete(Wheel).where(Wheel.filename == filename))
    db.session.execute(db.delete(OrphanWheel).where(OrphanWheel.filename == filename))
    p = Project.get_or_none(filename.split("-")[0])
    if p is not None:
        p.update_has_wheels()


def purge_old_versions() -> None:
    """
    For each project with more than one version, keep (a) the latest version if
    it has orphan wheels, (b) the latest version with wheels registered, and
    (c) the latest version with wheel data, and delete all other versions.
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
        seen_latest = False
        latest_wheel = latest_data = None
        for v, vwheels, vdata, vorphan in db.session.execute(
            # This queries the versions of project `p`, along with the number
            # of wheels, number of wheels with data, and number of orphan
            # wheels each version has:
            db.select(
                Version,
                db.func.count(Wheel.id),
                db.func.count(WheelData.id),
                db.func.count(OrphanWheel.id),
            )
            .join_from(Version, Wheel, isouter=True)
            .join_from(Wheel, WheelData, isouter=True)
            .join_from(Version, OrphanWheel, isouter=True)
            .where(with_parent(p, Project.versions))
            .group_by(Version)
            .order_by(Version.ordering.desc())
        ):
            keep = False
            if not seen_latest and vorphan:
                log.debug(
                    "Project %s: keeping latest version as it has orphan wheels: %s",
                    p.display_name,
                    v.display_name,
                )
                keep = True
            seen_latest = True
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
    emit_json_log(
        "purge_old_versions.log",
        {
            "op": "purge_old_versions",
            "start": str(start_time),
            "end": str(end_time),
            "purged": purged,
        },
    )
    log.info("END purge_old_versions")
