import os
import logging
from time import sleep
from utils.MongoStorage import MongoStorage
from models import Slave, Task
from mongoengine import Q, DoesNotExist
import requests
import json
from requests.exceptions import ConnectionError, ConnectTimeout
from threading import Thread
from utils.ResettableTimer import TimerReset

# TODO: Change this to use environment
HB_GRACE_PERIOD = 2.0


def check_positive_integer(test_str, purpose=""):
    if test_str.isdigit() and int(test_str) > 0:
        return int(test_str)
    else:
        logging.error("Invalid " + purpose + " , must be (0,N] in seconds")
        exit(1)


class Scheduler:
    def __init__(self):
        self.db = []
        self.continue_run = False   # Don't start the scheduler on startup

        # Object containers
        self.hb_timers = {}
        self.scheduler_loop = []
        self.heartbeat_loop = []

        # Initialize database connection and collection
        self.slave_col_name = os.getenv("SLAVE_COL_NAME", default="slave")
        self.schedule_interval = check_positive_integer(os.getenv("SCHEDULE_INTERVAL", default="5"), purpose="schedule interval")
        self.heartbeat_interval = check_positive_integer(os.getenv("HEARTBEAT_INTERVAL", default="3"), purpose="heartbeat interval")

        self.start()

    def connect_db(self):
        self.db = MongoStorage().get_db()

        if self.slave_col_name not in self.db.list_collection_names():
            logging.info("No metadata collection found, creating new collection")
            self.db.create_collection(self.slave_col_name())
        else:
            logging.info("Previous session metadata found, restoring master")

    def start(self):
        self.continue_run = True
        self.connect_db()
        logging.info("Starting scheduler loop, interval="+str(self.schedule_interval)+"s")
        self.scheduler_loop = Thread(target=self.run_scheduler_loop, args=(self.schedule_interval, ))
        self.scheduler_loop.start()

        logging.info("Starting heartbeat sensor, interval="+str(self.heartbeat_interval)+"s")
        self.heartbeat_loop = Thread(target=self.heartbeat_sensor, args=(self.heartbeat_interval, ))
        self.heartbeat_loop.start()

    def stop(self):
        # Graceful shutdown
        self.continue_run = False
        self.heartbeat_loop.join()
        self.scheduler_loop.join()

    def do_schedule_once(self):
        task = Task.objects(Q(state="created") | Q(state="killed"))

        if task:
            task = task[0]
            logging.info("Found pending task: " + task.taskname)
            try:
                slave = Slave.objects.get(state="READY")
            except DoesNotExist:
                logging.info("No available slaves found, waiting for next loop...")
                slave = None

            if slave:
                logging.info("Assigning task " + task.taskname + " to slave " + slave.hash)
                # Dispatch job to slave
                # Use threads here to share mongoengine connector and process request asynchronously
                Thread(target=self.send_task, args=(task, slave,)).start()
        else:
            logging.info("No tasks to be scheduled...")

    def run_scheduler_loop(self, interval):
        while self.continue_run:
            self.do_schedule_once()
            sleep(interval)

        logging.info("Scheduler shutdown requested; shutting down scheduler now...")

    def heartbeat_sensor(self, interval):
        while self.continue_run:
            try:
                slaves = Slave.objects()
                for slave in slaves:
                    # make async request for heartbeat on another thread
                    Thread(target=self.ping_slave_hb, args=(slave,)).start()
            except Exception as e:
                logging.error("Threading exception in heartbeat sensor" + str(e))
            sleep(interval)

        logging.info("Scheduler shutdown requested; shutting down heartbeat sensor now...")

    def ping_slave_hb(self, slave):
        try:
            logging.debug("Making heartbeat request to slave " + slave.hash)
            req = requests.get(slave.url)
            self.slave_hb_callback(req, slave)
        except (ConnectionError, ConnectTimeout) as e:
            # Slave failed heartbeat
            logging.warning("POST to slave " + slave.hash + " failed:\n" + str(e))
            self.remove_slave(slave)

    def slave_hb_callback(self, req, slave):
        if req.status_code == requests.codes.ok:
            slave_reply = json.loads(req.json())
            # On this hb request, slave side would have already set state -> READY
            if slave_reply["state"] == "DONE":
                # Master offline recovery
                self.handle_task_complete(slave_reply["task"]["taskname"], slave_reply["hash"])
            else:
                slave.update(hash=slave_reply["hash"], url=slave_reply["url"], state=slave_reply["state"])

            logging.debug(slave.hash + " replied!")
            # Slave is alive, refresh slave's timer
            if slave.hash in self.hb_timers:
                logging.info("Resetting " + slave.hash + " heartbeat timer")
                self.hb_timers[slave.hash].reset()
            else:
                logging.info("Starting new heartbeat timer for slave " + slave.hash)
                self.hb_timers[slave.hash] = TimerReset(self.heartbeat_interval + HB_GRACE_PERIOD,
                                                        self.handle_hb_timeout, args=(slave,))
                self.hb_timers[slave.hash].start()
        else:
            logging.warning("Slave " + slave.hash + " returned incorrect response code")
            self.remove_slave(slave)

    def handle_hb_timeout(self, slave):
        # Slave can be reached, but does not respond correctly
        logging.warning("Slave " + slave.hash + " has timed out")
        self.remove_slave(slave)

    def remove_slave(self, slave):
        # Universal method for removing slave and setting its task(s) to "killed state"
        if self.continue_run:
            # Only apply changes if the scheduler is still set to running to avoid async behavior due to detached thread
            logging.debug("Removing slave " + slave.hash + " from database")
            slave_tasks = Task.objects(host=slave.hash, state="running")
            if slave_tasks:
                for task_to_kill in slave_tasks:
                    logging.debug("Setting slave " + slave.hash + " task " + task_to_kill.taskname + "to state=killed")
                    task_to_kill.update(state="killed")
            slave.delete()
        else:
            logging.debug("Ignoring delete request for slave " + slave.hash + " since the scheduler has stopped")

    def send_task(self, task, slave):
        try:
            logging.debug("Sending task " + str(task.to_dict()) + " to slave " + slave.hash)
            req = requests.post(slave.url, json=task.to_dict())
            self.assign_cb(req, task, slave)
        except Exception as e:
            # Slave did not respond correctly, do not change task status
            logging.warning("POST to slave " + slave.hash + " failed:\n" + str(e))
            self.remove_slave(slave)

    def assign_cb(self, req, task, slave):
        # Callback to update database with task assignment
        if req.status_code == requests.codes.ok:
            task.update(host=slave.hash, state="running")
            slave.update(state="RUNNING")
            logging.info("Task registered with slave " + slave.hash)
        else:
            logging.warning("Slave " + slave.hash + " returned incorrect response code")
            self.remove_slave(slave)

    @staticmethod
    def handle_task_complete(task_name, slave_hash):
        logging.info("Slave " + slave_hash + " completed task " + task_name)
        slave = Slave.objects.get(hash=slave_hash)
        slave.update(hash=slave_hash, state="READY")
        task = Task.objects.get(taskname=task_name)
        task.update(state="success", host=slave_hash)
