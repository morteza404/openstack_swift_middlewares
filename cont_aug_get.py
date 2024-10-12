import json
from urllib.parse import quote
from swift.common.utils import get_logger
from swift.common.wsgi import make_subrequest
from swift.common.swob import Request, Response


class ContAugGetMiddleware:
    def __init__(self, app, conf):
        self.app = app
        self.logger = get_logger(conf, log_route="cont_aug_get")

    def __call__(self, env, start_response):
        req = Request(env)
        if req.method == "GET" and "X-List-Object-Metadata" in req.headers:
            try:
                objects = self.get_container_objects(env, env["PATH_INFO"])
                data_string = objects.decode("utf-8")
                data_list = json.loads(data_string)
                indices = {v["name"]:i for i,v in enumerate(data_list) if "name" in v}
                for obj in data_list:
                    if "name" in obj:
                        obj_metadata = self.get_object_metadata(
                            env, env["PATH_INFO"] + f"/{obj['name']}"
                        )
                        data_list[indices[obj["name"]]].update(obj_metadata)
                resp = Response(
                    request=req,
                    body=json.dumps(data_list, ensure_ascii=False),
                    content_type="application/json",
                )
                return resp(env, start_response)
            except Exception as e:
                self.logger.error(f"Error listing object metadata: {e}")
                return self.app(env, start_response)
        else:
            return self.app(env, start_response)

    def get_container_objects(self, env, path):
        subreq = make_subrequest(env, method="GET", path=path)
        resp = subreq.get_response(self.app)

        if resp.status_int // 100 == 2:
            objects = resp.body
            return objects
        else:
            resp.app_iter.close()
            return []
        
    def get_object_metadata(self, env, path):
        encoded_path = quote(path)
        subreq = make_subrequest(env, method="HEAD", path=encoded_path)
        resp = subreq.get_response(self.app)

        if resp.status_int // 100 == 2:
            return resp.headers
        else:
            resp.app_iter.close()
            return {}       


def filter_factory(global_conf, **local_conf):
    conf = global_conf.copy()
    conf.update(local_conf)

    def cont_aug_get_filter(app):
        return ContAugGetMiddleware(app, conf)

    return cont_aug_get_filter
