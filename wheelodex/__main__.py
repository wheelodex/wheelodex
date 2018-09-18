from   configparser           import ConfigParser
import logging
from   types                  import SimpleNamespace
import click
from   .                      import __version__
from   .db                    import WheelDatabase
from   .download.queue_wheels import queue_all_wheels

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
    ### TODO: Read max_size and latest_only from config and store on object
    logging.basicConfig(
        format  = '%(asctime)s %(levelname)s %(name)s %(message)s',
        datefmt = '%Y-%m-%dT%H:%M:%S%z',
        level   = logging.INFO,
    )

@main.command()
@click.pass_obj
def queue_init(obj):
    ### TODO: Pass in latest_only and max_size from config
    with obj.db:
        queue_all_wheels(obj.db)

if __name__ == '__main__':
    main()
