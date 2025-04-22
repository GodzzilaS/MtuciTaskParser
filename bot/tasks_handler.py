import asyncio
import logging
import time

from telegram import Update
from telegram.ext import ContextTypes

from core.db import insert
from core.models.tasks import create_tasks_bulk
from core.models.users import select_user
from utils.check_utils import available_or_message, measure_duration
from utils.date_utils import short_date, compact_time
from utils.status_utils import status_emoji

logger = logging.getLogger(__name__)


def get_tasks(settings, encryptor, scraper):
    """
    /get_tasks — асинхронный сбор заданий через Selenium, запись в БД и вывод в чат.
    """

    @available_or_message
    @measure_duration("get_tasks")
    async def _get_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
        tg_id = update.effective_user.id
        user = select_user(tg_id)
        if not user or not user.mtuci_login:
            await update.message.reply_text("❌ Сначала авторизуйся через /login")
            return

        insert("data", {
            "type": "command",
            "command": "get_tasks",
            "timestamp": time.time()
        })
        pwd = encryptor.decrypt(user.mtuci_password)

        status_msg = await update.message.reply_text(
            "🔄 Получаю задания, это займёт время..."
        )

        def fetch_assignments():
            driver = scraper.init_driver()
            try:
                scraper.login(driver, user.mtuci_login, pwd)
                by_course: dict[str, list[list[str]]] = {}
                for link in scraper.get_course_links(driver):
                    raws = scraper.parse_assignments_from_course(driver, link)
                    for item in raws:
                        course = item[0]
                        by_course.setdefault(course, []).append(item)
                return by_course
            finally:
                scraper.quit_and_clear(driver)

        try:
            assignments_by_course = await asyncio.to_thread(fetch_assignments)
        except Exception:
            assignments_by_course = None

        if not assignments_by_course:
            await status_msg.edit_text("❌ Заданий не найдено.")
            return

        # Подготовка массива для bulk‑записи
        tasks_data = []
        for course, raws in assignments_by_course.items():
            for item in raws:
                tasks_data.append({
                    "task_link": item[4],
                    "course": course,
                    "task_name": item[1],
                    "open_date": short_date(item[2]) if item[2] else "не указано",
                    "due_date": short_date(item[3]) if item[3] else "не указано",
                    "response_status": item[5],
                    "grade_status": item[6],
                    "time_left": compact_time(item[7]),
                    "last_change": item[8]
                })

        create_tasks_bulk(tg_id, tasks_data)

        # Формирование текстового вывода с учётом ограничения длины
        max_len = settings.MAX_MESSAGE_LENGTH
        chunks: list[str] = []
        current = ""
        for course, raws in assignments_by_course.items():
            header = f"\n<b>🎓 {course}</b>\n"
            block = ""
            for item in raws:
                grade_emo, resp_emo = status_emoji(item[5], item[6])
                block += (
                    f"<b>📌 {item[1]}</b>\n"
                    f"┃\n"
                    f"┠─🗓 <i>Открыто:</i> {short_date(item[2]) if item[2] else 'не указано'}\n"
                    f"┠─⏳ <i>Сдать до:</i> {short_date(item[3]) if item[3] else 'не указано'}\n"
                    f"┠─{resp_emo} <i>Статус:</i> {item[5]}\n"
                    f"┠─{grade_emo} <i>Оценка:</i> {item[6].split(':')[-1].strip()}\n"
                    f"┠─⏱ <i>Осталось:</i> {compact_time(item[7])}\n"
                    f"┖─🔗 <a href=\"{item[4]}\">Перейти к заданию</a>\n"
                    "<i>─────────────────────</i>\n\n"
                )
            if len(current) + len(header + block) > max_len:
                chunks.append(current)
                current = header + block
            else:
                current += header + block

        if current:
            chunks.append(current)

        # Отправка в чат
        await status_msg.edit_text(
            chunks[0], parse_mode="HTML", disable_web_page_preview=True
        )
        for c in chunks[1:]:
            await update.message.reply_text(
                c, parse_mode="HTML", disable_web_page_preview=True
            )

    return _get_tasks
