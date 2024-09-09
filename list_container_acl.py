import json
from swift.common.wsgi import make_subrequest
from swift.common.utils import get_logger, split_path
from swift.common.swob import Request, Response, HTTPInternalServerError


class ListContainerACLMiddleware:
    def __init__(self, app, conf):
        self.app = app
        self.logger = get_logger(conf, log_route="list_container_acl")

    def __call__(self, env, start_response):
        req = Request(env)
        _, account, _, _ = split_path(env["PATH_INFO"], 1, 4, True)
        if req.method == "GET" and len(req.path.split("/")) < 4 and account:
            try:
                containers = self._get_containers_with_acls(env, env["PATH_INFO"])

                resp = Response(
                    request=req,
                    body=json.dumps(containers),
                    content_type="application/json",
                )
                return resp(env, start_response)

            except Exception as e:
                message = f"Error retrieving containers or ACLs: {str(e)}"
                self.logger.error(message)
                ultimate_response = HTTPInternalServerError(body=message, request=req)
                return ultimate_response(env, start_response)

        return self.app(env, start_response)

    def _get_containers_with_acls(self, env, path):
        sub_req = make_subrequest(env, path=path, method="GET")
        resp = sub_req.get_response(self.app)

        if resp.status_int != 200:
            self.logger.error(f"Error fetching containers: {resp.body.decode('utf-8')}")
            raise Exception(
                f"Error fetching containers: {resp.status_int} {resp.body.decode('utf-8')}"
            )

        containers = json.loads(resp.body.decode("utf-8"))

        for container in containers:
            sub_req_meta = make_subrequest(
                env, path=path + f"/{container['name']}", method="HEAD"
            )
            resp_meta = sub_req_meta.get_response(self.app)

            if resp_meta.status_int // 100 == 2:
                read_acl = resp_meta.headers.get("X-Container-Read", "None")
                write_acl = resp_meta.headers.get("X-Container-Write", "None")
                container["read_acl"] = read_acl
                container["write_acl"] = write_acl

        return containers


def filter_factory(global_conf, **local_conf):
    conf = global_conf.copy()
    conf.update(local_conf)

    def list_container_acl_middleware_filter(app):
        return ListContainerACLMiddleware(app, conf)

    return list_container_acl_middleware_filter
