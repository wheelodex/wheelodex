import logging
from   ..db         import Wheel
from   ..util       import latest_version
from   .pypi_xmlrpc import PyPIXMLRPC

log = logging.getLogger(__name__)

def queue_all_wheels(db, latest_only=True, max_size=None):
    log.info('BEGIN queue_all_wheels')
    pypi = PyPIXMLRPC()
    serial = pypi.changelog_last_serial()
    log.info('changlog_last_serial() = %d', serial)
    for pkg in pypi.list_packages():
        log.info('Queuing wheels for project %r', pkg)
        versions = pypi.package_releases(pkg)
        log.info('Available versions: %r', versions)
        if latest_only:
            pref_version = latest_version(versions)
            if pref_version is not None:
                log.info('Preferring latest version: %r', pref_version)
            else:
                log.info('No non-prerelease versions available')
        for v in versions:
            for asset in pypi.release_urls(pkg, v):
                if asset["packagetype"] != "bdist_wheel":
                    # This produces too many irrelevant log entries:
                    #log.info('Asset %s: not a wheel; skipping',
                    #         asset["filename"])
                    continue
                if pref_version is not None and v != pref_version:
                    log.info('Asset %s: not latest version; not queuing',
                             asset["filename"])
                    queued = False
                elif max_size is not None and asset["size"] > max_size:
                    log.info('Asset %s: size %d too large; not queuing',
                             asset["filename"], asset["size"])
                    queued = False
                else:
                    log.info('Asset %s: queuing', asset["filename"])
                    queued = True
                db.add_wheel(Wheel(
                    filename = asset["filename"],
                    url      = asset["url"],
                    project  = pkg,
                    version  = v,
                    size     = asset["size"],
                    md5      = asset["digests"]["md5"].lower(),
                    sha256   = asset["digests"]["sha256"].lower(),
                    uploaded = str(asset["upload_time"]),
                    queued   = queued,
                ))
    db.serial = serial
    log.info('END queue_all_wheels')

def queue_wheels_since(db, since, max_size=None):
    log.info('BEGIN queue_wheels_since(%d)', since)
    pypi = PyPIXMLRPC()
    for proj, rel, _, action, serial in pypi.changelog_since_serial(since):
        actwords = action.split()
        # cf. calls to add_journal_entry in
        # <https://github.com/pypa/pypi-legacy/blob/master/store.py>
        if action == 'remove':
            # Package or version removed
            if rel is None:
                log.info('Event %d: project %r removed', serial, proj)
                db.remove_project(proj, serial)
            else:
                log.info('Event %d: version %r of project %r removed', serial,
                         rel, proj)
                db.remove_version(proj, rel, serial)
        elif actwords[0] == 'add' and len(actwords) == 4 and \
                actwords[2] == 'file' and actwords[3].endswith('.whl'):
            log.info('Event %d: wheel %s added', serial, actwords[3])
            ### TODO: Apply `latest_only`
            for asset in pypi.release_urls(proj, rel):
                if asset["filename"] == actwords[3]:
                    if max_size is not None and asset["size"] > max_size:
                        log.info('Asset %s: size %d too large; not queuing',
                                 asset["filename"], asset["size"])
                        queued = False
                    else:
                        log.info('Asset %s: queuing', asset["filename"])
                        queued = True
                    db.add_wheel(Wheel(
                        filename = asset["filename"],
                        url      = asset["url"],
                        project  = proj,
                        version  = rel,
                        size     = asset["size"],
                        md5      = asset["digests"].get("md5").lower(),
                        sha256   = asset["digests"].get("sha256").lower(),
                        uploaded = str(asset["upload_time"]),
                        queued   = queued,
                    ), serial=serial)
            ### TODO: Log if no wheel is found
        elif actwords[:2] == ['remove', 'file'] and len(actwords) == 3 and \
                actwords[2].endswith('.whl'):
            log.info('Event %d: wheel %s removed', serial, actwords[2])
            db.remove_wheel(actwords[2], serial)
    log.info('END queue_wheels_since')
