import asyncio
import logging
import time
from collections import defaultdict

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import CommandHandler, ContextTypes

from core.db import insert
from core.models.tasks import create_tasks_bulk
from core.models.users import create_user, select_user, exist
from core.settings import Settings
from services.encryption import EncryptionService
from services.scraper import Scraper
from utils.check_utils import available_or_message, measure_duration
from utils.date_utils import short_date, compact_time
from utils.status_utils import status_emoji

logger = logging.getLogger(__name__)


def register_handlers(app, keyboard: ReplyKeyboardMarkup):
    settings = Settings()
    encryptor = EncryptionService(settings.ENCRYPTION_KEY)
    scraper = Scraper(settings)

    app.bot_data["scraper"] = scraper

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("login", login(encryptor)))
    app.add_handler(CommandHandler("get_tasks", get_tasks(settings, encryptor, scraper), block=False))
    app.add_handler(CommandHandler("get_timetable", get_timetable(settings, encryptor, scraper), block=False))


@available_or_message
@measure_duration("start")
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    insert("data", {"type": "command", "command": "start", "timestamp": time.time()})
    await update.message.reply_html(
        f"Привет, {user.mention_html()}!\n"
        "Чтобы подключить LMS, отправь:\n"
        "/login твой_логин твой_пароль"
    )


def login(encryptor: EncryptionService):
    """
    /login логика: шифруем пароль, сохраняем или обновляем пользователя.
    """

    @available_or_message
    @measure_duration("login")
    async def _login(update: Update, context: ContextTypes.DEFAULT_TYPE):
        insert("data", {"type": "command", "command": "login", "timestamp": time.time()})

        args = context.args
        if len(args) != 2:
            await update.message.reply_text("❌ Неверный формат: /login логин пароль")
            return

        login_name, pwd = args
        encrypted = encryptor.encrypt(pwd)
        tg_id = update.effective_user.id
        username = update.effective_user.username or ""

        if exist(tg_id):
            user = select_user(tg_id)
            user.mtuci_login = login_name
            user.mtuci_password = encrypted
        else:
            create_user(tg_id, username, login_name, encrypted)

        await update.message.reply_text("✅ Данные успешно сохранены!")

    return _login


def get_tasks(settings: Settings, encryptor: EncryptionService, scraper: Scraper):
    """
    /get_tasks логика: offload в поток Selenium‑scraping,
    сохранение через create_tasks_bulk и отправка сообщений в чат.
    """

    @available_or_message
    @measure_duration("get_tasks")
    async def _get_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
        tg_id = update.effective_user.id
        user = select_user(tg_id)
        if not user or not user.mtuci_login:
            await update.message.reply_text("❌ Сначала авторизуйся через /login")
            return

        insert("data", {"type": "command", "command": "get_tasks", "timestamp": time.time()})
        pwd = encryptor.decrypt(user.mtuci_password)

        status_msg = await update.message.reply_text("🔄 Получаю задания, это займёт время...")

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
        except:
            assignments_by_course = None
            pass

        if not assignments_by_course:
            await status_msg.edit_text("❌ Заданий не найдено.")
            return

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

        await status_msg.edit_text(chunks[0], parse_mode="HTML", disable_web_page_preview=True)
        for c in chunks[1:]:
            await update.message.reply_text(c, parse_mode="HTML", disable_web_page_preview=True)

    return _get_tasks


def get_timetable(settings: Settings, encryptor, scraper):
    """
    /get_timetable логика: Парсим расписание с сайта личного кабинета.
    """

    @available_or_message
    @measure_duration("get_timetable")
    async def _get_timetable(update: Update, context: ContextTypes.DEFAULT_TYPE):
        tg_id = update.effective_user.id
        user = select_user(tg_id)

        if not user or not user.mtuci_login:
            await update.message.reply_text("❌ Сначала авторизуйся через /login")
            return

        insert("data", {"type": "command", "command": "get_timetable", "timestamp": time.time()})
        status_msg = await update.message.reply_text(
            "🔄 Получаю календарь на месяц, это может занять время…"
        )

        def _fetch():
            driver = scraper.init_driver()
            try:
                return scraper.get_timetable(
                    driver,
                    user.mtuci_login,
                    encryptor.decrypt(user.mtuci_password)
                )
            except Exception as e:
                print(e)
                pass

        try:
            entries = await asyncio.to_thread(_fetch)
        except Exception:
            await status_msg.edit_text("❌ Ошибка при получении расписания.")
            return

        entries = sorted(entries, key=lambda e: (e["date"], e["time_of_lesson"]))

        grouped = defaultdict(lambda: defaultdict(list))
        for e in entries:
            grouped[e['date']][e['time_of_lesson']].append(e)

        chunks: list[str] = []
        current = ""

        for date in sorted(grouped.keys()):
            date_header = f"\n📆 *{date}*\n"
            day_block = date_header

            for time_of_lesson in sorted(grouped[date].keys()):
                lessons = grouped[date][time_of_lesson]

                combined = defaultdict(list)
                for e in lessons:
                    key = (e['type'], e['lesson'])
                    combined[key].append((e['teacher'], e['cabinet']))

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

        await status_msg.edit_text(chunks[0], parse_mode="Markdown")
        for part in chunks[1:]:
            await update.message.reply_text(part, parse_mode="Markdown")

    return _get_timetable
