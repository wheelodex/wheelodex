from   configparser        import ConfigParser
from   datetime            import datetime, timedelta, timezone
import json
import logging
from   os.path             import join
from   time                import time
import click
from   flask               import current_app
from   flask.cli           import FlaskGroup
from   flask_migrate       import stamp
from   importlib_resources import as_file, files
from   sqlalchemy          import inspect
from   .                   import __version__
from   .app                import create_app
from   .dbutil             import add_wheel, add_wheel_from_json, dbcontext, \
                                      get_serial, purge_old_versions, set_serial
from   .models             import EntryPointGroup, OrphanWheel, Wheel, db
from   .process            import process_queue
from   .pypi_api           import PyPIAPI
from   .scan               import scan_changelog, scan_pypi

log = logging.getLogger(__name__)

with as_file(files('wheelodex') / 'data' / 'entry_points.ini') as ep_path:
    # Violating the context manager like this means that wheelodex can't be run
    # from within a zipfile.
    ep_path = str(ep_path)

# FlaskGroup causes all commands to be run inside an application context,
# thereby letting `db` do database operations.  This does require that
# `ctx.obj` be left untouched, though.
@click.group(cls=FlaskGroup, create_app=create_app)
@click.option(
    '-l', '--log-level',
    type = click.Choice(['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG']),
    default      = 'INFO',
    show_default = True,
    help         = 'Set command logging level',
)
@click.version_option(
    __version__, '-V', '--version', message='%(prog)s %(version)s',
)
def main(log_level):
    """ Manage a Wheelodex instance """
    logging.basicConfig(
        format  = '%(asctime)s %(levelname)s %(name)s %(message)s',
        datefmt = '%Y-%m-%dT%H:%M:%S%z',
        level   = getattr(logging, log_level),
    )

@main.command()
@click.option('-f', '--force', is_flag=True, help='Force initialization')
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
    """ Scan all PyPI projects for wheels """
    with dbcontext():
        scan_pypi()

@main.command('scan-changelog')
def scan_changelog_cmd():
    """ Scan the PyPI changelog for new wheels """
    with dbcontext():
        serial = get_serial()
        if serial is None:
            raise click.UsageError('No saved state to update')
        scan_changelog(serial)

@main.command('process-queue')
@click.option('-S', '--max-wheel-size', type=int,
              help='Maximum size of wheels to process')
def process_queue_cmd(max_wheel_size):
    """
    Analyze new wheels.

    This command downloads & analyzes wheels that have been registered but not
    analyzed yet and adds their data to the database.  Only wheels for the
    latest nonempty version of each project are analyzed.
    """
    if max_wheel_size is None:
        # Setting the option's default to the below expression or a
        # lambdafication thereof doesn't work:
        max_wheel_size = current_app.config.get("WHEELODEX_MAX_WHEEL_SIZE")
    with dbcontext():
        process_queue(max_wheel_size=max_wheel_size)

@main.command()
@click.option('-A', '--all', 'dump_all', is_flag=True, help='Dump all wheels')
@click.option('-o', '--outfile', default='-', help='File to dump to')
def dump(dump_all, outfile):
    """
    Dump wheel data as line-delimited JSON.

    This command outputs a JSONification of the wheels in the database to
    standard output or the file specified with ``--outfile``.  By default, only
    wheels that have been analyzed are output; use the ``--all`` option to also
    include registered wheels that have not yet been analyzed.

    The output format is a stream of newline-delimited one-line JSON objects.
    The order in which the wheels are output is undefined.

    If the output filename contains the substring "%(serial)s", it is replaced
    with the serial ID of the last seen PyPI event.
    """
    with dbcontext():
        outfile %= {"serial": get_serial()}
        with click.open_file(outfile, 'w') as fp:
            q = Wheel.query
            if not dump_all:
                q = q.filter(Wheel.data.has())
            # Dumping in pages gives a needed efficiency boost:
            q = q.paginate(page=1, per_page=100)
            ### TODO: Should the query be ordered by something?
            while True:
                for whl in q.items:
                    click.echo(json.dumps(whl.as_json()), file=fp)
                if q.has_next:
                    q = q.next()  # noqa: B305
                else:
                    break

@main.command()
@click.option('-S', '--serial', type=int,
              help='Also update PyPI serial to given value')
@click.argument('infile', type=click.File())
def load(infile, serial):
    """
    Load wheel data from line-delimited JSON.

    This command reads a file of JSONified wheel data, such as produced by
    the `dump` command, and adds the wheels to the database.  Wheels in the
    database that already have data are not modified.
    """
    with dbcontext(), infile:
        if serial is not None:
            set_serial(serial)
        for line in infile:
            add_wheel_from_json(json.loads(line))

@main.command('purge-old-versions')
def purge_old_versions_cmd():
    """ Delete old versions from the database """
    with dbcontext():
        purge_old_versions()

@main.command()
def process_orphan_wheels():
    """
    Register or expire orphan wheels.

    This command queries PyPI's JSON API to see if it can find the data for any
    orphaned wheels.  Those that are found are registered as "normal" wheels
    and no longer orphaned.  Those that aren't found despite being older than a
    configured number of seconds are considered expired and deleted from the
    database.
    """
    log.info('BEGIN process_orphan_wheels')
    start_time = time()
    unorphaned = 0
    remaining = 0
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
                unorphaned += 1
            else:
                log.info('Wheel %s: data not found', orphan.filename)
                remaining += 1
        expired = OrphanWheel.query.filter(
            OrphanWheel.uploaded
                < datetime.now(timezone.utc) - timedelta(seconds=max_age)
        ).delete()
        log.info('%d orphan wheels expired', expired)
    end_time = time()
    log_dir = current_app.config.get("WHEELODEX_STATS_LOG_DIR")
    if log_dir is not None:
        with open(join(log_dir, 'process_orphan_wheels.log'), 'a') as fp:
            print(
                'process_orphan_wheels|start={}|end={}|unorphaned={}'
                '|expired={}|remain={}'
                .format(start_time, end_time, unorphaned, expired,
                        remaining - expired),
                file=fp,
            )
    log.info('END process_orphan_wheels')

@main.command()
@click.argument('infile', type=click.File(), default=ep_path)
def load_entry_points(infile):
    """
    Load entry point group descriptions from a file.

    This command reads descriptions & summaries for entry point groups from
    either the given file or, if no file is specified, from a pre-made file
    bundled with Wheelodex; the data read is then stored in the database for
    display in the web interface when viewing entry point-related data.

    The file must be an INI file as parsed by ``configparser``.  Each section
    describes the entry point group of the same name and may contain
    ``summary`` and ``description`` options whose values are Markdown strings
    to render as the group's summary or description.  Summaries are limited to
    2048 characters and are expected to be a single line.  Descriptions are
    limited to 65535 characters and may span multiple lines.
    """
    epgs = ConfigParser(interpolation=None)
    epgs.read_file(infile)
    with dbcontext():
        for name in epgs.sections():
            group = EntryPointGroup.from_name(name)
            if epgs.has_option(name, 'summary'):
                group.summary = epgs.get(name, 'summary')
            if epgs.has_option(name, 'description'):
                group.description = epgs.get(name, 'description')

if __name__ == '__main__':
    main(prog_name=__package__)
