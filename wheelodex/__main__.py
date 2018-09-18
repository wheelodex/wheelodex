from   configparser           import ConfigParser
import logging
from   types                  import SimpleNamespace
import click
from   .                      import __version__
from   .db                    import WheelDatabase
from   .download.queue_wheels import queue_all_wheels, queue_wheels_since
from   .util                  import parse_memory

@click.group()
@click.option(
    '-c', '--config',
    type         = click.Path(dir_okay=False),
    default      = 'config.ini',
    show_default = True,
)
@click.version_option(
    __version__, '-V', '--version', message='%(prog)s %(version)s',
)
@click.pass_context
def main(ctx, config):
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
        level   = logging.INFO,
    )

@main.command()
### TODO: Add command-line options for setting `latest_only` and `max_size`
@click.pass_obj
def queue_init(obj):
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

if __name__ == '__main__':
    main()
