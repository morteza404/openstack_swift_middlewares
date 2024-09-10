import json
from swift.common.wsgi import make_subrequest
from swift.common.swob import Request, Response
from swift.common.utils import get_logger, split_path


class ListContainerACLMiddleware:
    def __init__(self, app, conf):
        self.app = app
        self.logger = get_logger(conf, log_route="list_container_acl")

    def __call__(self, env, start_response):
        req = Request(env)
        status_code = [None]

        def custom_start_response(status, response_headers, *args):
            status_code[0] = status.split(" ")[0] if status else None
            return start_response(status, response_headers)

        response = self.app(env, custom_start_response)

        _, account, _, _ = split_path(env["PATH_INFO"], 1, 4, True)

        if (
            req.method == "GET"
            and len(req.path.split("/")) < 4
            and account
            and (int(status_code[0]) // 100 == 2)
        ):
            containers = []
            for data in response:
                json_data = json.loads(data.decode("utf-8"))
                for container in json_data:
                    sub_req_meta = make_subrequest(
                        env,
                        path=env["PATH_INFO"] + f"/{container['name']}",
                        method="HEAD",
                    )
                    resp_meta = sub_req_meta.get_response(self.app)

                    if resp_meta.status_int // 100 == 2:
                        read_acl = resp_meta.headers.get("X-Container-Read", "None")
                        write_acl = resp_meta.headers.get("X-Container-Write", "None")
                        container["read_acl"] = read_acl
                        container["write_acl"] = write_acl
                        containers.append(container)
                    else:
                        ultimate_response = Response(
                            body=resp.body.decode("utf-8"), status_int=resp.status_int
                        )
                        return ultimate_response(env, start_response)

            resp = Response(
                request=req,
                body=json.dumps(containers),
                content_type="application/json",
            )
            return resp(env, start_response)

        return response


def filter_factory(global_conf, **local_conf):
    conf = global_conf.copy()
    conf.update(local_conf)

    def list_container_acl_middleware_filter(app):
        return ListContainerACLMiddleware(app, conf)

    return list_container_acl_middleware_filter
