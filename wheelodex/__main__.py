from   configparser import ConfigParser
import json
import logging
from   types        import SimpleNamespace
import click
from   .            import __version__
from   .db          import WheelDatabase, Wheel
from   .process     import process_queue
from   .scan        import scan_pypi, scan_changelog
from   .util        import parse_memory

@click.group()
@click.option(
    '-c', '--config',
    type         = click.Path(dir_okay=False),
    default      = 'config.ini',
    show_default = True,
)
@click.option(
    '-l', '--log-level',
    type = click.Choice(['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG']),
    default      = 'INFO',
    show_default = True,
)
@click.version_option(
    __version__, '-V', '--version', message='%(prog)s %(version)s',
)
@click.pass_context
def main(ctx, config, log_level):
    cfg = ConfigParser()
    cfg.read(config)
    ctx.obj = SimpleNamespace()
    ctx.obj.db = WheelDatabase(cfg["database"])
    try:
        ctx.obj.max_size = parse_memory(cfg["collection"]["max_size"])
    except KeyError:
        ctx.obj.max_size = None
    logging.basicConfig(
        format  = '%(asctime)s %(levelname)s %(name)s %(message)s',
        datefmt = '%Y-%m-%dT%H:%M:%S%z',
        level   = getattr(logging, log_level),
    )

@main.command('scan_pypi')
### TODO: Add a command-line option for setting `max_size`
@click.pass_obj
def scan_pypi_cmd(obj):
    with obj.db:
        scan_pypi(obj.db, max_size=obj.max_size)

@main.command('scan_changelog')
### TODO: Add a command-line option for setting `max_size`
@click.pass_obj
def scan_changelog_cmd(obj):
    with obj.db:
        if obj.db.serial is None:
            raise click.UsageError('No saved state to update')
        scan_changelog(obj.db, obj.db.serial, max_size=obj.max_size)

@main.command('process_queue')
@click.pass_obj
def process_queue_cmd(obj):
    with obj.db:
        process_queue(obj.db)

@main.command()
@click.option('-A', '--all', 'dump_all', is_flag=True)
@click.option('-o', '--outfile', type=click.File('w'), default='-')
@click.pass_obj
def dump(obj, dump_all, outfile):
    with outfile, obj.db:
        for whl in obj.db.session.query(Wheel):
            if dump_all or whl.data is not None:
                about = {
                    "pypi": {
                        "filename": whl.filename,
                        "url": whl.url,
                        "project": whl.version.project.display_name,
                        "version": whl.version.display_name,
                        "size": whl.size,
                        "md5": whl.md5,
                        "sha256": whl.sha256,
                        "uploaded": whl.uploaded,
                    },
                }
                if whl.data is not None:
                    about["data"] = whl.data.raw_data
                    about["wheelodex"] = {
                        "processed": str(whl.data.processed),
                        "wheelodex_version": whl.data.wheelodex_version,
                    }
                click.echo(json.dumps(about), file=outfile)

@main.command()
@click.argument('infile', type=click.File())
@click.pass_obj
def load(obj, infile):
    with infile, obj.db:
        for line in infile:
            about = json.loads(line)
            version = obj.db.add_version(
                about["pypi"].pop("project"),
                about["pypi"].pop("version"),
            )
            whl = obj.db.add_wheel(version, **about["pypi"])
            if "data" in about and whl.data is None:
                obj.db.add_wheel_data(whl, about["data"])
                whl.data.processed = about["wheelodex"]["processed"]
                whl.data.wheelodex_version \
                    = about["wheelodex"]["wheelodex_version"]

if __name__ == '__main__':
    main(prog_name=__package__)
