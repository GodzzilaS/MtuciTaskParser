from core.db import get_collection
from typing import Any

collection_name = "config"


def _coll():
    return get_collection(collection_name)


def get_flag(name: str, default: Any = None) -> Any:
    """
    Получить значение флага из коллекции config.
    Если документ не найден — вернуть default.
    """
    doc = _coll().find_one({"name": name})
    return doc["value"] if doc and "value" in doc else default


def set_flag(name: str, value: Any) -> None:
    """
    Установить (или обновить) значение флага в коллекции config.
    """
    _coll().update_one(
        {"name": name},
        {"$set": {"name": name, "value": value}},
        upsert=True
    )


def get_bot_enabled() -> bool:
    return get_flag("bot_enabled", True)


def set_bot_enabled(enabled: bool) -> None:
    set_flag("bot_enabled", enabled)


def get_maintenance_mode() -> bool:
    return get_flag("maintenance_mode", False)


def set_maintenance_mode(enabled: bool) -> None:
    set_flag("maintenance_mode", enabled)


def get_scheduled_enabled() -> bool:
    return get_flag("scheduled_enabled", True)


def set_scheduled_enabled(enabled: bool) -> None:
    set_flag("scheduled_enabled", enabled)
