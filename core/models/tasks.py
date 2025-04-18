import time
from copy import deepcopy

from pymongo import UpdateOne

from core import db, config

collection_name = "tasks"


class Task:
    def __init__(self, task):
        self._uuid = task["_id"]
        self._user_id = task["user_id"]
        self._task_link = task["task_link"]
        self._course = task.get("course", "")
        self._task_name = task.get("task_name", "")
        self._open_date = task.get("open_date", "не указано")
        self._due_date = task.get("due_date", "не указано")
        self._response_status = task.get("response_status", "")
        self._grade_status = task.get("grade_status", "")
        self._time_left = task.get("time_left", "")
        self._last_change = task.get("last_change", "")
        self._last_updated = task.get("last_updated", 0)

    @property
    def uuid(self): return self._uuid

    @property
    def user_id(self): return self._user_id

    @property
    def task_link(self): return self._task_link

    @property
    def course(self): return self._course

    @property
    def task_name(self): return self._task_name

    @property
    def open_date(self): return self._open_date

    @property
    def due_date(self): return self._due_date

    @property
    def response_status(self): return self._response_status

    @property
    def grade_status(self): return self._grade_status

    @property
    def time_left(self): return self._time_left

    @property
    def last_change(self): return self._last_change

    @property
    def last_updated(self): return self._last_updated

    @user_id.setter
    def user_id(self, value):
        self._user_id = value
        db.update_one(collection_name, {"_id": self._uuid}, {"$set": {"user_id": value}})

    @task_link.setter
    def task_link(self, value):
        self._task_link = value
        db.update_one(collection_name, {"_id": self._uuid}, {"$set": {"task_link": value}})

    @course.setter
    def course(self, value):
        self._course = value
        db.update_one(collection_name, {"_id": self._uuid}, {"$set": {"course": value}})

    @task_name.setter
    def task_name(self, value):
        self._task_name = value
        db.update_one(collection_name, {"_id": self._uuid}, {"$set": {"task_name": value}})

    @open_date.setter
    def open_date(self, value):
        self._open_date = value
        db.update_one(collection_name, {"_id": self._uuid}, {"$set": {"open_date": value}})

    @due_date.setter
    def due_date(self, value):
        self._due_date = value
        db.update_one(collection_name, {"_id": self._uuid}, {"$set": {"due_date": value}})

    @response_status.setter
    def response_status(self, value):
        self._response_status = value
        db.update_one(collection_name, {"_id": self._uuid}, {"$set": {"response_status": value}})

    @grade_status.setter
    def grade_status(self, value):
        self._grade_status = value
        db.update_one(collection_name, {"_id": self._uuid}, {"$set": {"grade_status": value}})

    @time_left.setter
    def time_left(self, value):
        self._time_left = value
        db.update_one(collection_name, {"_id": self._uuid}, {"$set": {"time_left": value}})

    @last_change.setter
    def last_change(self, value):
        self._last_change = value
        db.update_one(collection_name, {"_id": self._uuid}, {"$set": {"last_change": value}})

    @last_updated.setter
    def last_updated(self, value):
        self._last_updated = value
        db.update_one(collection_name, {"_id": self._uuid}, {"$set": {"last_updated": value}})


def _get_task(query):
    return db.find_one(collection_name, query)


def exist(query):
    return _get_task(query) is not None


def create_task(task_data):
    """
    Создает запись о задании с использованием шаблона task_template.
    task_data должен содержать следующие ключи:
      - user_id
      - task_link
      - course
      - task_name
      - open_date
      - due_date
      - response_status
      - grade_status
      - time_left
      - last_change
    """
    template = deepcopy(config.task_template)
    template["user_id"] = task_data.get("user_id")
    template["task_link"] = task_data.get("task_link")
    template["course"] = task_data.get("course", "")
    template["task_name"] = task_data.get("task_name", "")
    template["open_date"] = task_data.get("open_date", "не указано")
    template["due_date"] = task_data.get("due_date", "не указано")
    template["response_status"] = task_data.get("response_status", "")
    template["grade_status"] = task_data.get("grade_status", "")
    template["time_left"] = task_data.get("time_left", "")
    template["last_change"] = task_data.get("last_change", "")
    template["last_updated"] = time.time()

    db.insert(collection_name, template)
    return select_task({"user_id": template["user_id"], "task_link": template["task_link"]})


def create_tasks_bulk(user_id: int, tasks_data: list):
    """
    Создает или обновляет список заданий для указанного пользователя за один запрос (bulk upsert).

    :param user_id: Идентификатор пользователя (тип int).
    :param tasks_data: Список словарей с данными по заданиям. Каждый словарь должен содержать следующие ключи:
        - task_link (уникальный идентификатор или ссылка на задание)
        - course
        - task_name
        - open_date
        - due_date
        - response_status
        - grade_status
        - time_left
        - last_change
    Если некоторые ключи отсутствуют, можно задать для них значения по умолчанию.
    """
    bulk_ops = []
    current_ts = time.time()
    for task in tasks_data:
        template = deepcopy(config.task_template)
        template.update(task)
        template["user_id"] = user_id
        template.setdefault("last_updated", current_ts)

        query = {"user_id": user_id, "task_link": template.get("task_link")}
        update = {"$set": template}
        bulk_ops.append(UpdateOne(query, update, upsert=True))

    if bulk_ops:
        result = db.bulk_write(collection_name, bulk_ops)
        return result
    return None


def select_task(query) -> Task:
    try:
        return Task(_get_task(query))
    except TypeError:
        return None


def custom_select(query):
    return map(Task, db.find(collection_name, query))
