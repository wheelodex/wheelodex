import logging
import os
import os.path
import platform
from   tempfile          import TemporaryDirectory
import time
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

def process_queue(db: 'WheelDatabase'):
    with TemporaryDirectory() as tmpdir:
        for whl in db.iterqueue():
            try:
                about = process_wheel(
                    filename = whl.filename,
                    url      = whl.url,
                    size     = whl.size,
                    digests  = whl.digests,
                    uploaded = whl.uploaded,
                    tmpdir   = tmpdir,
                )
            except Exception:
                log.exception('Error processing %s', whl.filename)
                db.queue_error(whl, traceback.format_exc())
            else:
                db.add_wheel_entry(about)
            finally:
                db.unqueue_wheel(whl.filename)

def process_wheel(filename, url, size, digests, uploaded, tmpdir):
    fpath = os.path.join(tmpdir, filename)
    log.info('Downloading %s from %s ...', filename, url)
    # Write "user-agent" in lowercase so it overrides requests_download's
    # header correctly:
    download(url, fpath, headers={"user-agent": USER_AGENT})
    log.info('Inspecting %s ...', filename)
    about = inspect_wheel(fpath)
    os.remove(fpath)
    if about["file"]["size"] != size:
        log.error('Wheel %s: size mismatch: PyPI reports %d, got %d',
                  size, about["file"]["size"])
        raise ValueError('Size mismatch: PyPI reports {}, got {}'
                         .format(size, about["file"]["size"]))
    for alg in ("md5", "sha256"):
        if alg in digests:
            if digests[alg].lower() != about["file"]["digests"][alg]:
                log.error(
                    'Wheel %s: %s hash mismatch: PyPI reports %s, got %s',
                    alg,
                    digests[alg].lower(),
                    about["file"]["digests"][alg],
                )
                raise ValueError(
                    '{} hash mismatch: PyPI reports {}, got {}'.format(
                        alg,
                        digests[alg].lower(),
                        about["file"]["digests"][alg],
                    )
                )
    about["pypi"] = {
        "download_url": url,
        "uploaded": uploaded,
    }
    about["wheelodex"] = {
        "scanned": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        "wheelodex_version": __version__,
    }
    log.info('Finished inspecting %s', filename)
    return about
