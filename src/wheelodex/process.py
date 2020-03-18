""" Functions for downloading & analyzing wheels """

import logging
import os
from   os.path           import join
from   tempfile          import TemporaryDirectory
from   time              import time
import traceback
from   flask             import current_app
from   requests_download import download
from   wheel_inspect     import inspect_wheel
from   .dbutil           import iterqueue
from   .models           import db
from   .util             import USER_AGENT

log = logging.getLogger(__name__)

def process_queue(max_wheel_size=None):
    """
    Process all of the wheels returned by `iterqueue()` one by one and store
    the results in the database.  If an error occurs, the traceback is stored
    as a `ProcessingError` for the wheel.  The database session is committed
    after each wheel in order to save memory.

    This function requires a Flask application context with a database
    connection to be in effect.

    :param int max_wheel_size: If set, only wheels this size or smaller are
        analyzed
    """
    start_time = time()
    wheels_processed = 0
    bytes_processed = 0
    errors = 0
    with TemporaryDirectory() as tmpdir:
        try:
            # This outer `try` block is so that stats are written to the
            # logfile even when the function is cancelled via Cntrl-C.
            for whl in iterqueue(max_wheel_size=max_wheel_size):
                try:
                    about = process_wheel(
                        filename = whl.filename,
                        url      = whl.url,
                        size     = whl.size,
                        md5      = whl.md5,
                        sha256   = whl.sha256,
                        tmpdir   = tmpdir,
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
                    log.exception('Error processing %s', whl.filename)
                    whl.add_error(traceback.format_exc())
                    db.session.commit()
                    errors += 1
                wheels_processed += 1
                bytes_processed += whl.size
        finally:
            end_time = time()
            log_dir = current_app.config.get("WHEELODEX_STATS_LOG_DIR")
            if log_dir is not None:
                with open(join(log_dir, 'process_queue.log'), 'a') as fp:
                    print(
                        'process_queue|start={}|end={}|wheels={}|bytes={}'
                        '|errors={}'
                        .format(start_time, end_time, wheels_processed,
                                bytes_processed, errors),
                        file=fp,
                    )

def process_wheel(filename, url, size, md5, sha256, tmpdir):
    """
    Process an individual wheel.  The wheel is downloaded from ``url`` to the
    directory ``tmpdir``, analyzed with `inspect_wheel()`, and then deleted.
    The wheel's size and digests are also checked against ``size``, ``md5``,
    and ``sha256`` (provided by PyPI) to verify download integrity.

    :return: the results of the call to `inspect_wheel()`
    """
    fpath = join(tmpdir, filename)
    log.info('Downloading %s from %s ...', filename, url)
    # Write "user-agent" in lowercase so it overrides requests_download's
    # header correctly:
    download(url, fpath, headers={"user-agent": USER_AGENT})
    log.info('Inspecting %s ...', filename)
    try:
        about = inspect_wheel(fpath)
    finally:
        os.remove(fpath)
    if about["file"]["size"] != size:
        log.error('Wheel %s: size mismatch: PyPI reports %d, got %d',
                  size, about["file"]["size"])
        raise ValueError('Size mismatch: PyPI reports {}, got {}'
                         .format(size, about["file"]["size"]))
    for alg, expected in [("md5", md5), ("sha256", sha256)]:
        if expected is not None and expected != about["file"]["digests"][alg]:
            log.error(
                'Wheel %s: %s hash mismatch: PyPI reports %s, got %s',
                alg,
                expected,
                about["file"]["digests"][alg],
            )
            raise ValueError(
                '{} hash mismatch: PyPI reports {}, got {}'.format(
                    alg,
                    expected,
                    about["file"]["digests"][alg],
                )
            )
    log.info('Finished inspecting %s', filename)
    return about
