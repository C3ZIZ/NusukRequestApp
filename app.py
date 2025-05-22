import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix

# Base model
class Base(DeclarativeBase):
    pass

# Initialize SQLAlchemy with custom base
db = SQLAlchemy(model_class=Base)

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "hajj_card_service_secret_key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Set the DATABASE_URL for PostgreSQL compatibility
app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://nusuk_db_user:5sLEgCU31JmgCfOxfwiLAaIRC9XrOG5E@dpg-d0k6jmd6ubrc73b0v5e0-a.oregon-postgres.render.com/nusuk_db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize the database
db.init_app(app)

# Remove db.create_all() to avoid schema mismatch with managed PostgreSQL
with app.app_context():
    import models  # Ensure models are loaded
    # Do not call db.create_all() on managed PostgreSQL


