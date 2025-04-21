import json
import logging
import subprocess
import time
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from core.db import insert

logger = logging.getLogger(__name__)

SUBJECTS_MAP = {
    "ТИДЗ": "Теория информации, данные, знания",
    "ИЯ": "Иностранный язык",
    "САИИО": "Системный анализ и исследование операций",
    "Ф": "Физика",
    "ДМ": "Дискретная математика",
    "ИТИП": "Информационные технологии и программирование",
    "ОП": "Основы права",
    "СИАОД": "Структуры и алгоритмы обработки данных"
}
OPTION_FLAGS = (
    "--disable-gpu", "--disable-extensions", "--disable-dev-shm-usage",
    "--no-sandbox", "--disable-background-timer-throttling",
    "--disable-background-networking", "--disable-client-side-phishing-detection",
    "--disable-default-apps", "--disable-popup-blocking", "--disable-translate",
    "--disable-application-cache", "--disk-cache-size=0", "--aggressive-cache-discard",
    "--no-zygote", "--incognito"
)
OPTION_PREFS = {
    "profile.managed_default_content_settings.images": 2,
    "profile.managed_default_content_settings.stylesheets": 2,
}


class Scraper:
    def __init__(self, settings):
        self.settings = settings

    @staticmethod
    def init_driver(load_css=False) -> webdriver.Chrome:
        insert("data", {"type": "driver_init", "timestamp": time.time()})
        options = Options()
        options.add_argument("--headless")

        for f in OPTION_FLAGS:
            options.add_argument(f)

        options.add_experimental_option("prefs", OPTION_PREFS)
        options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

        driver = webdriver.Chrome(options=options)

        if not load_css:
            driver.execute_cdp_cmd("Network.enable", {})
            driver.execute_cdp_cmd("Network.setBlockedURLs", {
                "urls": ["*.ttf", "*.svg", "*.css", "*.png", "*.jpg", "*.jpeg", "*.gif", "*.woff2", "*.mp4"]
            })

        return driver

    def login(self, driver, username: str, password: str):
        insert("data", {"type": "authorization", "timestamp": time.time()})
        wait = WebDriverWait(driver, 10)
        driver.get(self.settings.LOGIN_PAGE)
        wait.until(EC.presence_of_element_located((By.NAME, "username")))
        logger.info(f"[{username}] Входим в систему")
        driver.find_element(By.NAME, "username").send_keys(username)
        driver.find_element(By.NAME, "password").send_keys(password + Keys.RETURN)
        wait.until(EC.presence_of_element_located((By.ID, "page-content")))
        logger.info(f"[{username}] Успешно вошли в систему")
        insert("data", {"type": "success_authorization", "timestamp": time.time()})

    @staticmethod
    def _dom_click(driver: WebDriver, element):
        """
        Генерирует последовательность pointer‑ и mouse‑событий,
        которую ожидают скрипты Moodle/YUI.
        """
        driver.execute_script(
            """
            const down  = new PointerEvent('pointerdown', {bubbles:true});
            const up    = new PointerEvent('pointerup',   {bubbles:true});
            const click = new MouseEvent  ('click',       {bubbles:true});
            arguments[0].dispatchEvent(down);
            arguments[0].dispatchEvent(up);
            arguments[0].dispatchEvent(click);
            """,
            element,
        )

    def _robust_click(self, driver: WebDriver, el):
        self._scroll_into_view(driver, el)
        try:
            el.click()
        except Exception:
            pass
        self._dom_click(driver, el)
        ActionChains(driver).pause(0.15).perform()

    @staticmethod
    def _scroll_into_view(driver: WebDriver, el):
        driver.execute_script("arguments[0].scrollIntoView({block:'center',inline:'center'});", el)

    def _open_drawer(self, driver, wait):
        toggle = wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, '[data-region="drawer-toggle"]')
            )
        )
        self._robust_click(driver, toggle)
        wait.until(
            EC.visibility_of_element_located(
                (By.CSS_SELECTOR, '.drawer.show')
            )
        )

    def _locate_dropdown(self, driver: WebDriver, wait: WebDriverWait):
        """
        Возвращает WebElement кнопки‑триггера #displaydropdown.
        Если страница ушла в mobile‑drawer, сначала раскрывает панель.
        """
        try:
            return driver.find_element(By.ID, "displaydropdown")
        except NoSuchElementException:
            self._open_drawer(driver, wait)
            return wait.until(
                EC.element_to_be_clickable((By.ID, "displaydropdown"))
            )

    def _ensure_card_view(self, driver: WebDriver, wait: WebDriverWait) -> None:
        """
        Переключает список курсов в режим «Карточка».
        Работает с настольной и mobile‑drawer разметкой.
        """

        def current_mode() -> str:
            """Читаем подпись на кнопке (быстрее, чем парсить DOM)."""
            return driver.execute_script(
                "const b=document.getElementById('displaydropdown');"
                "if(!b) return '';"
                "const s=b.querySelector('span[data-active-item-text]');"
                "return (s?s.textContent:b.textContent).trim();"
            ) or ""

        for _ in range(3):
            dropdown_btn = self._locate_dropdown(driver, wait)

            if "Карточка" in current_mode():
                return

            driver.execute_script("arguments[0].click();", dropdown_btn)

            try:
                card_link = wait.until(
                    EC.element_to_be_clickable(
                        (By.CSS_SELECTOR,
                         "a[data-display-option='display'][data-value='card']")
                    )
                )
                self._robust_click(driver, card_link)

                wait.until(lambda d: "Карточка" in current_mode())
                return
            except (TimeoutException, StaleElementReferenceException):
                time.sleep(0.2)

        raise RuntimeError("Не удалось переключить страницу в режим «Карточка»")

    def get_course_links(self, driver) -> list[str]:
        """
        Парсим страницу «Мои курсы» и возвращаем список ссылок.
        """
        wait = WebDriverWait(driver, 20)
        driver.get(self.settings.MY_COURSES_PAGE)
        # Ждём загрузки страницы
        wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.dropdown.mb-1")))

        # Проверяем, что выбран правильный стиль отображения
        self._ensure_card_view(driver, wait)

        # Ждём загрузки карточек
        wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.col.d-flex.px-0.mb-2")))
        soup = BeautifulSoup(driver.page_source, "html.parser")
        links = []

        for div in soup.select("div.col.d-flex.px-0.mb-2"):
            a = div.find("a", href=True)
            if a:
                href = a["href"]
                links.append(href if href.startswith("http") else urljoin(self.settings.BASE_URL, href))

        return links

    def select_option(self, driver, container_id: str, visible_text: str):
        """
        В контейнере с id=container_id находим .switch-btn, .selector-btn или .groups-btn
        с текстом visible_text и кликаем по нему.
        Спецобработка для группы: идём в #groups_container.
        """
        try:
            wait = WebDriverWait(driver, 10)
            visible_text = visible_text.replace('\u00A0', ' ').strip()

            if container_id == "groups":
                wait.until(EC.visibility_of_element_located((By.ID, "groups_container")))
                xpath = (
                    "//div[@id='groups_container']"
                    f"/div[contains(@class,'groups-btn') and normalize-space()='{visible_text}']"
                )
                btn = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
            else:
                wait.until(EC.visibility_of_element_located((By.ID, container_id)))
                xpath = (
                    f"//div[@id='{container_id}']"
                    "//div[contains(@class,'switch-btn') or contains(@class,'selector-btn')]"
                    f"[normalize-space()='{visible_text}']"
                )
                btn = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))

            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
            time.sleep(0.1)
            btn.click()
            time.sleep(0.2)
        except Exception as e:
            driver.save_screenshot(f"error_{int(time.time())}.png")
            raise

    def get_timetable(self, driver, login, pwd):
        """
        Возвращает «сырое» JSON‑тело ответа от /ilk/x/getProcessor
        """
        self.login(driver, login, pwd)
        driver.get(self.settings.TIME_TABLE_URL)
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.schedule-lessons")))

        data = None
        for entry in driver.get_log("performance"):
            msg = json.loads(entry["message"])["message"]
            if msg.get("method") == "Network.responseReceived":
                url = msg["params"]["response"]["url"]
                if "getProcessor" in url:
                    req_id = msg["params"]["requestId"]
                    body = driver.execute_cdp_cmd("Network.getResponseBody", {"requestId": req_id})
                    data = json.loads(body["body"])
                    break

        if data is None:
            raise RuntimeError("Не удалось поймать ответ getProcessor")

        return self.parse_api_timetable(data)

    @staticmethod
    def parse_api_timetable(api_json: dict) -> list[dict]:
        """
        Из структуры api_json['data']['Ответ']['МассивРасписания']
        выдаёт список записей вида:
          {"date": "DD.MM.YYYY", "type": "...", "lesson": "...", "teacher": "...", ...}
        """
        days = api_json["data"]["Ответ"]["МассивРасписания"]
        out = []

        for day in days:
            datestr = datetime.strptime(day["Дата"], "%Y%m%d%H%M%S").strftime("%d.%m.%Y")
            for slot in day.get("СеткаРасписания", []):
                if slot.get("НетЗанятия") or slot.get("ГруппыСтудентов", "")[0].get("name", "") == "":
                    continue

                teacher = slot.get("Преподаватель", {}).get("name", "").strip() or "—"
                lesson = slot.get("Дисциплина", {}).get("name", "").strip() or "—"
                time_of_lesson = slot.get("Занятие", {}).get("name", "").strip() or "—"
                cabinet = slot.get("Аудитория", "").strip()
                is_online = slot.get("Дистанционно", False)

                lesson_type = slot.get("ВидНагрузки", {}).get("name", "").strip()
                control_form = slot.get("ФормаКонтроля", {}).get("name", "").strip()

                if control_form == "Зачет":
                    control_form = "Зачёт (ПЕРЕСДАЧА)"

                if not lesson_type and is_online:
                    lesson_type = "Дистанционно"

                if is_online and control_form:
                    lesson_type += f" ({control_form})"

                lesson_type = lesson_type or "—"

                out.append({
                    "date": datestr,
                    "type": lesson_type,
                    "lesson": lesson,
                    "teacher": teacher,
                    "time_of_lesson": time_of_lesson,
                    "cabinet": cabinet
                })

        return out

    def get_groups(self, level: str, form: str, faculty: str, course: str) -> list[str]:
        driver = self.init_driver(True)
        wait = WebDriverWait(driver, 10)
        try:
            driver.get(self.settings.TIME_TABLE_URL)

            try:
                btn = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, ".cookies_block .cookies_btn"))
                )
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(0.2)
            except Exception:
                pass

            self.select_option(driver, "levels", level)
            self.select_option(driver, "forms", form)
            self.select_option(driver, "faculties", faculty)
            self.select_option(driver, "courses", course)

            wait.until(EC.presence_of_element_located((By.ID, "groups_container")))
            html = driver.page_source
            return self.list_groups_from_html(html)
        finally:
            self.quit_and_clear(driver)

    def list_groups_from_html(self, html: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        box = soup.select_one("#groups_container")
        if not box:
            return []
        return [div.get_text(strip=True) for div in box.select(".groups-btn")]

    def parse_assignments_from_course(self, driver, course_link: str) -> list[list[str]]:
        """
        Разбор задач одного курса
        Возвращает список необработанных записей
        """
        wait = WebDriverWait(driver, 20)
        full = course_link if course_link.startswith("http") else urljoin(self.settings.BASE_URL, course_link)
        driver.get(full)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1.h2.mb-0")))
        soup = BeautifulSoup(driver.page_source, "html.parser")
        course_name = (soup.select_one("h1.h2.mb-0").text.strip()
                       if soup.select_one("h1.h2.mb-0")
                       else f"Курс {full.split('id=')[-1]}")

        result = []
        for assign in soup.select("li.modtype_assign"):
            block = assign.select_one("div.activity-item")
            if not block:
                continue
            name = block.get("data-activityname", "").strip() or "Без названия"
            link_tag = block.select_one("a.aalink[href]")
            if not link_tag:
                continue
            href = link_tag["href"]
            task_link = href if href.startswith("http") else urljoin(self.settings.BASE_URL, href)

            open_date = "не указано"
            due_date = "не указано"
            for d in block.select("div.activity-dates div"):
                t = d.get_text(strip=True)
                if t.startswith("Открыто с"):
                    open_date = t.replace("Открыто с:", "").strip()
                elif t.startswith("Срок сдачи"):
                    due_date = t.replace("Срок сдачи:", "").strip()

            driver.get(task_link)
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "generaltable")))
            task_soup = BeautifulSoup(driver.page_source, "html.parser")

            status_table = task_soup.select_one("table.generaltable.table-bordered")
            stat = {
                "Состояние ответа на задание": "—",
                "Состояние оценивания": "—",
                "Оставшееся время": "—",
                "Последнее изменение": "—",
                "Файлы": ""
            }
            if status_table:
                for row in status_table.select("tr"):
                    th = row.find("th");
                    td = row.find("td")
                    if th and td and th.text.strip() in stat:
                        stat[th.text.strip()] = td.text.strip()

            files = [a["href"] for a in task_soup.select("a[href*='pluginfile.php']")]
            stat["Файлы"] = ", ".join(files)

            result.append([
                course_name, name, open_date, due_date, task_link,
                stat["Состояние ответа на задание"],
                stat["Состояние оценивания"],
                stat["Оставшееся время"],
                stat["Последнее изменение"],
                stat["Файлы"],
            ])

        return result

    def quit_and_clear(self, driver):
        """
        Фикс того, что хромиум занимает ~3гб на диске просто потому что существует
        """
        try:
            # Очистить кеш и куки
            # subprocess.check_call(["pip", "cache", "purge"])
            driver.execute_cdp_cmd('Network.clearBrowserCache', {})
            driver.execute_cdp_cmd('Network.clearBrowserCookies', {})
        except Exception:
            pass
        finally:
            driver.quit()
