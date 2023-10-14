from __future__ import with_statement
import logging
from logging.config import fileConfig
from alembic import context
from alembic.migration import MigrationContext
from alembic.operations.ops import MigrateOperation
from sqlalchemy import URL, engine_from_config, pool

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)  # type: ignore[arg-type]
logger = logging.getLogger("alembic.env")

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
from flask import current_app  # noqa: E402

url = current_app.config.get("SQLALCHEMY_DATABASE_URI")
if isinstance(url, URL):
    url = url.render_as_string(hide_password=False)
else:
    assert isinstance(url, str)

config.set_main_option("sqlalchemy.url", url)
target_metadata = current_app.extensions["migrate"].db.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    # this callback is used to prevent an auto-migration from being generated
    # when there are no changes to the schema
    # reference: http://alembic.zzzcomputing.com/en/latest/cookbook.html
    def process_revision_directives(
        context: MigrationContext,  # noqa: U100
        revision: tuple[str, str],  # noqa: U100
        directives: list[MigrateOperation],
    ) -> None:
        if getattr(config.cmd_opts, "autogenerate", False):
            script = directives[0]
            # <https://github.com/sqlalchemy/alembic/issues/1325>
            if script.upgrade_ops.is_empty():  # type: ignore[attr-defined]
                directives[:] = []
                logger.info("No changes in schema detected.")

    cfg = config.get_section(config.config_ini_section)
    assert cfg is not None
    engine = engine_from_config(cfg, prefix="sqlalchemy.", poolclass=pool.NullPool)

    connection = engine.connect()
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        process_revision_directives=process_revision_directives,
        compare_type=True,
        **current_app.extensions["migrate"].configure_args
    )

    try:
        with context.begin_transaction():
            context.run_migrations()
    finally:
        connection.close()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
