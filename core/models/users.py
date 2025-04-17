import time
from copy import deepcopy

from core import db, config

collection_name = "users"


class User:
    def __init__(self, user):
        self._uuid = user.get("_id")
        self._telegram_id = user.get("telegram_id")
        self._telegram_username = user.get("telegram_username")
        self._mtuci_login = user.get("mtuci_login")
        self._mtuci_password = user.get("mtuci_password")
        self._created = user.get("created")
        self._notifications = user.get("notifications")
        self._education_level = user.get("education_level")
        self._study_form = user.get("study_form")
        self._faculty = user.get("faculty")
        self._course = user.get("course")
        self._group = user.get("group")

    @property
    def uuid(self): return self._uuid

    @property
    def telegram_id(self): return self._telegram_id

    @property
    def telegram_username(self): return self._telegram_username

    @property
    def mtuci_login(self): return self._mtuci_login

    @property
    def mtuci_password(self): return self._mtuci_password

    @property
    def created(self): return self._created

    @property
    def notifications(self): return self._notifications

    @property
    def education_level(self): return self._education_level

    @property
    def study_form(self): return self._study_form

    @property
    def faculty(self): return self._faculty

    @property
    def course(self): return self._course

    @property
    def group(self): return self._group

    @telegram_id.setter
    def telegram_id(self, value):
        self._telegram_id = value
        db.update_one(collection_name, {"telegram_id": self.telegram_id}, {"$set": {"telegram_id": value}})

    @telegram_username.setter
    def telegram_username(self, value):
        self._telegram_username = value
        db.update_one(collection_name, {"telegram_id": self.telegram_id}, {"$set": {"telegram_username": value}})

    @mtuci_login.setter
    def mtuci_login(self, value):
        self._mtuci_login = value
        db.update_one(collection_name, {"telegram_id": self.telegram_id}, {"$set": {"mtuci_login": value}})

    @mtuci_password.setter
    def mtuci_password(self, value):
        self._mtuci_password = value
        db.update_one(collection_name, {"telegram_id": self.telegram_id}, {"$set": {"mtuci_password": value}})

    @notifications.setter
    def notifications(self, value):
        self._notifications = value
        db.update_one(collection_name, {"telegram_id": self.telegram_id}, {"$set": {"notifications": value}})

    @education_level.setter
    def education_level(self, value):
        self._education_level = value
        db.update_one(collection_name, {"telegram_id": self.telegram_id}, {"$set": {"education_level": value}})

    @study_form.setter
    def study_form(self, value):
        self._study_form = value
        db.update_one(collection_name, {"telegram_id": self.telegram_id}, {"$set": {"study_form": value}})

    @faculty.setter
    def faculty(self, value):
        self._faculty = value
        db.update_one(collection_name, {"telegram_id": self.telegram_id}, {"$set": {"faculty": value}})

    @course.setter
    def course(self, value):
        self._course = value
        db.update_one(collection_name, {"telegram_id": self.telegram_id}, {"$set": {"course": value}})

    @group.setter
    def group(self, value):
        self._group = value
        db.update_one(collection_name, {"telegram_id": self.telegram_id}, {"$set": {"group": value}})


def _get_user(telegram_id):
    return db.find_one(collection_name, {"telegram_id": telegram_id})


def exist(telegram_id):
    return _get_user(telegram_id) is not None if True else False


def create_user(telegram_id, telegram_username, mtuci_login, mtuci_password):
    telegram_id = telegram_id
    telegram_username = str(telegram_username)
    mtuci_login = str(mtuci_login)
    mtuci_password = str(mtuci_password)

    template = deepcopy(config.user_template)
    template["telegram_id"] = telegram_id
    template["telegram_username"] = telegram_username
    template["mtuci_login"] = mtuci_login
    template["mtuci_password"] = mtuci_password
    template["created"] = time.time()

    db.insert(collection_name, template)
    return select_user(telegram_id)


def select_user(telegram_id) -> User:
    try:
        return User(_get_user(telegram_id))
    except TypeError:
        return None


def custom_select(request):
    return map(User, db.find(collection_name, request))
