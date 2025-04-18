import logging
import time
from collections import defaultdict
from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, request, session, flash, current_app

from core.db import get_collection, insert
from core.models import users
from core.models.config import get_bot_enabled, set_bot_enabled, set_maintenance_mode, get_maintenance_mode, \
    get_scheduled_enabled, set_scheduled_enabled

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
            session["login_time"] = time.time()
            insert("data", {"type": "authorization_on_site", "timestamp": time.time()})
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

    data_coll = get_collection("data")

    # сессии
    authorizations_on_site = data_coll.count_documents({"type": "authorization_on_site"})
    login_time = session.get("login_time")
    session_time = None
    if login_time:
        seconds = int(time.time() - login_time)
        h, m, s = seconds // 3600, (seconds % 3600) // 60, seconds % 60
        session_time = f"{h}:{m:02}:{s:02}" if h > 0 else f"{m}:{s:02}"

    # статистика фоновых проверок
    total_schedule = data_coll.count_documents({"type": "scheduled_check"})
    last = data_coll.find({"type": "scheduled_check"}) \
        .sort("end_ts", -1) \
        .limit(1)
    last_schedule = None
    for d in last:
        last_schedule = datetime.fromtimestamp(d["end_ts"]).strftime("%Y-%m-%d %H:%M:%S")

    # статистика инициализаций драйвера
    driver_inits = data_coll.count_documents({"type": "driver_init"})

    # статистика новых пользователей
    new_users = data_coll.count_documents({"type": "new_user"})

    # статистика авторизаций
    authorizations = data_coll.count_documents({"type": "authorization"})
    success_authorization = data_coll.count_documents({"type": "success_authorization"})

    # счётчики команд
    commands_data = defaultdict(lambda: {"count": 0, "last": None})

    for d in data_coll.find({"type": "command"}):
        cmd = d.get("command", "unknown")
        ts = d.get("timestamp")
        commands_data[cmd]["count"] += 1
        if ts:
            if not commands_data[cmd]["last"] or ts > commands_data[cmd]["last"]:
                commands_data[cmd]["last"] = ts

    for cmd, data in commands_data.items():
        if data["last"]:
            data["last"] = datetime.fromtimestamp(data["last"]).strftime("%d.%m.%Y %H:%M")

    pipeline = [
        {"$match": {"type": "command_duration"}},
        {"$group": {
            "_id": "$command",
            "avg": {"$avg": "$duration"},
            "min": {"$min": "$duration"},
            "max": {"$max": "$duration"},
        }},
        {"$sort": {"_id": 1}}
    ]
    dur_stats = list(data_coll.aggregate(pipeline))
    command_stats = {
        d["_id"]: {
            "avg": round(d["avg"], 2),
            "min": round(d["min"], 2),
            "max": round(d["max"], 2)
        }
        for d in dur_stats
    }
    last_durations = {}
    for d in data_coll.find({"type": "command_duration"}).sort("end", -1):
        cmd = d["command"]
        if cmd not in last_durations:
            last_durations[cmd] = round(d["duration"], 2)

    # Вкладываем в command_stats
    for cmd, stats in command_stats.items():
        stats["last_duration"] = last_durations.get(cmd, None)

    return render_template(
        "index.html",
        admin=session.get("admin_username"),
        session_time=session_time,
        authorizations_on_site=authorizations_on_site,
        total_schedule=total_schedule,
        last_schedule=last_schedule,
        driver_inits=driver_inits,
        new_users=new_users,
        authorizations=authorizations,
        success_authorizations=success_authorization,
        commands_data=commands_data,
        command_stats=command_stats,
        bot_enabled=get_bot_enabled(),
        maintenance_mode=get_maintenance_mode(),
        scheduled_enabled=get_scheduled_enabled()
    )


@blueprint.route("/toggle_bot")
def toggle_bot():
    if not session.get("admin_logged_in"):
        return redirect(url_for("main.login"))

    new = not get_bot_enabled()
    set_bot_enabled(new)
    flash(f"Бот {'включён' if new else 'выключен'}", "info")
    return redirect(url_for("main.root"))


@blueprint.route("/toggle_maintenance")
def toggle_maintenance():
    if not session.get("admin_logged_in"):
        return redirect(url_for("main.login"))

    new = not get_maintenance_mode()
    set_maintenance_mode(new)
    flash(f"Режим тех.работ {'включён' if new else 'выключен'}", "info")
    return redirect(url_for("main.root"))


@blueprint.route("/toggle_scheduled")
def toggle_scheduled():
    if not session.get("admin_logged_in"):
        return redirect(url_for("main.login"))

    new = not get_scheduled_enabled()
    set_scheduled_enabled(new)
    flash(f"Плановые проверки {'включены' if new else 'выключены'}", "info")
    return redirect(url_for("main.root"))


@blueprint.route("/users")
def users_list_route():
    if not session.get("admin_logged_in"):
        return redirect(url_for("main.login"))

    users_list = users.custom_select({})
    logger.info(users_list)
    return render_template("users.html", admin=session.get("admin_username"), users_list=users_list)
