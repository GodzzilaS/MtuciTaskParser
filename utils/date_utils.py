from datetime import datetime

MONTH_MAP = {
    "января": "январь", "февраля": "февраль", "марта": "март",
    "апреля": "апрель", "мая": "май", "июня": "июнь",
    "июля": "июль", "августа": "август", "сентября": "сентябрь",
    "октября": "октябрь", "ноября": "ноябрь", "декабря": "декабрь"
}


def short_date(full_date: str) -> str:
    """
    Из 'среда, 12 мая 2025, 14:00' → '12.05.2025 14:00',
    или возвращает исходную строку, если не парсится.
    """
    if not full_date or full_date == "не указано":
        return full_date
    for old, new in MONTH_MAP.items():
        full_date = full_date.replace(old, new)
    try:
        dt = datetime.strptime(full_date, "%A, %d %B %Y, %H:%M")
        return dt.strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return full_date


def compact_time(time_str: str) -> str:
    """
    Из '0 дн. - 2 час. осталось' → '2 ч'
    """
    return (
        time_str
        .split("-")[-1]
        .strip()
        .replace("дн.", "д")
        .replace("час.", "ч")
        .replace(" осталось", "")
    )
