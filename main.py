import asyncio
import logging
import os
import platform
import sys
from datetime import timedelta
from threading import Thread

import colorlog
from flask import Flask, redirect
from telegram import ReplyKeyboardMarkup, BotCommand
from telegram.ext import ApplicationBuilder, Application

from core.settings import Settings
from bot.handlers import register_handlers
from scheduler import background_check
from utils import blueprints_utils
from utils.logger_utils import SafeColorHandler, CustomLogMiddleware

LOG_FORMAT = "[{asctime}] {log_color}{name:^24} | {levelname:^8} | {message}"
DATE_FORMAT = "%d.%m.%Y %H:%M:%S"
LOG_COLORS = {
    "DEBUG": "cyan",
    "INFO": "green",
    "WARNING": "yellow",
    "ERROR": "red",
    "CRITICAL": "bold_red",
}

for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

formatter = colorlog.ColoredFormatter(
    fmt=LOG_FORMAT,
    datefmt=DATE_FORMAT,
    log_colors=LOG_COLORS,
    reset=False,
    style='{'
)

handler = SafeColorHandler(stream=sys.stdout)
handler.setFormatter(formatter)

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(handler)

logger = logging.getLogger(__name__)


def create_flask_app(settings: Settings) -> Flask:
    base = os.path.dirname(__file__)
    app = Flask(
        __name__,
        template_folder=os.path.join(base, "webapp", "templates"),
        static_folder=os.path.join(base, "webapp", "static")
    )
    app.wsgi_app = CustomLogMiddleware(app.wsgi_app)
    app.config["SETTINGS"]: Settings = settings
    app.config["SESSION_PERMANENT"] = True
    app.secret_key = settings.ENCRYPTION_KEY
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=5)
    blueprints_utils.inject('webapp', app)

    @app.errorhandler(404)
    def page_not_found(e):
        return redirect('/')

    return app


def run_webadmin(settings: Settings):
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    app = create_flask_app(settings)
    app.run(host='0.0.0.0', port=5000, debug=False)


def main():
    settings = Settings()

    # 1. Запускаем нашу веб-админку
    Thread(target=run_webadmin, args=(settings,), daemon=True).start()

    # 2. Настраиваем и запускаем Telegram‑бота
    keyboard = ReplyKeyboardMarkup(
        [["/login", "/get_tasks"]],
        resize_keyboard=True
    )

    async def post_init(application: Application):
        await application.bot.set_my_commands([
            BotCommand("login", "Авторизация /login ваш_логин ваш_пароль"),
            # BotCommand("configure", "Настройка аккаунта для получения расписания"),
            BotCommand("get_tasks", "Получить список заданий из LMS"),
            BotCommand("get_timetable", "Получить расписание из LMS")
        ])

        if platform.system() != "Windows":
            asyncio.create_task(background_check(application))

    app = (
        ApplicationBuilder()
        .token(settings.BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    register_handlers(app, keyboard)

    app.run_polling()


if __name__ == "__main__":
    main()
