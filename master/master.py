import logging
from scheduler import Scheduler
from apiserver import Server

if __name__ == "__main__":
    logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=logging.DEBUG,
        datefmt='%Y-%m-%d %H:%M:%S')
    Scheduler().start()
    Server().start()
