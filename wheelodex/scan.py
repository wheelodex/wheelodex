import logging
from   .pypi_api import PyPIAPI
from   .util     import latest_version

log = logging.getLogger(__name__)

def scan_pypi(db, max_size=None):
    log.info('BEGIN scan_pypi')
    pypi = PyPIAPI()
    serial = pypi.changelog_last_serial()
    log.info('changlog_last_serial() = %d', serial)
    db.serial = serial
    for pkg in pypi.list_packages():
        log.info('Adding wheels for project %r', pkg)
        project = db.add_project(pkg)
        data = pypi.project_data(pkg)
        if data is None or not data.get("releases", {}):
            log.info('Project has no releases')
            continue
        versions = list(data["releases"].keys())
        log.debug('Available versions: %r', versions)
        latest = latest_version(versions)
        log.info('Using latest version: %r', latest)
        qty_queued = 0
        vobj = db.add_version(project, latest)
        for asset in data["releases"][latest]:
            if not asset["filename"].endswith('.whl'):
                log.debug('Asset %s: not a wheel; skipping', asset["filename"])
            elif max_size is not None and asset["size"] > max_size:
                log.debug('Asset %s: size %d too large; skipping',
                          asset["filename"], asset["size"])
            else:
                log.debug('Asset %s: adding', asset["filename"])
                qty_queued += 1
                db.add_wheel(
                    version  = vobj,
                    filename = asset["filename"],
                    url      = asset["url"],
                    size     = asset["size"],
                    md5      = asset["digests"]["md5"].lower(),
                    sha256   = asset["digests"]["sha256"].lower(),
                    uploaded = str(asset["upload_time"]),
                )
        log.info('%s: %d wheels added', pkg, qty_queued)
    log.info('END scan_pypi')

def scan_changelog(db, since, max_size=None):
    log.info('BEGIN scan_changelog(%d)', since)
    pypi = PyPIAPI()
    for proj, rel, _, action, serial in pypi.changelog_since_serial(since):
        actwords = action.split()

        # As of pypa/warehouse revision 97f28df (2018-09-20), the possible
        # "action" strings are (found by searching for "JournalEntry" in the
        # code):
        # - "add {python_version} file {filename}"
        # - "remove file {filename}"
        # - "create" [new project]
        # - "remove project"
        # - "new release"
        # - "remove release"
        # - "add Owner {username}"
        # - "add {role_name} {username}"
        # - "remove {role_name} {username}"
        # - "change {role_name} {username} to {role_name2}" [?]
        # - "nuke user"
        # - "docdestroy"

        if actwords[0] == 'add' and len(actwords) == 4 and \
                actwords[2] == 'file' and actwords[3].endswith('.whl'):
            log.info('Event %d: wheel %s added', serial, actwords[3])
            # New wheels should more often than not belong to the latest
            # version of the project, and if they don't, they can be pruned out
            # later.  There's likely little to nothing to be gained by
            # comparing `rel` to the latest version in the database at this
            # point.
            data = pypi.project_data(proj)
            if data is None or not data.get("releases", {}):
                log.warning('No releases found for project %r', proj)
                continue
            for asset in data["releases"].get(rel, []):
                if asset["filename"] == actwords[3]:
                    if max_size is not None and asset["size"] > max_size:
                        log.info('Asset %s: size %d too large; skipping',
                                 asset["filename"], asset["size"])
                    else:
                        log.info('Asset %s: adding', asset["filename"])
                        db.add_wheel(
                            version  = db.add_version(proj, rel),
                            filename = asset["filename"],
                            url      = asset["url"],
                            size     = asset["size"],
                            md5      = asset["digests"].get("md5").lower(),
                            sha256   = asset["digests"].get("sha256").lower(),
                            uploaded = str(asset["upload_time"]),
                        )
            ### TODO: Log warning if wheel is not found

        elif actwords[:2] == ['remove', 'file'] and len(actwords) == 3 and \
                actwords[2].endswith('.whl'):
            log.info('Event %d: wheel %s removed', serial, actwords[2])
            db.remove_wheel(actwords[2])

        elif action == 'create':
            log.info('Event %d: project %r created', serial, proj)
            db.add_project(proj)

        elif action == 'remove project':
            log.info('Event %d: project %r removed', serial, proj)
            db.remove_project(proj)

        elif action == 'new release':
            log.info('Event %d: version %r of project %r released', serial,
                     rel, proj)
            db.add_version(proj, rel)

        elif action == 'remove release':
            log.info('Event %d: version %r of project %r removed', serial,
                     rel, proj)
            db.remove_version(proj, rel)

        db.serial = serial
    log.info('END scan_changelog')
