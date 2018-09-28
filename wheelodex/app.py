import os
from   flask import Flask

DEFAULT_CONFIG = {
    "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    "SQLALCHEMY_TRACK_MODIFICATIONS": False,
}

def create_app():
    app = Flask('wheelodex')
    app.config.update(DEFAULT_CONFIG)
    if "WHEELODEX_CONFIG" in os.environ:
        app.config.from_envvar("WHEELODEX_CONFIG")
    from .db import db
    db.init_app(app)
    from .views import web
    app.register_blueprint(web)
    return app
