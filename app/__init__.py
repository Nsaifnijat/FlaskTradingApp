from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate


# Globals
db = SQLAlchemy()
migrate = Migrate()

def init_app():
    """Initialize the core app"""
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object('config.Config')

    # Plugins
    db.init_app(app)
    migrate.init_app(app, db)

    with app.app_context():
        from . import routes

        return app