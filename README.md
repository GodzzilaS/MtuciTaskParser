# MtuciTaskParser

Асинхронный Telegram‑бот c веб-админкой для мониторинга и уведомления об изменениях статуса заданий в LMS МТУСИ.

## Структура проекта

```
MtuciTaskParser/
├── README.md                   # Это руководство
├── requirements.txt            # Зависимости проекта
├── .env                        # Конфиг для среды
├── main.py                     # Точка входа приложения
├── scheduler.py                # Фоновая периодическая проверка
├── core/
│   ├── settings.py             # Загрузка .env и константы приложения
│   ├── db.py                   # Инициализация подключения и работа с MongoDB
│   └── models/                 # Модели и методы работы с БД
│       ├── config.py           # Флаги конфигурации (maintenance_mode, scheduled_enabled)
│       ├── users.py            # CRUD для пользователей
│       └── tasks.py            # CRUD и bulk‑операции для задач
├── services/
│   ├── encryption.py           # Сервис шифрования паролей
│   └── scraper.py              # Selenium‑парсер LMS
├── utils/
│   ├── blueprints_utils.py     # Динамическая загрузка Flask‑blueprint’ов
│   ├── check_utils.py          # Декораторы проверки доступности бота/тех.работ
│   ├── date_utils.py           # Преобразование дат/времени в удобный формат
│   ├── logger_utils.py         # Логгер с цветами + middleware для Flask
│   └── status_utils.py         # Преобразование статусов задания в эмодзи
├── webapp/                     # Веб‑интерфейс на Flask для админки
│   ├── routes.py               # Blueprint‑роуты (управление пользователями, флагами)
│   ├── templates/              # Jinja2‑шаблоны (base, index, login, users)
│   └── static/                 # CSS, favicon’ы, SVG‑иконки
└── bot/                        # Обработчики Telegram‑бота
    ├── __init__.py             # Регистрация всех команд
    ├── start_handler.py        # Обработка /start
    ├── login_handler.py        # Обработка /login
    ├── tasks_handler.py        # Обработка /get_tasks
    └── timetable_handler.py    # Обработка /get_timetable
```

## Возможности

- Авторизация пользователя командой `/login <login> <password>`
- Ручной сбор списка заданий командой `/get_tasks`
- Ручной сбор расписания `/get_timetable`
- Фоновая периодическая проверка (по умолчанию каждые 5 минут)
- Уведомления в Telegram при изменении статуса ответа или оценки
- Шифрование паролей в БД с помощью Fernet
- Хранение пользователей и заданий в MongoDB
- Модульная архитектура для лёгкого тестирования и расширения

## Требования

- Python 3.13
- MongoDB
- Google Chrome/Chromium & ChromeDriver в PATH
- Telegram Bot Token
- Fernet encryption key
- Пакеты из `requirements.txt`

## Конфигурация

Создай файл `.env` в корне проекта со следующим содержимым:

```dotenv
TELEGRAM_DEV_TOKEN="<токен бота для разработки>"
TELEGRAM_PROD_TOKEN="<токен бота для продакшена>"
ENCRYPTION_KEY=<Base64-ключ Fernet>
DB_URL="<строка подключения к MongoDB>"
DB_NAME="<название базы данных>"
```

- `TELEGRAM_DEV_TOKEN` и `TELEGRAM_PROD_TOKEN` — токены ботов для разных сред.
- `ENCRYPTION_KEY` — ключ для шифрования паролей пользователей.

## Запуск

1. Установка зависимостей
    ```bash
    pip install -r requirements.txt
    ```

2. Запуск бота
    ```bash
    python main.py
    ```
