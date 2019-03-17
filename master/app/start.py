import falcon

from .resources.slave import SlaveResource
from .resources.scheduler import SchedulerResource


api = application = falcon.API()
api.req_options.auto_parse_form_urlencoded = True


slave_resource = SlaveResource()
scheduler_resource = SchedulerResource()
api.add_route('/scheduler/{action}', scheduler_resource)
api.add_route('/slave', slave_resource)

