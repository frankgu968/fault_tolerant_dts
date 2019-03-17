from mongoengine import Document
from mongoengine.fields import StringField


class Task(Document):
    taskname = StringField(required=True)
    sleeptime = StringField(required=True)
    state = StringField(required=True)
    host = StringField(required=False)

    @property
    def created(self):
        return self.id.generation_time.isoformat() if self.id else None

    def to_dict(self):
        return {
            'taskname': str(self.taskname),
            'sleeptime': str(self.sleeptime),
            'state': str(self.state),
            'host': str(self.host)
        }
