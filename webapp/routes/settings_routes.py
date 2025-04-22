import asyncio
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from telegram import Bot

from core.models.command_config import CommandConfig
from core.models.config import get_schedule_interval, set_schedule_interval
from . import login_required

settings_bp = Blueprint("settings", __name__)


@settings_bp.route("/settings", methods=["GET"])
@login_required
def view_settings():
    bot = Bot(token=current_app.config["SETTINGS"].BOT_TOKEN)

    async def get_data():
        name = await bot.get_my_name()
        desc = await bot.get_my_short_description()
        return name.name, desc.short_description

    bot_name, bot_about = asyncio.run(get_data())
    return render_template(
        "settings.html",
        interval=get_schedule_interval(),
        command_configs=[cmd.__dict__() for cmd in CommandConfig.get_all()],
        bot_name=bot_name,
        bot_about=bot_about
    )


@settings_bp.route("/edit_interval", methods=["POST"])
@login_required
def edit_interval():
    try:
        interval = int(request.form["interval"])
        set_schedule_interval(interval)
        flash(f"Интервал проверки изменён: {interval} мин.", "info")
    except (ValueError, KeyError):
        flash("Ошибка формата интервала", "error")
    return redirect(url_for("settings.view_settings"))


@settings_bp.route("/create_command", methods=["POST"])
@login_required
def create_command():
    try:
        new_cmd = request.form.get("new_command_name", "").replace("/", "")
        if new_cmd == "":
            flash("Вы не указали имя команды", "warn")
            return redirect(url_for("settings.view_settings"))

        exist = CommandConfig.exist(new_cmd)
        if exist:
            flash(f"Команда /{new_cmd} уже существует", "warn")
        else:
            CommandConfig.get(new_cmd)
            flash(f"Команда /{new_cmd} добавлена", "info")

    except Exception as e:
        print(e)
        flash("Ошибка создания команды", "error")

    return redirect(url_for("settings.view_settings"))


@settings_bp.route("/update_command", methods=["POST"])
@login_required
def update_command():
    try:
        command_name = request.form["command_name"]
        messages = {}

        for field in request.form:
            if field.startswith("key__"):
                index = field.split("__")[1]
                key = request.form[field]
                value = request.form.get(f"value__{index}")
                if key and value:
                    messages[key] = value

        CommandConfig.update(command_name, messages)
        flash("Сообщения обновлены", "info")
    except Exception as e:
        print(e)
        flash(f"Возникла ошибка при обновлении команды", "error")

    return redirect(url_for("settings.view_settings"))


@settings_bp.route("/update_bot_profile", methods=["POST"])
@login_required
def update_bot_profile():
    try:
        name = request.form.get("bot_name")
        about = request.form.get("bot_about")

        bot = Bot(token=current_app.config["SETTINGS"].BOT_TOKEN)

        async def update():
            if name:
                await bot.set_my_name(name=name)
            if about:
                await bot.set_my_short_description(short_description=about)

        asyncio.run(update())
        flash("Профиль бота обновлён", "info")
    except Exception as e:
        print(e)
        flash("Ошибка обновления профиля бота", "error")

    return redirect(url_for("settings.view_settings"))


@settings_bp.route("/delete_command", methods=["POST"])
@login_required
def delete_command():
    try:
        command_name = request.form.get("command_name", "").replace("/", "")
        if command_name == "":
            flash("Вы не указали имя команды", "warn")
            return redirect(url_for("settings.view_settings"))

        CommandConfig.delete(command_name)
        flash(f"Команда /{command_name} удалена", "info")
    except Exception as e:
        print(e)
        flash(f"Возникла ошибка при удалении команды", "error")

    return redirect(url_for("settings.view_settings"))
