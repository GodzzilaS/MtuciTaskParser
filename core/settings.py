import os
import platform
from urllib.parse import urljoin

from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Основные URL LMS
    BASE_URL = os.getenv("BASE_URL", "https://lms.mtuci.ru")
    LOGIN_PAGE = urljoin(BASE_URL, "/lms/login/index.php")
    MY_COURSES_PAGE = urljoin(BASE_URL, "/lms/my/courses.php")
    TIME_TABLE_URL = "https://lk.mtuci.ru/student/schedule?clear_history=true&period=month"

    # Ограничения
    MAX_MESSAGE_LENGTH = int(os.getenv("MAX_MESSAGE_LENGTH", "4000"))
    MAX_CONCURRENT_BROWSERS = int(os.getenv("MAX_CONCURRENT_BROWSERS", "3"))

    # Ключ шифрования и токен бота
    ENCRYPTION_KEY = os.environ["ENCRYPTION_KEY"]
    BOT_TOKEN = (
        os.getenv("TELEGRAM_DEV_TOKEN")
        if platform.system() == "Windows"
        else os.getenv("TELEGRAM_PROD_TOKEN")
    )
