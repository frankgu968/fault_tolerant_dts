import falcon

from .resources.slaveself import SlaveSelfResource


api = application = falcon.API()
api.req_options.auto_parse_form_urlencoded = True


slave_self = SlaveSelfResource()
api.add_route('/', slave_self)

