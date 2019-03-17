import json
import logging
import falcon
from components.slave import Slave
import os

logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=os.getenv("LOG_LEVEL", default=logging.DEBUG),
        datefmt='%Y-%m-%d %H:%M:%S')


class SlaveSelfResource(object):
    def __init__(self):
        self.slave = Slave()

    def on_get(self, req, resp):
        # Heartbeat response and state transition handler
        logging.info("Received heartbeat message from master")

        ret_str = json.dumps({
            "hash": self.slave.hash,
            "url": self.slave.url,
            "state": self.slave.state,
            "task": self.slave.task
        })

        logging.debug(ret_str)

        # Transition handler for DONE state after master recovery
        if self.slave.state == "DONE":
            logging.info("Slave transitioning from DONE to READY")
            self.slave.state = "READY"
            self.slave.task = []
            self.slave.runner = []
        self.slave.refresh_master_timeout()
        resp.body = json.dumps(ret_str)

    def on_post(self, req, resp):
        # New job handler
        task = json.load(req.stream)
        logging.debug("Slave received new task: " + str(task))
        self.slave.refresh_master_timeout()

        if self.slave.run_task(task):
            logging.info("Slave has started running new task " + task["taskname"])
            resp.status = falcon.HTTP_OK
        else:
            logging.info("Slave could not start running new task " + task["taskname"])
            self.slave.reset()
            resp.status = falcon.HTTP_INTERNAL_SERVER_ERROR

