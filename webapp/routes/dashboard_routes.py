import logging
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Blueprint, render_template, redirect, url_for, flash

from core.db import get_collection
from core.models.config import (get_bot_enabled, set_bot_enabled, get_maintenance_mode, set_maintenance_mode,
                                get_scheduled_enabled, set_scheduled_enabled, get_schedule_interval)
from . import login_required

logger = logging.getLogger(__name__)
main_bp = Blueprint("main", __name__)


@main_bp.route("/")
@login_required
def root():
    data_coll = get_collection("data")

    # статистика фоновых проверок
    total_schedule = data_coll.count_documents({"type": "scheduled_check"})
    last = data_coll.find({"type": "scheduled_check"}) \
        .sort("end_ts", -1) \
        .limit(1)
    last_schedule = None
    for d in last:
        moscow_time = datetime.fromtimestamp(d["end_ts"], tz=ZoneInfo("UTC")).astimezone(ZoneInfo("Europe/Moscow"))
        last_schedule = moscow_time.strftime("%d.%m.%Y %H:%M:%S")

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
            moscow_time = datetime.fromtimestamp(data["last"], tz=ZoneInfo("UTC")).astimezone(ZoneInfo("Europe/Moscow"))
            data["last"] = moscow_time.strftime("%d.%m.%Y %H:%M")

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
        scheduled_enabled=get_scheduled_enabled(),
        interval=get_schedule_interval()
    )


@main_bp.route("/toggle_bot")
@login_required
def toggle_bot():
    new = not get_bot_enabled()
    set_bot_enabled(new)
    flash(f"Бот {'включён' if new else 'выключен'}", "info")
    return redirect(url_for("main.root"))


@main_bp.route("/toggle_maintenance")
@login_required
def toggle_maintenance():
    new = not get_maintenance_mode()
    set_maintenance_mode(new)
    flash(f"Тех.работы {'включены' if new else 'выключены'}", "info")
    return redirect(url_for("main.root"))


@main_bp.route("/toggle_scheduled")
@login_required
def toggle_scheduled():
    new = not get_scheduled_enabled()
    set_scheduled_enabled(new)
    flash(f"Плановые проверки {'включены' if new else 'выключены'}", "info")
    return redirect(url_for("main.root"))
