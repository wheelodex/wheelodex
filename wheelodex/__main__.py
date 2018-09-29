import json
import logging
import click
from   flask     import current_app
from   flask.cli import FlaskGroup
from   .         import __version__
from   .app      import create_app
from   .db       import Wheel, WheelDatabase
from   .process  import process_queue
from   .scan     import scan_pypi, scan_changelog

# FlaskGroup causes all commands to be run inside an application context,
# thereby letting `wheelodex.db.db` do database operations and making
# `WheelDatabase()` just work.  This does require that `ctx.obj` be left
# untouched, though.
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

@main.command('scan_pypi')
### TODO: Add a command-line option for setting `max_size`
def scan_pypi_cmd():
    with WheelDatabase() as db:
        scan_pypi(
            db,
            max_size=current_app.config.get("WHEELODEX_MAX_WHEEL_SIZE"),
        )

@main.command('scan_changelog')
### TODO: Add a command-line option for setting `max_size`
def scan_changelog_cmd():
    with WheelDatabase() as db:
        if db.serial is None:
            raise click.UsageError('No saved state to update')
        scan_changelog(
            db,
            db.serial,
            max_size=current_app.config.get("WHEELODEX_MAX_WHEEL_SIZE"),
        )

@main.command('process_queue')
def process_queue_cmd():
    with WheelDatabase() as db:
        process_queue(db)

@main.command()
@click.option('-A', '--all', 'dump_all', is_flag=True)
@click.option('-o', '--outfile', default='-')
def dump(dump_all, outfile):
    with WheelDatabase() as db:
        outfile %= {"serial": db.serial}
        with click.open_file(outfile, 'w') as fp:
            for whl in db.session.query(Wheel):
                if dump_all or whl.data is not None:
                    click.echo(json.dumps(whl.as_json()), file=fp)

@main.command()
@click.option('-S', '--serial', type=int)
@click.argument('infile', type=click.File())
def load(infile, serial):
    with WheelDatabase() as db, infile:
        if serial is not None:
            db.serial = serial
        for line in infile:
            about = json.loads(line)
            version = db.add_version(
                about["pypi"].pop("project"),
                about["pypi"].pop("version"),
            )
            whl = db.add_wheel(version, **about["pypi"])
            if "data" in about and whl.data is None:
                db.add_wheel_data(whl, about["data"])
                whl.data.processed = about["wheelodex"]["processed"]
                whl.data.wheelodex_version \
                    = about["wheelodex"]["wheelodex_version"]

if __name__ == '__main__':
    main(prog_name=__package__)
