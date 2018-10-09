from   datetime      import datetime, timedelta, timezone
import json
import logging
import click
from   flask         import current_app
from   flask.cli     import FlaskGroup
from   flask_migrate import stamp
from   sqlalchemy    import inspect
from   .             import __version__
from   .app          import create_app
from   .models       import OrphanWheel, Wheel, db
from   .dbutil       import dbcontext, add_version, add_wheel, get_serial, \
                                purge_old_versions, set_serial
from   .process      import process_queue
from   .pypi_api     import PyPIAPI
from   .scan         import scan_pypi, scan_changelog

log = logging.getLogger(__name__)

# FlaskGroup causes all commands to be run inside an application context,
# thereby letting `wheelodex.db.db` do database operations.  This does require
# that `ctx.obj` be left untouched, though.
@click.group(cls=FlaskGroup, create_app=create_app)
@click.option(
    '-l', '--log-level',
    type = click.Choice(['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG']),
    default      = 'INFO',
    show_default = True,
)
@click.version_option(
    __version__, '-V', '--version', message='%(prog)s %(version)s',
)
def main(log_level):
    logging.basicConfig(
        format  = '%(asctime)s %(levelname)s %(name)s %(message)s',
        datefmt = '%Y-%m-%dT%H:%M:%S%z',
        level   = getattr(logging, log_level),
    )

@main.command()
@click.option('-f', '--force', is_flag=True)
def initdb(force):
    """
    Initialize the database.

    This command creates the database tables, initializes the PyPI serial to 0,
    and sets the Alembic revision to the latest version.  In an attempt at
    ensuring idempotence, this command will do nothing if there are already one
    or more tables in the database; use the ``--force`` option to override this
    check.
    """
    if force or not inspect(db.engine).get_table_names():
        click.echo('Initializing database ...')
        with dbcontext():
            db.create_all()
            set_serial(0)
        stamp()
    else:
        click.echo('Database appears to already be initialized; doing nothing')

@main.command('scan-pypi')
def scan_pypi_cmd():
    with dbcontext():
        scan_pypi()

@main.command('scan-changelog')
def scan_changelog_cmd():
    with dbcontext():
        serial = get_serial()
        if serial is None:
            raise click.UsageError('No saved state to update')
        scan_changelog(serial)

@main.command('process-queue')
### TODO: Add a command-line option for setting `max_wheel_size`
def process_queue_cmd():
    with dbcontext():
        process_queue(
            max_wheel_size=current_app.config.get("WHEELODEX_MAX_WHEEL_SIZE")
        )

@main.command()
@click.option('-A', '--all', 'dump_all', is_flag=True)
@click.option('-o', '--outfile', default='-')
def dump(dump_all, outfile):
    with dbcontext():
        outfile %= {"serial": get_serial()}
        with click.open_file(outfile, 'w') as fp:
            for whl in Wheel.query:
                if dump_all or whl.data is not None:
                    click.echo(json.dumps(whl.as_json()), file=fp)

@main.command()
@click.option('-S', '--serial', type=int)
@click.argument('infile', type=click.File())
def load(infile, serial):
    with dbcontext(), infile:
        if serial is not None:
            set_serial(serial)
        for line in infile:
            about = json.loads(line)
            version = add_version(
                about["pypi"].pop("project"),
                about["pypi"].pop("version"),
            )
            whl = add_wheel(version, **about["pypi"])
            if "data" in about and whl.data is None:
                whl.set_data(about["data"])
                whl.data.processed = about["wheelodex"]["processed"]
                whl.data.wheelodex_version \
                    = about["wheelodex"]["wheelodex_version"]

@main.command('purge-old-versions')
def purge_old_versions_cmd():
    with dbcontext():
        purge_old_versions()

@main.command()
def process_orphan_wheels():
    log.info('BEGIN process_orphan_wheels')
    pypi = PyPIAPI()
    max_age = current_app.config["WHEELODEX_MAX_ORPHAN_AGE_SECONDS"]
    with dbcontext():
        for orphan in OrphanWheel.query:
            data = pypi.asset_data(
                orphan.project.name,
                orphan.version.display_name,
                orphan.filename,
            )
            if data is not None:
                log.info('Wheel %s: data found', orphan.filename)
                add_wheel(
                    version  = orphan.version,
                    filename = data["filename"],
                    url      = data["url"],
                    size     = data["size"],
                    md5      = data["digests"].get("md5").lower(),
                    sha256   = data["digests"].get("sha256").lower(),
                    uploaded = str(data["upload_time"]),
                )
                db.session.delete(orphan)
            else:
                log.info('Wheel %s: data not found', orphan.filename)
        expired = OrphanWheel.query.filter(
            OrphanWheel.uploaded
                < datetime.now(timezone.utc) - timedelta(seconds=max_age)
        ).delete()
        log.info('%d orphan wheels expired', expired)
    log.info('END process_orphan_wheels')

if __name__ == '__main__':
    main(prog_name=__package__)
