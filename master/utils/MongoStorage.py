import os
import logging
import mongoengine as mongo

logger = logging.getLogger(__name__)


class MongoStorage():
    def __init__(self):
        self.db_name = os.getenv("DB_NAME", default="scheduler_db")
        self.task_col = os.getenv("TASK_COL_NAME", default="task")
        self.slave_col = os.getenv("SLAVE_COL_NAME", default="slave")
        self.db_uri = "mongodb://" + \
                      os.getenv("MONGO_USER", default="root") + ":" + \
                      os.getenv("MONGO_PASSWORD", default="example") + "@" + \
                      os.getenv("MONGO_HOST", default="localhost") + ":" + \
                      os.getenv("MONGO_PORT", default="27017") + "/?authSource=admin"
        self.db = mongo.connect(self.db_name, host=self.db_uri, alias="default", connect=True)
        logger.debug("Connected to mongodb!")

    def get_db(self):
        return self.db[self.db_name]

    def slave_col_name(self):
        return self.slave_col()
