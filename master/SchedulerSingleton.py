from scheduler import Scheduler


class SchedulerSingleton(object):
    def __init__(self):
        self.scheduler = Scheduler()
