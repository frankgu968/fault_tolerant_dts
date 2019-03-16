import os
import logging
from time import sleep
from multiprocessing import Process
from MongoStorage import MongoStorage
from models import Slave, Task
from mongoengine import Q,DoesNotExist
import requests
import _thread

class Scheduler():
    def __init__(self):
        self.db = []

        # Initialize database connection and collection
        self.slave_col_name = os.getenv("SLAVE_COL_NAME", default="slave")

        self.schedule_interval = os.getenv("SCHEDULE_INTERVAL", default="5")
        if self.schedule_interval.isdigit() and int(self.schedule_interval) > 0:
            self.schedule_interval = int(self.schedule_interval)
        else:
            logging.error("Invalid schedule interval, must be (0,N] in seconds")
            exit(1)

        self.start_loop()

    def connect_db(self):
        self.db = MongoStorage().get_db()

        if self.slave_col_name not in self.db.list_collection_names():
            logging.info("No metadata collection found, creating new collection")
            self.db.create_collection(self.slave_col_name())
        else:
            logging.info("Previous session metadata found, restoring master")

    def start_loop(self):
        logging.info("Starting scheduler loop, interval="+str(self.schedule_interval)+"s")
        scheduler_loop = Process(target=self.do_schedule_once, args=(self.schedule_interval, ))
        scheduler_loop.start()

    def do_schedule_once(self, interval):
        self.connect_db()   # Connect to database before fork

        all_done = False
        while not all_done:
            try:
                task = Task.objects.get(state="created")
            except DoesNotExist:
                logging.info("No incomplete tasks found!")
                task = None

            if task:
                logging.info("Found pending task: " + task.taskname)
                try:
                    slave = Slave.objects.get(state="READY")
                except DoesNotExist:
                    logging.info("No available slaves found, waiting for next loop...")
                    slave = None

                if slave:
                    logging.info("Assigning task " + task.taskname + "to slave " + slave.hash)
                    # Dispatch job to slave
                    # Use threads here to share mongoengine connector
                    _thread.start_new_thread(self.send_task, (task, slave, ))
            sleep(interval)

    def send_task(self, task, slave):
        print(slave)
        try:
            req = requests.post(slave.url, data=task.to_dict())
            self.assign_cb(req, task, slave)
        except Exception as e:
            logging.warning("POST to slave " + slave.hash + " failed:\n" + str(e))

    @staticmethod
    def assign_cb(req, task, slave):
        # Callback to update database
        if req.status_code == requests.codes.ok:
            task.update(host=slave.url, state="running")
            slave.update(state="RUNNING")
            logging.info("Task registered with slave " + slave.hash)

