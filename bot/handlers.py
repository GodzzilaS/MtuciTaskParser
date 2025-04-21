import asyncio
import logging
import time
from collections import defaultdict

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import CommandHandler, ConversationHandler, ContextTypes

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

(
    LEVEL, FORM, FACULTY,
    COURSE, GROUP
) = range(5)
LEVELS = ("Бакалавариат", "Магистратура", "Специалитет", "Аспирантура")
FORMS = ("Очная", "Очно-заочная", "Заочная")
FORMS_MAP = {
    "Бакалавариат": ["Очная", "Очно-заочная", "Заочная"],
    "Магистратура": ["Очная", "Очно-заочная", "Заочная"],
    "Специалитет": ["Очная"],
    "Аспирантура": ["Очная"],
}
FACULTIES_MAP = {
    "Бакалавариат": {
        "Очная": [
            "Информационные технологии",
            "Кибернетика и информационная безопасность",
            "Радио и телевидение",
            "Сети и системы связи",
            "Цифровая экономика и массовые коммуникации"
        ],
        "Очно-заочная": [
            "Центр индивидуального обучения"
        ],
        "Заочная": [
            "Центр заочного обучения по программам бакалавриата",
            "Центр индивидуального обучения"
        ]
    },
    "Магистратура": {
        "Очная": [
            "Информационные технологии",
            "Кибернетика и информационная безопасность",
            "Радио и телевидение",
            "Сети и системы связи",
            "Цифровая экономика и массовые коммуникации"
        ],
        "Очно-заочная": [
            "Центр заочного обучения по программам магистратуры"
        ],
        "Заочная": [
            "Центр заочного обучения по программам бакалавриата",
            "Центр заочного обучения по программам магистратуры"
        ]
    },
    "Специалитет": {
        "Очная": ["Кибернетика и информационная безопасность"]
    },
    "Аспирантура": {
        "Очная": ["Отдел аспирантуры"]
    }
}
COURSES = ("Первый", "Второй", "Третий", "Четвёртый", "Пятый")


def register_handlers(app, keyboard: ReplyKeyboardMarkup):
    settings = Settings()
    encryptor = EncryptionService(settings.ENCRYPTION_KEY)
    scraper = Scraper(settings)

    app.bot_data["scraper"] = scraper

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("login", login(encryptor)))
    app.add_handler(CommandHandler("get_tasks", get_tasks(settings, encryptor, scraper)))
    app.add_handler(CommandHandler("get_timetable", get_timetable(settings, encryptor, scraper)))

    # conv = ConversationHandler(
    #     entry_points=[CommandHandler("configure", start_config)],
    #     states={
    #         LEVEL: [
    #             CallbackQueryHandler(cancel, pattern="^cancel$"),
    #             CallbackQueryHandler(on_level, pattern="^(" + "|".join(LEVELS) + ")$"),
    #         ],
    #         FORM: [
    #             CallbackQueryHandler(cancel, pattern="^cancel$"),
    #             CallbackQueryHandler(on_form, pattern="^(" + "|".join(FORMS) + ")$"),
    #         ],
    #         FACULTY: [
    #             CallbackQueryHandler(cancel, pattern="^cancel$"),
    #             CallbackQueryHandler(on_faculty),
    #         ],
    #         COURSE: [
    #             CallbackQueryHandler(cancel, pattern="^cancel$"),
    #             CallbackQueryHandler(on_course, pattern="^(" + "|".join(COURSES) + ")$"),
    #         ],
    #         GROUP: [
    #             CallbackQueryHandler(cancel, pattern="^cancel$"),
    #             CallbackQueryHandler(on_group),
    #         ],
    #     },
    #     fallbacks=[
    #         CommandHandler("cancel", cancel),
    #     ],
    #     allow_reentry=True,
    # )
    # app.add_handler(conv)


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


async def start_config(update, context):
    # Шаг 1: выбор уровня образования
    keyboard = [[InlineKeyboardButton(lvl, callback_data=lvl)] for lvl in LEVELS] + [
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]]
    await update.message.reply_text("Шаг 1: выберите уровень образования:", reply_markup=InlineKeyboardMarkup(keyboard))
    return LEVEL


async def on_level(update, context):
    # Шаг 2: выбор формы обучения
    lvl = update.callback_query.data
    context.user_data['level'] = lvl
    await update.callback_query.answer()

    forms = FORMS_MAP[lvl]
    keyboard = [[InlineKeyboardButton(f, callback_data=f)] for f in forms]
    keyboard += [[InlineKeyboardButton("❌ Отмена", callback_data="cancel")]]

    await update.callback_query.edit_message_text(
        f"Шаг 2: уровень *{lvl}* выбран.\nТеперь форма обучения:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return FORM


async def on_form(update, context):
    # Шаг 3: выбор факультета
    form = update.callback_query.data
    context.user_data["form"] = form
    await update.callback_query.answer()

    level = context.user_data["level"]
    facs = FACULTIES_MAP.get(level, {}).get(form, [])

    if not facs:
        await update.callback_query.edit_message_text(
            "⚠️ К сожалению, для выбранных уровня и формы обучения факультетов не найдено.\nОбратитесь к https://t.me/GodzzilaS.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("❌ Отмена", callback_data="cancel")]]
            )
        )
        return FORM

    fac_ids = {f"fac_{i}": name for i, name in enumerate(facs)}
    context.user_data["fac_ids"] = fac_ids

    keyboard = [
        [InlineKeyboardButton(name, callback_data=fac_id)]
        for fac_id, name in fac_ids.items()
    ]
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])

    await update.callback_query.edit_message_text(
        f"Шаг 3: форма *{form}*.\nТеперь выберите факультет:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return FACULTY


async def on_faculty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Шаг 4: выбор курса
    fac_id = update.callback_query.data
    await update.callback_query.answer()

    faculty = context.user_data['fac_ids'].get(fac_id)
    context.user_data['faculty'] = faculty or "—"

    level = context.user_data['level']
    form = context.user_data['form']

    courses = COURSES_MAP.get(level, {}).get(form, {}).get(faculty, [])

    if not courses:
        await update.callback_query.edit_message_text(
            "⚠️ Для выбранных уровня, формы и факультета курсов не найдено.\nОбратитесь к https://t.me/GodzzilaS.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("❌ Отмена", callback_data="cancel")]]
            )
        )
        return FACULTY

    keyboard = [[InlineKeyboardButton(c, callback_data=c)] for c in courses]
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])

    await update.callback_query.edit_message_text(
        f"Шаг 4: факультет *{faculty}*.\nТеперь выберите курс:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return COURSE


async def on_course(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Шаг 5: выбор группы
    context.user_data['course'] = update.callback_query.data
    await update.callback_query.answer()

    scraper: Scraper = context.bot_data["scraper"]
    lvl = context.user_data['level']
    form = context.user_data['form']
    faculty = context.user_data['faculty']
    course = context.user_data['course']

    waiting_msg = "⏳ Получаю список групп, пожалуйста подождите..."
    await update.callback_query.edit_message_text(waiting_msg)

    # ── получаем список групп в отдельном потоке ────────────
    def _fetch():
        logger.info(f"{lvl}, {form}, {faculty}, {course}")
        return scraper.get_groups(lvl, form, faculty, course)

    groups = await asyncio.to_thread(_fetch)

    if not groups:
        await update.callback_query.edit_message_text(
            "⚠️ Для выбранных параметров группы не найдены.\nОбратитесь к https://t.me/GodzzilaS.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("❌ Отмена", callback_data="cancel")]]
            )
        )
        return COURSE

    keyboard = [[InlineKeyboardButton(g, callback_data=g)] for g in groups]
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])

    await update.callback_query.edit_message_text(
        f"Курс: *{course}*\n\nВыберите группу:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return GROUP


async def on_group(update, context):
    # Шаг 6: сохранение настроек
    context.user_data['group'] = update.callback_query.data
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "Отлично! Я запомнил:\n"
        f"- Уровень: *{context.user_data['level']}*\n"
        f"- Форма: *{context.user_data['form']}*\n"
        f"- Факультет: *{context.user_data['faculty']}*\n"
        f"- Курс: *{context.user_data['course']}*\n"
        f"- Группа: *{context.user_data['group']}*",
        parse_mode="Markdown"
    )
    tg_id = update.effective_user.id
    user = select_user(tg_id)
    user.education_level = context.user_data['level']
    user.study_form = context.user_data['form']
    user.faculty = context.user_data['faculty']
    user.course = context.user_data['course']
    user.group = context.user_data['group']
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Отмена настройки
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text("❌ Настройка отменена.")
    else:
        await update.message.reply_text("❌ Настройка отменена.")
    return ConversationHandler.END
