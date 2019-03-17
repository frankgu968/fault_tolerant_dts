import json
import logging
import falcon
from components.scheduler import Scheduler

logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=logging.DEBUG,
        datefmt='%Y-%m-%d %H:%M:%S')


class SchedulerResource(object):
    def __init__(self):
        self.scheduler = Scheduler()

    def on_post(self, req, resp, action):
        if action == "start":
            if self.scheduler.continue_run:
                resp.body = json.dumps({"error": "Scheduler is already running!"})
                resp.status = falcon.HTTP_INTERNAL_SERVER_ERROR
            else:
                self.scheduler.start()
                resp.body = json.dumps({"message": "Scheduler has started..."})
        elif action == "stop":
            if self.scheduler.continue_run:
                self.scheduler.stop()
                logging.info("scheduler has stopped!")
                resp.body = json.dumps({"message": "Scheduler has stopped."})
            else:
                resp.body = json.dumps({"error": "Scheduler was not running!"})
                resp.status = falcon.HTTP_INTERNAL_SERVER_ERROR
        elif action == "task_done":
            if self.scheduler.continue_run:
                raw_json = req.stream.read()
                body = json.loads(raw_json, encoding='utf-8')
                task_name = body["task_name"]
                slave_hash = body["slave_hash"]
                self.scheduler.handle_task_complete(task_name, slave_hash)
                self.scheduler.do_schedule_once()
                resp.status = falcon.HTTP_OK
            else:
                logging.warning("Slave posted task complete when master scheduler was not running")
                resp.body = json.dumps({"error": "Master scheduler was not running!"})
                resp.status = falcon.HTTP_INTERNAL_SERVER_ERROR

