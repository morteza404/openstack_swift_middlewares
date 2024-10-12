import json
from swift.common.swob import Request
from swift.common.utils import get_logger, split_path


class HideSegGetMiddleware:
    def __init__(self, app, conf):
        self.app = app
        self.logger = get_logger(conf, log_route="hide_seg_get")

    def __call__(self, env, start_response):
        req = Request(env)
        try:
            _, account, container, obj = split_path(env["PATH_INFO"], 0, 4, True)
        except ValueError:
            return self.app(env, start_response)

        self.logger.warning(
            f"hide segments get::: account, container, obj : '{account} {container} {obj}'\n"
        )
        if container is not None and container == "":
            container = None

        resp = req.get_response(self.app)

        if req.method != "GET" or (account and container is not None):
            return self.app(env, start_response)

        json_data = json.loads(resp.body.decode("utf-8"))

        del_list = []

        for container in json_data[:]:
            if ("_segments" in container["name"]) or ("+segments" in container["name"]):
                del_list.append(str(container["name"]))
                json_data.remove(container)

        self.logger.warning(
            f"hide segments get::: These items are not shown in result:\n ' {str(del_list)}'\n"
        )
        resp.body = json.dumps(json_data).encode("utf-8")
        return resp(env, start_response)


def filter_factory(global_conf, **local_conf):
    conf = global_conf.copy()
    conf.update(local_conf)

    def hide_seg_get_filter(app):
        return HideSegGetMiddleware(app, conf)

    return hide_seg_get_filter
