import asyncio
import json
import logging
import os
import time
from collections import defaultdict
from datetime import datetime
from threading import Thread
from zoneinfo import ZoneInfo

from flask import Blueprint, render_template, redirect, url_for, request, session, flash, current_app, send_file

from core.db import get_collection, insert
from core.models import users
from core.models.config import get_bot_enabled, set_bot_enabled, set_maintenance_mode, get_maintenance_mode, \
    get_scheduled_enabled, set_scheduled_enabled, get_schedule_interval, set_schedule_interval
from scheduler import scheduled_check
from services.encryption import EncryptionService
from services.scraper import Scraper

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
        scheduled_enabled=get_scheduled_enabled(),
        interval=get_schedule_interval()
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

    data_coll = get_collection("data")
    authorizations_on_site = data_coll.count_documents({"type": "authorization_on_site"})
    login_time = session.get("login_time")
    session_time = None
    if login_time:
        seconds = int(time.time() - login_time)
        h, m, s = seconds // 3600, (seconds % 3600) // 60, seconds % 60
        session_time = f"{h}:{m:02}:{s:02}" if h > 0 else f"{m}:{s:02}"

    users_list = users.custom_select({})
    return render_template(
        "users.html",
        admin=session.get("admin_username"),
        session_time=session_time,
        authorizations_on_site=authorizations_on_site,
        users_list=users_list,
        courses_map=json.dumps(current_app.config["SETTINGS"].COURSES_MAP, ensure_ascii=False)
    )


@blueprint.route("/update_user", methods=["POST"])
def update_user():
    if not session.get("admin_logged_in"):
        return redirect(url_for("main.login"))

    try:
        telegram_id = request.form.get('telegram_id')
        if not telegram_id:
            flash("Не указан идентификатор пользователя", "error")
            return redirect(url_for("main.users_list_route"))

        user = users.select_user(int(telegram_id))
        if not user:
            flash("Пользователь не найден", "error")
            return redirect(url_for("main.users_list_route"))

        has_changes = False

        new_telegram = request.form.get('telegram_username')
        if user.telegram_username != new_telegram:
            user.telegram_username = new_telegram
            has_changes = True

        new_mtuci_login = request.form.get('mtuci_login') or None
        if user.mtuci_login != new_mtuci_login:
            user.mtuci_login = new_mtuci_login
            has_changes = True

        new_faculty = request.form.get('faculty') or None
        if user.faculty != new_faculty:
            user.faculty = new_faculty
            has_changes = True

        new_course = request.form.get('course') or None
        if user.course != new_course:
            user.course = new_course
            has_changes = True

        new_group = request.form.get('group') or None
        if user.group != new_group:
            user.group = new_group
            has_changes = True

        new_education_level = request.form.get('education_level') or None
        if user.education_level != new_education_level:
            user.education_level = new_education_level
            has_changes = True

        new_form = request.form.get('study_form') or None
        if user.study_form != new_form:
            user.study_form = new_form
            has_changes = True

        if has_changes:
            flash(f"Данные пользователя {user.telegram_username} успешно обновлены", "info")
        else:
            flash("Нет изменений для сохранения", "info")

    except ValueError as e:
        flash(f"Ошибка формата данных: {str(e)}", "error")
    except Exception as e:
        logger.error(f"Ошибка при обновлении пользователя: {str(e)}")
        flash("Произошла ошибка при обновлении", "error")

    return redirect(url_for("main.users_list_route"))


@blueprint.route("/delete_user", methods=["POST"])
def delete_user():
    if not session.get("admin_logged_in"):
        return redirect(url_for("main.login"))

    try:
        telegram_id = request.form.get('telegram_id')
        if not telegram_id:
            flash("Не указан идентификатор пользователя", "error")
            return redirect(url_for("main.users_list_route"))

        user = users.select_user(int(telegram_id))
        if not user:
            flash("Пользователь не найден", "error")
            return redirect(url_for("main.users_list_route"))

        users.remove_user(int(telegram_id))

        flash(f"Пользователь удален", "info")

    except ValueError as e:
        flash(f"Ошибка формата данных: {str(e)}", "error")
    except Exception as e:
        logger.error(f"Ошибка при обновлении пользователя: {str(e)}")
        flash("Произошла ошибка при обновлении", "error")

    return redirect(url_for("main.users_list_route"))


@blueprint.route('/run-check', methods=['POST'])
def run_check_route():
    """
    Запустить одну итерацию фоновой проверки в отдельном потоке.
    """
    settings = current_app.config['SETTINGS']

    def worker():
        scraper = Scraper(settings)
        encryptor = EncryptionService(settings.ENCRYPTION_KEY)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(scheduled_check(None,
                                                    settings,
                                                    scraper,
                                                    encryptor))
        finally:
            loop.close()

    Thread(target=worker, daemon=True).start()
    flash("✅ Ручная проверка задач запущена", "info")
    return redirect("/")


@blueprint.route('/settings', methods=['GET', 'POST'])
def schedule_settings_route():
    """
    Интерфейс для изменения интервала фоновой проверки.
    """
    if request.method == 'POST':
        try:
            interval = int(request.form.get('interval', 5))
            set_schedule_interval(interval)
            flash(f"✅ Интервал проверки изменён: {interval} мин.", "info")
        except ValueError:
            flash("❌ Неверный формат интервала", "danger")
        return redirect(url_for('main.schedule_settings_route'))

    # GET
    interval = get_schedule_interval()
    return render_template('settings.html', interval=interval)


@blueprint.route('/logs')
def view_logs_route():
    """
    Показывает последние 200 строк лога.
    """
    log_path = current_app.config['SETTINGS'].LOG_FILE
    print("DEBUG: смотрим лог по пути", log_path)
    lines = []
    if os.path.exists(log_path):
        with open(log_path, encoding='utf-8', errors='ignore') as f:
            for line in f.readlines():
                lines.append(line.replace('[32m', ''))
    return render_template('logs.html', logs=lines)


@blueprint.route('/logs/download')
def download_logs_route():
    """
    Скачать весь лог-файл.
    """
    log_path = current_app.config['SETTINGS'].LOG_FILE
    if not os.path.exists(log_path):
        flash("❌ Лог-файл не найден", "warning")
        return redirect(url_for('main.view_logs_route'))
    return send_file(log_path,
                     as_attachment=True,
                     download_name=os.path.basename(log_path))


@blueprint.route('/logs/clear', methods=['POST'])
def clear_logs_route():
    """
    Очистить лог-файл.
    """
    log_path = current_app.config['SETTINGS'].LOG_FILE
    try:
        open(log_path, 'w', encoding='utf-8').close()
        flash("✅ Логи успешно очищены", "info")
    except Exception as e:
        logger.error("Ошибка при очистке логов: %s", e)
        flash("❌ Не удалось очистить логи", "danger")
    return redirect(url_for('main.view_logs_route'))
