import os
import logging
import requests
import socket
import json
from utils.ResettableTimer import TimerReset
from time import sleep

def check_positive_integer(test_str, purpose=""):
    if test_str.isdigit() and int(test_str) > 0:
        return int(test_str)
    else:
        logging.error("Invalid " + purpose + " , must be (0,N] in seconds")
        exit(1)


class Slave(object):
    def __init__(self):
        # Self aware variables
        self.state = "INIT"
        self.running = []
        self.master_timeout = check_positive_integer(os.getenv("MASTER_TIMEOUT", default="30"), purpose="master timeout")
        self.hb_timer = TimerReset(self.master_timeout, self.master_timeout_handler)
        self.hostname = socket.gethostname()
        self.port = check_positive_integer(os.getenv("SLAVE_PORT", default="8888"), purpose="slave port")
        self.url = "http://" + self.hostname + ":" + self.port + "/slave"

        self.master_host = os.getenv("MASTER_HOST", default="localhost")
        self.master_port = check_positive_integer(os.getenv("MASTER_PORT", default="8000"), purpose="master port")
        self.master_url = "http://" + self.master_host + ":" + self.master_port + "/slave"

    def register(self):
        # Continuously try to register itself with the master if the state is in INIT
        req_str = json.dumps({"url": self.url})
        while self.state == "INIT":
            try:
                req = requests.post(self.master_url, data=req_str)
            except Exception as e:
                # Master did not respond correctly, continue trying
                logging.error("POST to master " + self.master_host + " failed:\n" + str(e))

            if req.status_code == requests.codes.ok:
                # Registered with master, begin state transition
                self.state = "READY"
                self.hb_timer.start()   # Start the master timeout timer
            else:
                logging.error("Master returned incorrect response code, retrying registration...")

    def master_timeout_handler(self):
        # Connection with master lost
        self.state = "INIT"     # Reset state
        self.running.join()     # TODO: Kill the subprocess
        self.running = []       # Clear the object
        self.register()         # Retry registration loop

    def run_task(self, task):
        try:
            if self.state == "READY":
                sleeptime = float(task["sleeptime"])
                if sleeptime < 0:
                    raise ValueError
                # TODO: Runner shall be a subprocess
                # self.running = Thread(target=sleep, args=(sleeptime,))
                self.state = "RUNNING"
                return True
        except ValueError:
            logging.error("Task sleeptime definition was not a positive number!")
        return False


