import logging
import os
import os.path
import platform
from   tempfile          import TemporaryDirectory
import traceback
import requests
from   requests_download import __version__ as rd_version, download
from   ..                import __url__, __version__
from   ..inspect         import inspect_wheel

log = logging.getLogger(__name__)

USER_AGENT = 'wheelodex/{} ({}) requests/{} requests_download/{} {}/{}'.format(
    __version__,
    __url__,
    requests.__version__,
    rd_version,
    platform.python_implementation(),
    platform.python_version(),
)

def process_queue(db):
    with TemporaryDirectory() as tmpdir:
        for whl in db.iterqueue():
            try:
                about = process_wheel(
                    filename = whl.filename,
                    url      = whl.url,
                    size     = whl.size,
                    md5      = whl.md5,
                    sha256   = whl.sha256,
                    tmpdir   = tmpdir,
                )
            except Exception:
                log.exception('Error processing %s', whl.filename)
                db.add_wheel_error(whl, traceback.format_exc())
            else:
                db.add_wheel_data(whl, about)
            finally:
                db.session.commit()

def process_wheel(filename, url, size, md5, sha256, tmpdir):
    fpath = os.path.join(tmpdir, filename)
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
