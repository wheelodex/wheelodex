import json
import logging
import click
from   flask     import current_app
from   flask.cli import FlaskGroup
from   .         import __version__
from   .app      import create_app
from   .models   import Wheel, db
from   .dbutil   import dbcontext, add_version, add_wheel, get_serial, set_serial
from   .process  import process_queue
from   .scan     import scan_pypi, scan_changelog

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
def initdb():
    """ Ensure the database is initialized """
    with dbcontext():
        db.create_all()
        set_serial(0)

@main.command('scan-pypi')
### TODO: Add a command-line option for setting `max_size`
def scan_pypi_cmd():
    with dbcontext():
        scan_pypi(max_size=current_app.config.get("WHEELODEX_MAX_WHEEL_SIZE"))

@main.command('scan-changelog')
### TODO: Add a command-line option for setting `max_size`
def scan_changelog_cmd():
    with dbcontext():
        serial = get_serial()
        if serial is None:
            raise click.UsageError('No saved state to update')
        scan_changelog(
            serial,
            max_size=current_app.config.get("WHEELODEX_MAX_WHEEL_SIZE"),
        )

@main.command('process-queue')
def process_queue_cmd():
    with dbcontext():
        process_queue()

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

@main.command()
def purge_old_versions():
    with dbcontext():
        purge_old_versions()

if __name__ == '__main__':
    main(prog_name=__package__)
