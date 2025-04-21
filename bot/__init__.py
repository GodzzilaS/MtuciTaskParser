import logging
from telegram import ReplyKeyboardMarkup
from telegram.ext import CommandHandler

from core.settings import Settings
from services.encryption import EncryptionService
from services.scraper import Scraper

from .start_handler import start
from .login_handler import login
from .tasks_handler import get_tasks
from .timetable_handler import get_timetable

logger = logging.getLogger(__name__)


def register_handlers(app, keyboard: ReplyKeyboardMarkup):
    """
    Регистрирует все команды бота.
    """
    settings = Settings()
    encryptor = EncryptionService(settings.ENCRYPTION_KEY)
    scraper = Scraper(settings)

    # Доступ к scraper из любых хендлеров, если нужно
    app.bot_data["scraper"] = scraper

    # Основные команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("login", login(encryptor)))
    app.add_handler(CommandHandler("get_tasks", get_tasks(settings, encryptor, scraper), block=False))
    app.add_handler(CommandHandler("get_timetable", get_timetable(settings, encryptor, scraper), block=False))
