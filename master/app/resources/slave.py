import json
import logging
from models.slave import Slave
import falcon
from mongoengine.errors import NotUniqueError
from utils.MongoStorage import MongoStorage

class SlaveResource(object):
    def __init__(self):
        self.mongo = MongoStorage()

    @staticmethod
    def on_post(req, resp):
        raw_json = req.stream.read()
        body = json.loads(raw_json, encoding='utf-8')
        url = body["url"]
        state = "READY"
        try:
            slave = Slave(url=url, state=state).save()
            logging.info("New slave " + slave.hash + " registerd; creating new entry in database")
            resp.body = json.dumps(slave.to_dict())
        except NotUniqueError:
            logging.error("Attempted to register duplicate slave URL!")
            resp.body = json.dumps({"error": "Slave URL already exists"})
            resp.status = falcon.HTTP_400


