import logging
import time

from telegram import Update
from telegram.ext import ContextTypes

from core.db import insert
from core.models.command_config import CommandConfig
from core.models.users import create_user, select_user, exist
from services.scraper import Scraper
from utils.check_utils import available_or_message, measure_duration

logger = logging.getLogger(__name__)


def login(encryptor):
    """
    /login — шифрование пароля и сохранение/обновление пользователя в БД.
    """

    @available_or_message
    @measure_duration("login")
    async def _login(update: Update, context: ContextTypes.DEFAULT_TYPE):
        insert("data", {
            "type": "command",
            "command": "login",
            "timestamp": time.time()
        })
        cfg = CommandConfig.get("login")

        args = context.args
        if len(args) != 2:
            await update.message.reply_text(cfg.get_message("incorrect_format"))
            return

        login_name, pwd = args
        status_msg = await update.message.reply_text(cfg.get_message("check_data"))

        try:
            scraper: Scraper = context.bot_data["scraper"]
            scraper.login(scraper.init_driver(False), login_name, pwd)
        except Exception:
            await status_msg.edit_text(cfg.get_message("incorrect_data"))
            return

        encrypted = encryptor.encrypt(pwd)
        tg_id = update.effective_user.id
        username = update.effective_user.username or ""

        if exist(tg_id):
            user = select_user(tg_id)
            user.mtuci_login = login_name
            user.mtuci_password = encrypted
        else:
            create_user(tg_id, username, login_name, encrypted)

        await status_msg.edit_text(cfg.get_message("correct_data"))

    return _login
