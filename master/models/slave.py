from mongoengine import Document
from mongoengine.fields import StringField
import hashlib
from mongoengine import signals
import logging


class Slave(Document):

    url = StringField(required=True)
    state = StringField(required=True)
    hash = StringField(required=True, unique=True)

    @property
    def created(self):
        return self.id.generation_time.isoformat() if self.id else None

    @classmethod
    def pre_save(cls, sender, document, **kwargs):
        doc_url = document.url
        document.hash = hashlib.sha1(doc_url.encode()).hexdigest()
        logging.debug("Pre-save hook: generated sha1 for url " + doc_url)

    def to_dict(self):
        return {
            'hash': "something",
            'url': self.url,
            'state': self.state,
        }


signals.pre_save.connect(Slave.pre_save, sender=Slave)
