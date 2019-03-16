import json
import logging
from models.slave import Slave
from ResettableTimer import TimerReset

# TODO: Change this to use environment
HB_INTERVAL = 1.0


class SlaveResource(object):
    def __init__(self):
        self.hb_timers = {}


    def on_post(self, req, resp):
        raw_json = req.stream.read()
        body = json.loads(raw_json, encoding='utf-8')
        url = body["url"]
        state = "READY"

        if "state" in body:
            # Slave already registered
            if (body["state"] != "READY") and (body["state"] != "RUNNING"):
                # Slave is in an incorrect state, don't assign task!
                logging.warning("Slave " + url + " is in an undefined state; it will not be utilized!")
                resp.body = {}
                return

            else:
                # Update slave status
                slave = Slave.objects.get(url=url)
                logging.info("Heartbeat: " + slave.hash)
                resp.body = json.dumps(slave.to_dict())
        else:
            # Create new slave entry

            slave = Slave(url=url, state=state).save()
            logging.info("New slave " + slave.hash + " registerd; creating new entry in database")
            resp.body = json.dumps(slave.to_dict())

        # Reset heartbeat timers
        self.hb_timers[slave.url] = TimerReset(HB_INTERVAL, self.handle_hb_timeout, args=(slave,)).start()

    @staticmethod
    def handle_hb_timeout(slave):
        logging.warning("Slave " + slave.hash + " has timed out; removing from database...")
        # TODO: Remove entry from database