import json
from swift.common.swob import Request, Response
from swift.common.utils import get_logger, split_path


class LOFixMiddleware:
    def __init__(self, app, conf):
        self.app = app
        self.logger = get_logger(conf, log_route="lofix")

    def __call__(self, env, start_response):
        req = Request(env)
        _, account, container, obj = split_path(env["PATH_INFO"], 1, 4, True)
        self.logger.warning(
            f"lofix::: account, container, obj : '{account} {container} {obj}'\n"
        )
        if container is not None and container == "":
            container = None

        response = self.app(env, start_response)

        if req.method != "GET" or (account and container is not None):
            return response

        for data in response:
            json_data = json.loads(data.decode("utf-8"))

            del_list = []

            for item in json_data[:]:
                item.get("name")
                if ("_segments" in item.get("name")) or ("+segments" in item["name"]):
                    del_list.append(str(item["name"]))
                    json_data.remove(item)

            body_json = json.dumps(json_data)
            self.logger.warning(
                f"lofix::: These items are not shown in result:\n ' {str(del_list)}'\n"
            )
        resp = Response(
            request=req,
            body=body_json,
            content_type="application/json",
        )
        return resp(env, start_response)


def filter_factory(global_conf, **local_conf):
    conf = global_conf.copy()
    conf.update(local_conf)

    def lofix_filter(app):
        return LOFixMiddleware(app, conf)

    return lofix_filter
