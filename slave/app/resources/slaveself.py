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
        logging.info("Received heartbeat message from master")
        if (self.slave.state == "RUNNING") and (self.slave.runner.poll()) is not None:
            self.slave.state = "DONE"

        ret_str = json.dumps({
            "hash": self.slave.hash,
            "url": self.slave.url,
            "state": self.slave.state,
            "task": self.slave.task
        })

        # Transition handler for DONE state
        if self.slave.state == "DONE":
            logging.info("Slave transitioning from DONE to READY")
            self.slave.done_transition()
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
            resp.status = falcon.HTTP_INTERNAL_SERVER_ERROR

