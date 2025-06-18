"""Functions for downloading & analyzing wheels"""

from __future__ import annotations
from datetime import datetime, timezone
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
import traceback
from typing import Any
import requests
from wheel_inspect import inspect_wheel
from .app import emit_json_log
from .models import Wheel, db
from .util import USER_AGENT

log = logging.getLogger(__name__)


def process_queue(max_wheel_size: int | None = None) -> None:
    """
    Process all of the wheels returned by `Wheel.to_process()` one by one and
    store the results in the database.  If an error occurs, the traceback is
    stored as a `ProcessingError` for the wheel.  The database session is
    committed after each wheel in order to save memory.

    This function requires a Flask application context with a database
    connection to be in effect.

    :param int max_wheel_size: If set, only wheels this size or smaller are
        analyzed
    """
    log.info("BEGIN process_queue")
    start_time = datetime.now(timezone.utc)
    wheels_processed = 0
    bytes_processed = 0
    errors = 0
    with TemporaryDirectory() as tmpdir, requests.Session() as s:
        s.headers["User-Agent"] = USER_AGENT
        try:
            # This outer `try` block is so that stats are written to the
            # logfile even when the function is cancelled via Cntrl-C.
            for whl in Wheel.to_process(max_wheel_size=max_wheel_size):
                fpath = Path(tmpdir, whl.filename)
                try:
                    log.info("Downloading %s from %s ...", whl.filename, whl.url)
                    download(s, whl.url, fpath)
                    about = process_wheel(
                        path=fpath,
                        size=whl.size,
                        md5=whl.md5,
                        sha256=whl.sha256,
                    )
                    whl.set_data(about)
                    # Some errors in inserting data aren't raised until we
                    # actually try to insert by calling commit(), so include
                    # the commit() under the `try`.
                    db.session.commit()
                except Exception:
                    # rollback() needs to be called before log.exception() or
                    # else SQLAlchemy gets all complainy.
                    db.session.rollback()
                    log.exception("Error processing %s", whl.filename)
                    whl.add_error(traceback.format_exc())
                    db.session.commit()
                    errors += 1
                finally:
                    fpath.unlink(missing_ok=True)
                wheels_processed += 1
                bytes_processed += whl.size
        finally:
            end_time = datetime.now(timezone.utc)
            emit_json_log(
                "process_queue.log",
                {
                    "op": "process_queue",
                    "start": str(start_time),
                    "end": str(end_time),
                    "wheels": wheels_processed,
                    "bytes": bytes_processed,
                    "errors": errors,
                },
            )
            log.info("END process_queue")


def process_wheel(path: Path, size: int, md5: str | None, sha256: str | None) -> dict:
    """
    Process the wheel at ``path``.  The wheel is analyzed with
    `inspect_wheel()`, and its size & digests are checked against ``size``,
    ``md5``, and ``sha256`` (provided by PyPI) to verify download integrity.

    :return: the results of the call to `inspect_wheel()`
    """
    log.info("Inspecting %s ...", path.name)
    about: dict[str, Any] = inspect_wheel(path)
    if about["file"]["size"] != size:
        log.error(
            "Wheel %s: size mismatch: PyPI reports %d, got %d",
            size,
            about["file"]["size"],
        )
        raise ValueError(
            f'Size mismatch: PyPI reports {size}, got {about["file"]["size"]}'
        )
    for alg, expected in [("md5", md5), ("sha256", sha256)]:
        if expected is not None and expected != about["file"]["digests"][alg]:
            log.error(
                "Wheel %s: %s hash mismatch: PyPI reports %s, got %s",
                alg,
                expected,
                about["file"]["digests"][alg],
            )
            raise ValueError(
                f"{alg} hash mismatch: PyPI reports {expected},"
                f' got {about["file"]["digests"][alg]}'
            )
    log.info("Finished inspecting %s", path.name)
    return about


def download(s: requests.Session, url: str, path: Path) -> None:
    r = s.get(url, stream=True)
    r.raise_for_status()
    with path.open("wb") as fp:
        for chunk in r.iter_content(65535):
            fp.write(chunk)
