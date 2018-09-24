import logging
from   .pypi_api import PyPIAPI
from   ..db      import Wheel
from   ..util    import latest_version

log = logging.getLogger(__name__)

def queue_all_wheels(db, latest_only=True, max_size=None):
    log.info('BEGIN queue_all_wheels')
    pypi = PyPIAPI()
    serial = pypi.changelog_last_serial()
    log.info('changlog_last_serial() = %d', serial)
    db.serial = serial
    #projects_seen = set(db.session.query(Project.display_name))
    for pkg in pypi.list_packages():
        #if pkg in projects_seen: continue
        log.info('Queuing wheels for project %r', pkg)
        data = pypi.project_data(pkg) or {"releases": {}}
        versions = list(data["releases"].keys())
        log.info('Available versions: %r', versions)
        latest = latest_version(versions)
        if latest_only and latest is not None:
            log.info('Preferring latest version: %r', latest)
        project = db.add_project(pkg, latest)
        qty_queued = 0
        qty_unqueued = 0
        for v in versions:
            for asset in data["releases"][v]:
                if not asset["filename"].endswith('.whl'):
                    log.debug('Asset %s: not a wheel; skipping',
                              asset["filename"])
                    continue
                if latest_only and v != latest:
                    log.debug('Asset %s: not latest version; not queuing',
                              asset["filename"])
                    queued = False
                    qty_unqueued += 1
                elif max_size is not None and asset["size"] > max_size:
                    log.debug('Asset %s: size %d too large; not queuing',
                              asset["filename"], asset["size"])
                    queued = False
                    qty_unqueued += 1
                else:
                    log.debug('Asset %s: queuing', asset["filename"])
                    queued = True
                    qty_queued += 1
                db.add_wheel(Wheel(
                    filename = asset["filename"],
                    url      = asset["url"],
                    project  = project,
                    version  = v,
                    size     = asset["size"],
                    md5      = asset["digests"]["md5"].lower(),
                    sha256   = asset["digests"]["sha256"].lower(),
                    uploaded = str(asset["upload_time"]),
                    queued   = queued,
                ))
        log.info('%s: %d wheels queued, %d wheels not queued',
                 pkg, qty_queued, qty_unqueued)
        if qty_queued or qty_unqueued:
            db.session.commit()
    log.info('END queue_all_wheels')

def queue_wheels_since(db, since, max_size=None):
    log.info('BEGIN queue_wheels_since(%d)', since)
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
            ### TODO: Apply `latest_only`
            data = pypi.project_data(proj)
            if data is None:
                log.warning('No releases found for project %r', proj)
                continue
            for asset in data["releases"].get(rel, []):
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
                        project  = db.get_project(proj, create=True),
                        version  = rel,
                        size     = asset["size"],
                        md5      = asset["digests"].get("md5").lower(),
                        sha256   = asset["digests"].get("sha256").lower(),
                        uploaded = str(asset["upload_time"]),
                        queued   = queued,
                    ))
            ### TODO: Log if no wheel is found

        elif actwords[:2] == ['remove', 'file'] and len(actwords) == 3 and \
                actwords[2].endswith('.whl'):
            log.info('Event %d: wheel %s removed', serial, actwords[2])
            db.remove_wheel(actwords[2])

        elif action == 'create':
            log.info('Event %d: project %r created', serial, proj)
            db.add_project(proj, None)

        elif action == 'remove project':
            log.info('Event %d: project %r removed', serial, proj)
            db.remove_project(proj)

        elif action == 'new release':
            log.info('Event %d: version %r of project %r released', serial,
                     rel, proj)
            project = db.get_project(proj, create=True)
            if project.latest_version is None or \
                    latest_version([project.latest_version, rel]) == rel:
                project.latest_version = rel

        elif action == 'remove release':
            log.info('Event %d: version %r of project %r removed', serial,
                     rel, proj)
            db.remove_version(proj, rel)

        db.serial = serial
    log.info('END queue_wheels_since')
