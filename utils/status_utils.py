def status_emoji(response_status: str, grade_status: str) -> tuple[str, str]:
    """
    Возвращает (grade_emoji, response_emoji) по двум статусам.
    """
    resp_map = {
        "Отправлено для оценивания": "📤",
        "Ответы на задание еще не представлены": "⚠️"
    }
    grade_map = {
        "Оценено": "🟢",
        "Не оценено": "🔴"
    }

    # смайлик для ответа
    response_emoji = next(
        (e for k, e in resp_map.items() if k.lower() in response_status.lower()),
        "▪️"
    )
    # смайлик для оценки
    key = grade_status.split(":")[0].strip() if ":" in grade_status else grade_status
    grade_emoji = grade_map.get(key, "⚪")
    return grade_emoji, response_emoji
