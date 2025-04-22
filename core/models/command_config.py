from copy import deepcopy
from typing import Dict, List, Optional, Any

from bson import ObjectId

from core import db
from core.templates import command_config_template

collection_name = "config"


class CommandConfig:
    def __init__(self, data: Dict[str, Any]) -> None:
        self.id: ObjectId = data["_id"]
        self.name: str = data["name"]
        self.command: str = data["command"]
        self.messages: Dict[str, str] = data.get("messages", {})

    def __repr__(self) -> str:
        return f"CommandConfig(id={self.id}, name={self.name}, command={self.command})"

    def __dict__(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "name": self.name,
            "command": self.command,
            "messages": self.messages,
        }

    def get_message(self, key: str, **kwargs: Any) -> Optional[str]:
        text: Optional[str] = self.messages.get(key)
        if not text:
            return None

        if kwargs:
            text = text.format(**kwargs)

        return text.replace(r"\\n", "\n").replace(r"\n", "\n")

    @classmethod
    def exist(cls, command_name: str) -> bool:
        """
        Проверить существует-ли команда.
        """
        if not db.find_one(collection_name, {"command": command_name}):
            return False
        return True

    @classmethod
    def delete(cls, command_name: str) -> None:
        """
        Удалить команду из БД
        """
        db.delete_one(collection_name, {"command": command_name})

    @classmethod
    def update(cls, command_name: str, messages: dict) -> 'CommandConfig':
        """
        Обновить команду.
        """
        cmd = CommandConfig.get(command_name)
        cmd.messages = messages
        db.update_one(collection_name, {"command": command_name}, {"$set": {"messages": messages}})
        return cmd

    @classmethod
    def get(cls, command_name: str) -> 'CommandConfig':
        """
        Загрузить конфиг команды из БД или создать новый по шаблону.
        """
        data: Dict[str, Any] = db.find_one(collection_name, {"command": command_name})
        if not data:
            data = deepcopy(command_config_template)
            data["command"] = command_name
            db.insert(collection_name, data)
        return cls(data)

    @classmethod
    def get_by_id(cls, command_id: ObjectId) -> 'CommandConfig':
        """
        Загрузить конфиг команды из БД по ObjectId.
        """
        data: Dict[str, Any] = db.find_one(collection_name, {"_id": command_id})
        return cls(data)

    @classmethod
    def get_all(cls) -> List['CommandConfig']:
        """
        Вернуть список всех конфигов
        """
        data = db.find(collection_name, {"name": "config"})
        return [cls(c) for c in data]

    def update_message(self, key: str, text: str) -> None:
        """
        Обновить ключ в messages и записать в БД
        """
        self.messages[key] = text
        db.update_one(
            collection_name,
            {"command": self.command},
            {"$set": {f"messages.{key}": text}}
        )
