# MtuciTaskParser

Асинхронный Telegram‑бот c веб-админкой для мониторинга и уведомления об изменениях статуса заданий в LMS МТУСИ.

## Структура проекта

```
MtuciTaskParser/
├── bot/                        # Telegram‑бот: хендлеры команд
│   ├── __init__.py             # Регистрация команд в приложении
│   ├── login_handler.py        # Обработка /login
│   ├── start_handler.py        # Обработка /start
│   ├── tasks_handler.py        # Обработка /get_tasks
│   └── timetable_handler.py    # Обработка /get_timetable
├── core/                       # Ядро приложения
│   ├── models/                 # CRUD‑модели
│   │   ├── config.py           # Флаги конфигурации и интервалы
│   │   ├── tasks.py            # CRUD и bulk‑операции для задач
│   │   └── users.py            # CRUD для пользователей
│   ├── db.py                   # Инициализация MongoDB
│   ├── templates.py            # Шаблоны для регистрации записей в БД
│   └── settings.py             # Загрузка .env и константы
├── images/                     # Изображения для бота
├── logs/                       # Логи проекта
├── services/                   # Сервисы
│   ├── encryption.py           # Шифрование/дешифрование паролей (Fernet)
│   └── scraper.py              # Логика сбора данных из LMS
├── utils/                      # Утилиты и декораторы
│   ├── check_utils.py          # Декораторы доступности бота/режима тех.работ
│   ├── date_utils.py           # Форматирование дат и времени
│   ├── logger_utils.py         # Логгер (colorlog, file handler, middleware)
│   └── status_utils.py         # Преобразование статусов в эмодзи
├── webapp/                     # Веб‑админка Flask
│   ├── routes/                 # Разбитые маршруты
│   │   ├── __init__.py         # Регистрация blueprint + context_processor
│   │   ├── auth_routes.py      # /auth/login, /auth/logout
│   │   ├── check_routes.py     # /run-check (ручная проверка)
│   │   ├── dashboard_routes.py # /, /toggle_bot, /toggle_maintenance, /toggle_scheduled
│   │   ├── logs_routes.py      # /logs, /logs/download, /logs/clear
│   │   ├── settings_routes.py  # /settings (интервал проверки)
│   │   └── user_routes.py      # /users (фильтрация, обновление, удаление)
│   ├── static/                 # CSS, иконки
│   └── templates/              # Jinja2‑шаблоны
├── main.py                     # Точка входа: запускает бота и админку
├── README.md                   # Документация проекта
├── requirements.txt            # Зависимости проекта
├── scheduler.py                # Одна итерация фоновой проверки
└── TODO.md                     # Список задач и roadmap
```

---

## Возможности

- **Авторизация в LMS** `/login <логин> <пароль>`
- **Ручной сбор**
  - `/get_tasks` — получить и сохранить все задания
  - `/get_timetable` — получить расписание
- **Фоновая проверка** с интервалом (по умолчанию 5 мин)
- **Уведомления** при смене статуса или оценке
- **Веб‑админка**
  - Запуск проверки вручную
  - Изменение интервала проверки
  - Включение/выключение бота и режима тех.работ
  - Просмотр/скачивание/очистка логов
- **Безопасное хранение паролей** (Fernet + MongoDB)
- **Модульная архитектура (почти)** для простоты расширения

---

## Требования

- Python 3.13
- MongoDB
- Google Chrome/Chromium + ChromeDriver (в PATH)
- Переменные окружения в файле `.env`:

  ```dotenv
  TELEGRAM_DEV_TOKEN="<токен для dev>"
  TELEGRAM_PROD_TOKEN="<токен для prod>"
  ENCRYPTION_KEY="<Base64‑ключ Fernet>"
  DB_URL="<MongoDB URI>"
  DB_NAME="<имя базы>"
  ```

---

## Запуск

1. Установить зависимости:

   ```bash
   pip install -r requirements.txt
   ```

2. Создать и заполнить `.env` (см. выше).

3. Запустить приложение:

   ```bash
   python main.py
   ```

   - Бот автоматически стартует в консоли.
   - Веб‑админка доступна по `http://localhost:5000/`.

---

## TODO

Все задачи и план работ находятся в [`TODO.md`](./TODO.md).  
