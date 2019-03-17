import json
import logging
import falcon
from scheduler import Scheduler


class SchedulerResource(object):
    def __init__(self):
        self.scheduler = Scheduler()

    def on_post(self, req, resp, action):
        if action == "start":
            if self.scheduler.continue_run:
                resp.body = json.dumps({"error": "Scheduler is already running!"})
                resp.status = falcon.HTTP_400
            else:
                self.scheduler.start()
                resp.body = json.dumps({"message": "Scheduler has started..."})
        elif action == "stop":
            if self.scheduler.continue_run:
                self.scheduler.stop()
                resp.body = json.dumps({"message": "Scheduler has stopped."})
            else:
                resp.body = json.dumps({"error": "Scheduler is was not running!"})
                resp.status = falcon.HTTP_400

