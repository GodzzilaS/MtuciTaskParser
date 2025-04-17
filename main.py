import asyncio
import logging
import platform

from telegram import ReplyKeyboardMarkup, BotCommand
from telegram.ext import ApplicationBuilder, Application

from core.settings import Settings
from bot.handlers import register_handlers
from scheduler import background_check

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    settings = Settings()

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
