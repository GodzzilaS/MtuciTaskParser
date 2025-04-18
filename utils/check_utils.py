# check_utils.py
import time
from functools import wraps

from telegram import Update
from telegram.ext import ContextTypes

from core.db import insert
from core.models.config import get_bot_enabled, get_maintenance_mode


def is_available():
    """
    Проверяет флаги из config:
      – если бот выключен — возвращает (False, 'disabled')
      – если на тех.работах — (False, 'maintenance')
      – иначе (True, None)
    """
    if not get_bot_enabled():
        return False, "disabled"
    if get_maintenance_mode():
        return False, "maintenance"
    return True, None


def available_or_message(func):
    """
    Декоратор для async‑функций‑хендлеров.
    Если бот недоступен — шлёт пользователю причину и НЕ вызывает оригинальный хендлер.
    """

    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        ok, reason = is_available()
        if not ok:
            text = (
                "❌ Бот выключен."
                if reason == "disabled"
                else "⚙️ Сейчас идут технические работы, попробуйте позже."
            )

            msg = getattr(update, "message", None) or getattr(update, "callback_query", None).message
            await msg.reply_text(text)
            return
        return await func(update, context)

    return wrapper


def measure_duration(command_name):
    """
    Декоратор, который вокруг handler-а меряет время и пишет в data:
      { type: 'command_duration', command, start, end, duration }
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(update, context):
            start_ts = time.time()
            try:
                return await func(update, context)
            finally:
                end_ts = time.time()
                insert("data", {
                    "type": "command_duration",
                    "command": command_name,
                    "start": start_ts,
                    "end": end_ts,
                    "duration": end_ts - start_ts
                })

        return wrapper

    return decorator
