from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any
from flask import Flask, current_app
from flask_migrate import Migrate

DEFAULT_CONFIG = {
    "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    "SQLALCHEMY_TRACK_MODIFICATIONS": False,
    "WHEELODEX_MAX_WHEEL_SIZE": None,
    "WHEELODEX_ENTRY_POINTS_PER_PAGE": 100,
    "WHEELODEX_ENTRY_POINT_GROUPS_PER_PAGE": 100,
    "WHEELODEX_RDEPENDS_PER_PAGE": 100,
    "WHEELODEX_MAX_ORPHAN_AGE_SECONDS": 2 * 24 * 60 * 60,  # 2 days
    "WHEELODEX_PROJECTS_PER_PAGE": 100,
    "WHEELODEX_SEARCH_RESULTS_PER_PAGE": 100,
    "WHEELODEX_FILE_SEARCH_RESULTS_PER_WHEEL": 5,
    "WHEELODEX_RECENT_WHEELS_QTY": 100,
    "WHEELODEX_STATS_LOG_DIR": None,
    "WHEELODEX_RDEPENDS_LEADERS_QTY": 100,
}


def create_app(**kwargs: Any) -> Flask:
    app = Flask("wheelodex")
    app.config.update(DEFAULT_CONFIG)
    if "WHEELODEX_CONFIG" in os.environ:
        app.config.from_envvar("WHEELODEX_CONFIG")
    app.config.update(kwargs)
    from .models import db

    db.init_app(app)
    Migrate(app, db, directory=str(Path(__file__).with_name("migrations")))
    from .views import web

    app.register_blueprint(web)
    return app


def emit_json_log(logname: str, data: dict) -> None:
    logdir = current_app.config["WHEELODEX_STATS_LOG_DIR"]
    if logdir is not None:
        logfile = Path(logdir, logname)
        logfile.parent.mkdir(parents=True, exist_ok=True)
        with logfile.open("a", encoding="utf-8") as fp:
            print(json.dumps(data), file=fp)
