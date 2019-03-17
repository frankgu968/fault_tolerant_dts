import json
import logging
import falcon
from components.slave import Slave

logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=logging.DEBUG,
        datefmt='%Y-%m-%d %H:%M:%S')


class SlaveSelfResource(object):
    def __init__(self):
        self.slave = Slave()

    def on_get(self, req, resp):
        # Heartbeat response and state transition handler
        ret_str = json.dumps({
            "hash": self.slave.hash,
            "url": self.slave.url,
            "state": self.slave.state,
            "task": self.slave.task
        })

        # Transition handler for DONE state
        if self.slave.state == "DONE":
            self.slave.done_transition()
        self.slave.refresh_master_timeout()
        resp.body = json.dumps(ret_str)

    def on_post(self, req, resp):
        # New job handler
        raw_json = req.stream.read()
        task = json.loads(raw_json, encoding='utf-8')
        self.slave.refresh_master_timeout()

        if self.slave.run_task(task):
            resp.status = falcon.HTTP_OK
        else:
            resp.status = falcon.HTTP_INTERNAL_SERVER_ERROR

