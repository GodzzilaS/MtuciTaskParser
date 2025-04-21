import logging
import time

from telegram import Update
from telegram.ext import ContextTypes

from core.db import insert
from utils.check_utils import available_or_message, measure_duration

logger = logging.getLogger(__name__)


@available_or_message
@measure_duration("start")
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /start — приветствие и инструктаж по авторизации.
    """
    user = update.effective_user
    insert("data", {
        "type": "command",
        "command": "start",
        "timestamp": time.time()
    })
    await update.message.reply_html(
        f"Привет, {user.mention_html()}!\n"
        "Чтобы подключить LMS, отправь:\n"
        "/login твой_логин твой_пароль"
    )
