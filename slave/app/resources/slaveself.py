import json
import logging
import falcon

class SlaveSelfResource(object):
    def __init__(self):
        self.mongo = MongoStorage()




