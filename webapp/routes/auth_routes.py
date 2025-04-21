import logging
import time

from flask import Blueprint, render_template, request, session, redirect, url_for, flash, current_app

from core.db import insert
from core.settings import Settings

logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    settings: Settings = current_app.config["SETTINGS"]
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == settings.ADMIN_USERNAME and password == settings.ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            session["admin_username"] = username
            session["login_time"] = time.time()
            insert("data", {"type": "authorization_on_site", "timestamp": time.time()})
            return redirect(url_for("main.root"))
        flash("Неверный логин или пароль", "error")
    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
