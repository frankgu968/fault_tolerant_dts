from pymongo import MongoClient
from random import randint
from os import environ
import logging

DB_NAME =        environ["DB_NAME"]
TASK_COL_NAME =  environ["TASK_COL_NAME"]
MONGO_HOST =     environ["MONGO_HOST"]
MONGO_PORT =     environ["MONGO_PORT"]
MONGO_USER =     environ["MONGO_USER"]
MONGO_PASSWORD = environ["MONGO_PASSWORD"]


def seed_db():
    if not MONGO_PORT.isdigit():
        logging.error("MONGO_PORT environment variable must be a positive number!")
        exit(1)

    client = MongoClient(MONGO_HOST,
                         int(MONGO_PORT),
                         username=MONGO_USER,
                         password=MONGO_PASSWORD)

    # Clean database and recreate
    logging.info("Creating database " + DB_NAME)
    if DB_NAME in client.list_database_names():
        client.drop_database(DB_NAME)
    new_db = client[DB_NAME]

    # Add task collection
    logging.info("Adding collection " + TASK_COL_NAME)
    task_col = new_db[TASK_COL_NAME]

    # Seed 100 tasks in task collection
    logging.info("Seeding tasks...")
    for idx in range(100):
        seed_task(idx, task_col)

    logging.info("Database seeded!")

def seed_task(index, collection):
    new_task = {
        "taskname": "task" + str(index),
        "sleeptime": randint(1, 30),
        "state": "created"
    }
    collection.insert_one(new_task)


if __name__ == "__main__":
    logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=logging.INFO,
        datefmt='%Y-%m-%d %H:%M:%S')
    seed_db()
