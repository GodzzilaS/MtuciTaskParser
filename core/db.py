import os
from typing import Optional

from pymongo import MongoClient, errors

db_connection_url = os.environ["DB_URL"]
client = None


def get_client() -> Optional[MongoClient]:
    if client is None:
        try:
            return MongoClient(db_connection_url)
        except errors.ServerSelectionTimeoutError as e:
            print(e)
            return None
    else:
        pass


client = get_client()


def get_db(db):
    global client
    if client is not None:
        return client[db]
    else:
        client = get_client()
        return client[db]


def get_collection(collection):
    base = get_db(os.environ["DB_NAME"])
    return base[collection]


def update_one(collection, select_request, data):
    base = get_collection(collection)
    base.update_one(select_request, data)


def find(collection, request):
    base = get_collection(collection)
    request = list(base.find(request))
    return request


def find_one(collection, request):
    base = get_collection(collection)
    result = base.find(request)
    data = list(result)
    if len(data) > 0:
        return data[0]
    else:
        return None


def insert(collection, *args):
    base = get_collection(collection)
    base.insert_many(args)


def low_lvl_find(collection, request):
    base = get_collection(collection)
    return base.find(request)


def delete_one(collection, select_request):
    base = get_collection(collection)
    base.delete_one(select_request)


def bulk_write(collection, bulk_ops):
    base = get_collection(collection)
    return base.bulk_write(bulk_ops)
