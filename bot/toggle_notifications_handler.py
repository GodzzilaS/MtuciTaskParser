import logging

from telegram import Update
from telegram.ext import ContextTypes

from core.models.command_config import CommandConfig
from core.models.users import select_user
from utils.check_utils import available_or_message, measure_duration

logger = logging.getLogger(__name__)


def toggle_notifications():
    """
    /toggle_notifications — Переключить уведомления у пользователя.
    """

    @available_or_message
    @measure_duration("toggle_notifications")
    async def _toggle_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
        cfg = CommandConfig.get("toggle_notifications")
        tg_id = update.effective_user.id
        user = select_user(tg_id)
        if not user or not user.mtuci_login:
            await update.message.reply_text(cfg.get_message("not_authorized"))
            return

        user.notifications = not user.notifications
        await update.message.reply_text(cfg.get_message("success", user_notifications='включили' if user.notifications else 'выключили'), parse_mode="Markdown")

    return _toggle_notifications
