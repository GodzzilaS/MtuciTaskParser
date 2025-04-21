import asyncio
import logging
import time
import time as _time

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from telegram.ext import Application

from core.db import insert
from core.models.config import get_scheduled_enabled, get_schedule_interval
from core.models.tasks import custom_select as task_select
from core.models.users import custom_select as user_select
from core.settings import Settings
from services.encryption import EncryptionService
from services.scraper import Scraper

logger = logging.getLogger(__name__)


async def scheduled_check(
        app: Application,
        settings: Settings,
        scraper: Scraper,
        encryptor: EncryptionService
):
    """
    Основная точка входа — перебирает всех подписанных пользователей,
    запускает их проверку в параллельных потоках, ограниченных семафором
    """
    if get_scheduled_enabled():
        start_wall = time.time()
        tasks_list = list(task_select({}))
        total_tasks = len(tasks_list)
        users_with_tasks = {t.user_id for t in tasks_list}
        total_users_with_tasks = len(users_with_tasks)

        start_ts = time.perf_counter()
        logger.info("=== НАЧАЛО ПРОВЕРКИ ЗАДАНИЙ ===")

        users = list(user_select({"notifications": True}))
        logger.info(f"Пользователей для проверки: {len(users)}")

        sem = asyncio.Semaphore(settings.MAX_CONCURRENT_BROWSERS)
        tasks = [
            asyncio.create_task(
                _check_one_user(u, app, settings, scraper, encryptor, sem)
            )
            for u in users
        ]
        await asyncio.gather(*tasks)

        elapsed = time.perf_counter() - start_ts
        end_wall = time.time()
        logger.info(f"=== ПРОВЕРКА ЗАВЕРШЕНА (за {elapsed:.2f} с) ===")

        insert("data", {
            "type": "scheduled_check",
            "start_ts": start_wall,
            "end_ts": end_wall,
            "duration": elapsed,
            "total_tasks": total_tasks,
            "users_with_tasks": total_users_with_tasks,
            "checked_users": len(users)
        })

async def _check_one_user(
        user,
        app: Application,
        settings: Settings,
        scraper: Scraper,
        encryptor: EncryptionService,
        sem: asyncio.Semaphore
):
    """
    Обёртка для одной проверки пользователя:
    - offload синхронного _check_user_sync в поток
    - отправка сообщений об изменениях
    """
    async with sem:
        # offload тяжёлой работы в поток
        changes = await asyncio.to_thread(
            _check_user_sync, user, settings, scraper, encryptor
        )

        # теперь в async-контексте шлём телеграм‑сообщения
        for c in changes:
            text = (
                f"<b>Задача:</b> {c['course']} | {c['name']}\n"
                f"┠─ <b>Статус ответа:</b> {c['old_resp']} → {c['new_resp']}\n"
                f"┠─ <b>Оценка:</b> {c['old_grade']} → {c['new_grade']}\n"
                f"┖─ <b>Ссылка:</b> <a href=\"{c['link']}\">Перейти к заданию</a>"
            )
            if app is not None:
                await app.bot.send_message(
                    chat_id=user.telegram_id,
                    text=text,
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )


def _check_user_sync(user, settings, scraper: Scraper, encryptor: EncryptionService):
    """
    Всё синхронно: заводим WebDriver, логинимся, парсим задания,
    сравниваем старое/новое состояние, обновляем модель и собираем список изменений.
    Возвращает list[dict], где каждый dict = данные для одного уведомления.
    """
    driver = scraper.init_driver()
    wait = WebDriverWait(driver, 20)
    changes = []

    try:
        pwd = encryptor.decrypt(user.mtuci_password)
        scraper.login(driver, user.mtuci_login, pwd)

        db_tasks = list(task_select({"user_id": user.telegram_id}))
        logger.info(f"[{user.mtuci_login}] Задач в БД: {len(db_tasks)}")

        for task in db_tasks:
            try:
                driver.get(task.task_link)
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, "generaltable")))
                soup = BeautifulSoup(driver.page_source, "html.parser")

                table = soup.find("table", class_="generaltable table-bordered")
                if not table:
                    logger.warning(f"[{user.telegram_id}] Нет таблицы на {task.task_link}")
                    continue

                old_resp, old_grade = task.response_status, task.grade_status
                new_resp = new_grade = "—"
                for row in table.find_all("tr"):
                    th, td = row.find("th"), row.find("td")
                    if not (th and td):
                        continue
                    key, val = th.get_text(strip=True), td.get_text(strip=True)
                    if key == "Состояние ответа на задание":
                        new_resp = val
                    elif key == "Состояние оценивания":
                        new_grade = val

                if (new_resp != old_resp) or (new_grade != old_grade):
                    logger.info(
                        f"[{user.telegram_id}] Изменение «{task.task_name}»: "
                        f"{old_resp}→{new_resp}, {old_grade}→{new_grade}"
                    )
                    task.response_status = new_resp
                    task.grade_status = new_grade
                    task.last_updated = _time.time()

                    # добавляем в уведомления
                    changes.append({
                        "course": task.course,
                        "name": task.task_name,
                        "old_resp": old_resp,
                        "new_resp": new_resp,
                        "old_grade": old_grade,
                        "new_grade": new_grade,
                        "link": task.task_link
                    })
            except Exception as e:
                logger.exception(f"[{user.telegram_id}] Ошибка при проверке «{task.task_name}»: {e}")

    except Exception as e:
        logger.exception(f"[{user.telegram_id}] Ошибка в _check_user_sync: {e}")
    finally:
        scraper.quit_and_clear(driver)
        logger.info(f"[{user.telegram_id}] WebDriver закрыт")

    return changes


async def background_check(app):
    await asyncio.sleep(5)

    settings = Settings()
    scraper = Scraper(settings)
    encryptor = EncryptionService(settings.ENCRYPTION_KEY)

    while True:
        await scheduled_check(app, settings, scraper, encryptor)
        await asyncio.sleep(get_schedule_interval() * 60)
