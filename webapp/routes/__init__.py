import time
from functools import wraps

from flask import session, redirect, url_for

from core.db import get_collection


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)

    return decorated


from .auth_routes import auth_bp
from .dashboard_routes import main_bp
from .user_routes import users_bp
from .check_routes import check_bp
from .settings_routes import settings_bp
from .logs_routes import logs_bp
from .tasks_routes import tasks_bp


def register_blueprints(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(users_bp, url_prefix="/users")
    app.register_blueprint(check_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(logs_bp, url_prefix="/logs")
    app.register_blueprint(tasks_bp, url_prefix="/tasks")

    @app.context_processor
    def inject_common():
        """
        Прокидывает в шаблоны:
         - admin: имя администратора
         - session_time: сколько админ в сессии
         - authorizations_on_site: сколько логинов на сайте
        """
        admin = session.get("admin_username")
        session_time = None
        if session.get("login_time"):
            seconds = int(time.time() - session["login_time"])
            h, m, s = seconds // 3600, (seconds % 3600) // 60, seconds % 60
            session_time = f"{h}:{m:02}:{s:02}" if h > 0 else f"{m}:{s:02}"

        data_coll = get_collection("data")
        authorizations_on_site = data_coll.count_documents({"type": "authorization_on_site"})

        return dict(
            admin=admin,
            session_time=session_time,
            authorizations_on_site=authorizations_on_site
        )