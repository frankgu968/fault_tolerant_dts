import os
import logging
import requests
import socket
import json
from utils.ResettableTimer import TimerReset
from time import sleep
import subprocess
import threading
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
        self.runner = []
        self.task = []
        self.run_checker = []
        self.master_timeout = check_positive_integer(os.getenv("MASTER_TIMEOUT", default="5"), purpose="master timeout")
        self.hb_timer = TimerReset(self.master_timeout, self.master_timeout_handler)
        self.hostname = socket.gethostname()
        self.port = check_positive_integer(os.getenv("SLAVE_PORT", default="8888"), purpose="slave port")
        self.url = "http://" + self.hostname + ":" + str(self.port) + "/"
        self.hash = ""

        self.master_host = os.getenv("MASTER_HOST", default="localhost")
        self.master_port = check_positive_integer(os.getenv("MASTER_PORT", default="8000"), purpose="master port")
        self.master_base = "http://" + self.master_host + ":" + str(self.master_port)
        self.master_url = self.master_base + "/slave"

        self.register()

    def register(self, first_loop=True):
        # Continuously try to register itself with the master if the state is in INIT
        req_str = json.dumps({"url": self.url})
        registered = False
        while not registered:
            try:
                logging.info("Attempting to register with master")
                req = requests.post(self.master_url, data=req_str)
                body = req.json()
                if req.status_code == requests.codes.ok:
                    # Registered with master, begin state transition
                    registered = True
                    if self.state == "INIT":
                        self.state = "READY"
                        self.hash = body["hash"]

                    if not first_loop:
                        # Since previous timer expired, create new timer object
                        self.hb_timer.reset()
                        self.hb_timer.run()
                    else:
                        self.hb_timer.start()  # Start the master timeout

                    logging.info("Slave successfully registered with master; started master timeout=" + \
                                 str(self.master_timeout) + "s")
                else:
                    logging.error("Master returned incorrect response code, retrying registration...")
                    logging.info(body)
            except Exception as e:
                # Master did not respond correctly, continue trying
                logging.error("POST to master " + self.master_host + " failed:\n" + str(e))
            sleep(5)

    def master_timeout_handler(self):
        # Connection with master lost
        logging.info("Master timed out!")
        self.register(first_loop=False)         # Retry registration loop

    def run_task(self, task):
        try:
            if self.state == "READY":
                if (not self.runner) or (not self.task):
                    sleeptime = float(task["sleeptime"])
                    if sleeptime < 0:
                        raise ValueError
                    # Use subprocess that can be killed
                    self.task = task
                    self.state = "RUNNING"
                    self.runner = self.popenAndCall(self.done_transition, ["sleep", self.task["sleeptime"]])
                    return True
                else:
                    logging.error("There is already a task running...")
            else:
                logging.error("Attempted to run task in state  " + self.state)
        except ValueError:
            logging.error("Task sleeptime definition was not a positive number!")
        return False

    def done_transition(self, returncode):
        if returncode == 0:
            logging.info("Slave has completed task " + self.task["taskname"])
            try:
                req_dict = {
                    "task_name": self.task["taskname"],
                    "slave_hash": self.hash
                }
                req = requests.post(self.master_base + "/scheduler/task_done", data=json.dumps(req_dict))
                if req.status_code == requests.codes.ok:
                    self.state = "READY"
                    self.task = []
                    self.runner = []
                else:
                    self.state = "DONE"
            except Exception as e:
                logging.error(e)
        else:
            logging.error("Task execution returned " + str(returncode))
            self.reset()

    def reset(self):
        self.state = "INIT"
        self.register(first_loop=False)
        self.task = []
        self.runner = []

    def refresh_master_timeout(self):
        self.hb_timer.reset(interval=self.master_timeout)

    @staticmethod
    def popenAndCall(onExit, popenArgs):
        """
        Runs the given args in a subprocess.Popen, and then calls the function
        onExit when the subprocess completes.
        onExit is a callable object, and popenArgs is a list/tuple of args that
        would give to subprocess.Popen.
        """

        def runInThread(onExit, popenArgs):
            proc = subprocess.Popen(popenArgs)
            proc.wait()
            onExit(proc.returncode)
            return

        thread = threading.Thread(target=runInThread, args=(onExit, popenArgs, ))
        thread.start()
        # returns immediately after the thread starts
        return thread

