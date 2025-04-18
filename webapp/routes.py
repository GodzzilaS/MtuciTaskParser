import logging

from flask import Blueprint, render_template, redirect, url_for, request, session, flash, current_app

from core.models import users

blueprint = Blueprint('main', __name__)
logger = logging.getLogger(__name__)


@blueprint.route("/auth/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        settings = current_app.config["SETTINGS"]
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == settings.ADMIN_USERNAME and password == settings.ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            session["admin_username"] = username
            return redirect(url_for("main.root"))
        flash("Неверный логин или пароль", "error")
    return render_template("login.html")


@blueprint.route("/auth/logout")
def logout():
    session.clear()
    return redirect(url_for("main.login"))


@blueprint.route("/")
def root():
    if not session.get("admin_logged_in"):
        return redirect(url_for("main.login"))

    return render_template("index.html", admin=session.get("admin_username"))


@blueprint.route("/users")
def users_list_route():
    if not session.get("admin_logged_in"):
        return redirect(url_for("main.login"))

    users_list = users.custom_select({})
    logger.info(users_list)
    return render_template("index.html", admin=session.get("admin_username"), users_list=users_list)
