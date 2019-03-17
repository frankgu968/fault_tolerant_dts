import json
import logging
from models.slave import Slave


class SlaveResource(object):
    def on_post(self, req, resp):
        raw_json = req.stream.read()
        body = json.loads(raw_json, encoding='utf-8')
        url = body["url"]
        state = "READY"
        slave = Slave(url=url, state=state).save()
        logging.info("New slave " + slave.hash + " registerd; creating new entry in database")
        resp.body = json.dumps(slave.to_dict())

