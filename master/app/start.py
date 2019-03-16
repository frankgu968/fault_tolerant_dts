import falcon

from .resources.slave import SlaveResource


api = application = falcon.API()
api.req_options.auto_parse_form_urlencoded = True


slave_resource = SlaveResource()
api.add_route('/slave/{name}', slave_resource)
api.add_route('/slave', slave_resource)

