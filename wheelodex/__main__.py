from   configparser             import ConfigParser
import json
import logging
from   types                    import SimpleNamespace
import click
from   .                        import __version__
from   .db                      import WheelDatabase, Wheel
from   .download.queue_wheels   import queue_all_wheels, queue_wheels_since
from   .download.unqueue_wheels import process_queue
from   .util                    import parse_memory

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
    ctx.obj.latest_only \
        = cfg.getboolean("collection", "latest_only", fallback=True)
    logging.basicConfig(
        format  = '%(asctime)s %(levelname)s %(name)s %(message)s',
        datefmt = '%Y-%m-%dT%H:%M:%S%z',
        level   = getattr(logging, log_level),
    )

@main.command()
### TODO: Add command-line options for setting `latest_only` and `max_size`
@click.pass_obj
def queue_all(obj):
    with obj.db:
        queue_all_wheels(
            obj.db,
            latest_only = obj.latest_only,
            max_size    = obj.max_size,
        )

@main.command()
### TODO: Add a command-line option for setting `max_size`
@click.pass_obj
def queue_update(obj):
    with obj.db:
        if obj.db.serial is None:
            raise click.UsageError('No saved state to update')
        queue_wheels_since(obj.db, obj.db.serial, max_size=obj.max_size)

@main.command('process_queue')
@click.pass_obj
def process_queue_cmd(obj):
    with obj.db:
        process_queue(obj.db)

@main.command()
@click.option('-A', '--all', 'dump_all', is_flag=True)
@click.option('-o', '--outfile', type=click.File('w'), default='-')
@click.option('-Q', '--queue', is_flag=True)
@click.pass_obj
def dump(obj, dump_all, queue, outfile):
    with outfile, obj.db:
        for whl in obj.db.session.query(Wheel):
            if dump_all or whl.data is not None:
                about = {
                    "pypi": {
                        "filename": whl.filename,
                        "project": whl.project,
                        "version": whl.version,
                        "size": whl.size,
                        "md5": whl.md5,
                        "sha256": whl.sha256,
                        "uploaded": whl.uploaded,
                    },
                }
                if whl.data is not None:
                    about["data"] = whl.data.raw_data,
                    about["wheelodex"] = {
                        "processed": str(whl.data.processed),
                        "wheelodex_version": whl.data.wheelodex_version,
                    }
                if queue:
                    about["queued"] = whl.queued
                click.echo(json.dumps(about), file=outfile)

if __name__ == '__main__':
    main(prog_name=__package__)
