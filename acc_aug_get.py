import json
from swift.common.wsgi import make_subrequest
from swift.common.swob import Request, Response
from swift.common.utils import get_logger, split_path


class AccAugGetMiddleware:
    def __init__(self, app, conf):
        self.app = app
        self.logger = get_logger(conf, log_route="acc_aug_get")

    def __call__(self, env, start_response):
        req = Request(env)

        try:
            _, account, _, _ = split_path(env["PATH_INFO"], 0, 4, True)
        except ValueError:
            return self.app(env, start_response)

        if (
            req.method == "GET"
            and len(req.path.split("/")) < 4
            and account
        ):
            sub_req_meta = make_subrequest(
                env,
                path=env["PATH_INFO"],
                method="GET",
            )
            resp_meta = sub_req_meta.get_response(self.app)

            if resp_meta.status_int // 100 == 2:
                json_data = json.loads(resp_meta.body.decode("utf-8"))
                for container in json_data:
                    if not container["name"].endswith(("_segments", "+segments")):
                        full_path = f"{env['PATH_INFO']}/{container['name']}"
                        container_sub_req_meta = make_subrequest(
                            env, path=full_path, method="HEAD"
                        )
                        container_resp_meta = container_sub_req_meta.get_response(
                            self.app
                        )
                        data = {
                            "read_acls": container_resp_meta.headers.get("Read_Acls"),
                            "write_acls": container_resp_meta.headers.get("Write_Acls"),
                            "bytes_used": container_resp_meta.headers.get("Bytes_Used"),
                            "total_bytes_used": container_resp_meta.headers.get(
                                "Total_Bytes_Used"
                            ),
                            "related_containers": container_resp_meta.headers.get(
                                "Related_Containers"
                            ),
                        }
                        container.update(data)
                        self.convert_string_numbers_to_int(container)

            resp = Response(
                request=req, body=json.dumps(json_data), content_type="application/json"
            )
            return resp(env, start_response)

        return self.app(env, start_response)

    def convert_string_numbers_to_int(self, d):
        for key, value in d.items():
            if isinstance(value, str):
                try:
                    d[key] = int(value)
                except ValueError:
                    pass
        return d


def filter_factory(global_conf, **local_conf):
    conf = global_conf.copy()
    conf.update(local_conf)

    def acc_aug_get_middleware_filter(app):
        return AccAugGetMiddleware(app, conf)

    return acc_aug_get_middleware_filter
