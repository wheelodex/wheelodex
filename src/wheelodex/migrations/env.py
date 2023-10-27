from __future__ import with_statement
from collections.abc import Iterable
import logging
from logging.config import fileConfig
from alembic import context
from alembic.migration import MigrationContext
from alembic.operations import MigrationScript
from flask import current_app
from sqlalchemy import URL

# This is the Alembic Config object, which provides
# access to the values within the .ini file in use:
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
logger = logging.getLogger("alembic.env")

target_db = current_app.extensions["migrate"].db

url = target_db.engine.url
if isinstance(url, URL):
    url = url.render_as_string(hide_password=False)
config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_db.metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """

    # This callback is used to prevent an auto-migration from being generated
    # when there are no changes to the schema
    # <http://alembic.zzzcomputing.com/en/latest/cookbook.html>
    def process_revision_directives(
        _context: MigrationContext,
        _revision: str | Iterable[str | None] | Iterable[str],
        directives: list[MigrationScript],
    ) -> None:
        if getattr(config.cmd_opts, "autogenerate", False):
            script = directives[0]
            # <https://github.com/sqlalchemy/alembic/issues/1325>
            if script.upgrade_ops.is_empty():
                directives[:] = []
                logger.info("No changes in schema detected.")

    with target_db.engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_db.metadata,
            process_revision_directives=process_revision_directives,
            **current_app.extensions["migrate"].configure_args
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
