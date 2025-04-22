import asyncio
import logging
import time
from collections import defaultdict

from telegram import Update
from telegram.ext import ContextTypes

from core.db import insert
from core.models.users import select_user
from utils.check_utils import available_or_message, measure_duration

logger = logging.getLogger(__name__)


def get_timetable(settings, encryptor, scraper):
    """
    /get_timetable — парсинг расписания пользователя, группировка по дате/времени.
    """

    @available_or_message
    @measure_duration("get_timetable")
    async def _get_timetable(update: Update, context: ContextTypes.DEFAULT_TYPE):
        tg_id = update.effective_user.id
        user = select_user(tg_id)
        if not user or not user.mtuci_login:
            await update.message.reply_text("❌ Сначала авторизуйся через /login")
            return

        insert("data", {
            "type": "command",
            "command": "get_timetable",
            "timestamp": time.time()
        })

        status_msg = await update.message.reply_text("🔄 Получаю календарь на месяц, это может занять время…")

        def _fetch():
            driver = scraper.init_driver()
            try:
                return scraper.get_timetable(
                    driver,
                    user.mtuci_login,
                    encryptor.decrypt(user.mtuci_password)
                )
            finally:
                scraper.quit_and_clear(driver)

        try:
            entries = await asyncio.to_thread(_fetch)
        except Exception:
            await status_msg.edit_text("❌ Ошибка при получении расписания.")
            return

        entries = sorted(entries, key=lambda e: (e["date"], e["time_of_lesson"]))

        grouped = defaultdict(lambda: defaultdict(list))
        for e in entries:
            grouped[e["date"]][e["time_of_lesson"]].append(e)

        chunks: list[str] = []
        current = ""
        for date in sorted(grouped.keys()):
            date_header = f"\n📆 *{date}*\n"
            day_block = date_header
            for time_of_lesson in sorted(grouped[date].keys()):
                lessons = grouped[date][time_of_lesson]
                combined = defaultdict(list)
                for e in lessons:
                    key = (e["type"], e["lesson"])
                    combined[key].append((e["teacher"], e["cabinet"]))
                for (lesson_type, lesson_name), teachers in combined.items():
                    day_block += f"**{lesson_type}** ({time_of_lesson})\n"
                    day_block += f"▫️ *Предмет:* {lesson_name}\n"
                    for teacher, cabinet in teachers:
                        cab = f", {cabinet}" if lesson_type != "Дистанционно" else ""
                        day_block += f"▫️ *Преподаватель:* {teacher}{cab}\n"
                    day_block += "\n"
            if len(current) + len(day_block) > settings.MAX_MESSAGE_LENGTH:
                chunks.append(current.strip())
                current = day_block
            else:
                current += day_block

        if current:
            chunks.append(current.strip())

        # Отправка
        await status_msg.edit_text(
            chunks[0], parse_mode="Markdown"
        )
        for part in chunks[1:]:
            await update.message.reply_text(
                part, parse_mode="Markdown"
            )

    return _get_timetable
