import os
import logging
from time import sleep
from multiprocessing import Process
from MongoStorage import MongoStorage
from models import Slave, Task
from mongoengine import Q, DoesNotExist
import requests
from requests.exceptions import ConnectionError, ConnectTimeout
import _thread
from ResettableTimer import TimerReset

# TODO: Change this to use environment
HB_GRACE_PERIOD = 2.0

class Scheduler:
    def __init__(self):
        self.db = []
        self.continue_run = True
        self.hb_timers = {}

        # Initialize database connection and collection
        self.slave_col_name = os.getenv("SLAVE_COL_NAME", default="slave")

        self.schedule_interval = os.getenv("SCHEDULE_INTERVAL", default="5")
        if self.schedule_interval.isdigit() and int(self.schedule_interval) > 0:
            self.schedule_interval = int(self.schedule_interval)
        else:
            logging.error("Invalid schedule interval, must be (0,N] in seconds")
            exit(1)

        self.heartbeat_interval = os.getenv("HEARTBEAT_INTERVAL", default="3")
        if self.heartbeat_interval.isdigit() and int(self.heartbeat_interval) > 0:
            self.heartbeat_interval = int(self.heartbeat_interval)
        else:
            logging.error("Invalid heartbeat interval, must be (0,N] in seconds")
            exit(1)

    def connect_db(self):
        self.db = MongoStorage().get_db()

        if self.slave_col_name not in self.db.list_collection_names():
            logging.info("No metadata collection found, creating new collection")
            self.db.create_collection(self.slave_col_name())
        else:
            logging.info("Previous session metadata found, restoring master")

    def start(self):
        logging.info("Starting scheduler loop, interval="+str(self.schedule_interval)+"s")
        scheduler_loop = Process(target=self.do_schedule_once, args=(self.schedule_interval, ))
        scheduler_loop.start()

        logging.info("Starting heartbeat sensor, interval="+str(self.heartbeat_interval)+"s")
        heartbeat_loop = Process(target=self.heartbeat_sensor, args=(self.heartbeat_interval, ))
        heartbeat_loop.start()

    def do_schedule_once(self, interval):
        self.connect_db()   # Connect to database before fork

        while self.continue_run:
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
                    logging.info("Assigning task " + task.taskname + "to slave " + slave.hash)
                    # Dispatch job to slave
                    # Use threads here to share mongoengine connector and process request asynchronously
                    _thread.start_new_thread(self.send_task, (task, slave, ))
            else:
                logging.info("All tasks completed!")
            sleep(interval)

        logging.info("Scheduler shutdown requested; shutting down scheduler now...")

    def heartbeat_sensor(self, interval):
        self.connect_db()   # Seperate connection entity as the scheduler

        while self.continue_run:
            try:
                slaves = Slave.objects()
                for slave in slaves:
                    # make async request for heartbeat on another thread
                    _thread.start_new_thread(self.ping_slave_hb, (slave,))
            except Exception as e:
                logging.error(e)
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
            # slave.delete() DEBUG  # Remove the faulty slave

    def slave_hb_callback(self, req, slave):
        if req.status_code == requests.codes.ok:
            # TODO: when real slave comes in!
            # slave_reply = req.json() DEBUG
            # slave.update(host=slave_reply["url"], state=slave_reply["state"]) DEBUG
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
            logging.warning("Slave " + slave.hash + "returned incorrect response code; removing from database...")
            # slave.delete() DEBUG

    @staticmethod
    def handle_hb_timeout(slave):
        # Slave can be reached, but does not respond correctly
        logging.warning("Slave " + slave.hash + " has timed out; removing from database...")

    def send_task(self, task, slave):
        try:
            req = requests.post(slave.url, data=task.to_dict())
            self.assign_cb(req, task, slave)
        except Exception as e:
            # Slave did not respond correctly, do not change task status
            logging.warning("POST to slave " + slave.hash + " failed:\n" + str(e))
            slave.delete() # Remove the unhealthy slave

    @staticmethod
    def assign_cb(req, task, slave):
        # Callback to update database with task assignment
        if req.status_code == requests.codes.ok:
            task.update(host=slave.url, state="running")
            slave.update(state="RUNNING")
            logging.info("Task registered with slave " + slave.hash)


