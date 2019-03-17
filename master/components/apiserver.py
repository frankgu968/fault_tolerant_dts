import logging
import gunicorn.app.base
from gunicorn.six import iteritems
from app.start import application

gunicorn.SERVER_SOFTWARE = 'gunicorn'  # hide gunicorn version

class Application(gunicorn.app.base.BaseApplication):
    def __init__(self, app, options=None):
        self.options = options or {}
        self.application = app
        super(Application, self).__init__()

    def load_config(self):
        config = dict([(key, value) for key, value in iteritems(self.options)
                       if key in self.cfg.settings and value is not None])
        for key, value in iteritems(config):
            self.cfg.set(key.lower(), value)

    def load(self):
        return self.application


class Server:
    @staticmethod
    def start():
        logging.info("Starting API server")
        opts = {
            "bind": ["0.0.0.0:8000"]
        }
        Application(application, opts).run()



