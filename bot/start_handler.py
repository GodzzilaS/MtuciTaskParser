import logging
import time

from telegram import Update
from telegram.ext import ContextTypes

from core.db import insert
from core.models.command_config import CommandConfig
from utils.check_utils import available_or_message, measure_duration

logger = logging.getLogger(__name__)


@available_or_message
@measure_duration("start")
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /start — приветствие и инструктаж по авторизации.
    """
    insert("data", {
        "type": "command",
        "command": "start",
        "timestamp": time.time()
    })
    cfg = CommandConfig.get("start")
    await update.message.reply_html(cfg.get_message("main", user={"mention_html": update.effective_user.mention_html()}))
