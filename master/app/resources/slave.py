import json

from models.slave import Slave


class SlaveResource(object):

    def on_post(self, req, resp):
        raw_json = req.stream.read()
        body = json.loads(raw_json, encoding='utf-8')
        url = body["url"]
        state = "READY"

        slave = Slave(url=url, state=state).save()
        resp.body = json.dumps(slave.to_dict())
