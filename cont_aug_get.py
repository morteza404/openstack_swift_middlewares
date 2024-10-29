import json
from swift.common.http import is_success
from swift.common.wsgi import make_subrequest
from swift.common.swob import Request, Response
from swift.common.utils import get_logger, split_path


class CustomException(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


class ContAugGetMiddleware:
    def __init__(self, app, conf):
        self.app = app
        self.logger = get_logger(conf, log_route="cont_aug_get")

    def __call__(self, env, start_response):
        req = Request(env)
        try:
            _, _, container, _ = split_path(env["PATH_INFO"], 0, 4, True)
        except ValueError:
            return self.app(env, start_response)
        if req.method == "GET" and len(req.path.split("/")) < 5 and container:
            try:
                resp = req.get_response(self.app)
                json_data = json.loads(resp.body.decode("utf-8"))
                for object in json_data:
                    object_meta = self.get_object_metadata(req, object["name"])
                    object.update(object_meta)

                resp.body = json.dumps(json_data).encode("utf-8")
                resp.content_length = len(resp.body)
                return resp(env, start_response)
            except CustomException as exception:
                return Response(
                    body=str(exception), status=exception.status, request=req
                )(env, start_response)

        return self.app(env, start_response)

    def get_object_metadata(self, req, object_name):
        subreq = make_subrequest(
            req.environ, method="HEAD", path=f"{req.path_info}/{object_name}"
        )
        resp = subreq.get_response(self.app)

        if not is_success(resp.status_int):
            message = f"ERROR MIDDLEWARE CONT_AUG_GET :: {resp.status} {subreq.method} {subreq.path}"
            self.logger.error(message)
            raise CustomException(resp.status, resp.body.decode())

        return resp.headers


def filter_factory(global_conf, **local_conf):
    conf = global_conf.copy()
    conf.update(local_conf)

    def cont_aug_get_filter(app):
        return ContAugGetMiddleware(app, conf)

    return cont_aug_get_filter
