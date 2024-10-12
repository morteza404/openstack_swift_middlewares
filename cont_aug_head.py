from swift.common.wsgi import make_subrequest
from swift.common.swob import Request, Response
from swift.common.utils import get_logger, split_path


class ContAugHeadMiddleware:
    def __init__(self, app, conf):
        self.app = app
        self.logger = get_logger(conf, log_route="cont_aug_head")

    def __call__(self, env, start_response):
        req = Request(env)

        try:
            _, _, container, _ = split_path(env["PATH_INFO"], 0, 4, True)
        except ValueError:
            return self.app(env, start_response)

        if req.method == "HEAD" and len(req.path.split("/")) < 5 and container:
            account_path = "/".join(env["PATH_INFO"].split("/")[:-1])

            resp_dict = self.get_subrequest_metadata(env, account_path, container)
            resp = Response(request=req, headers=resp_dict)
            return resp(env, start_response)

        return self.app(env, start_response)

    def get_subrequest_metadata(self, env, account_path, container):
        container_sub_req_meta = make_subrequest(
            env, path=f"{account_path}/{container}", method="HEAD"
        )
        container_resp_meta = container_sub_req_meta.get_response(self.app)
        bytes_used = int(container_resp_meta.headers.get("X-Container-Bytes-Used", 0))
        resp_dict = {
            "read_acls": "None",
            "write_acls": "None",
            "bytes_used": bytes_used,
            "total_bytes_used": bytes_used,
            "related_containers": [],
        }
        subrequest_paths = [
            f"{account_path}/{container}_segments",
            f"{account_path}/{container}+segments",
        ]
        for path in subrequest_paths:
            related_containers_sub_req_meta = make_subrequest(
                env, path=path, method="HEAD"
            )
            related_containers_resp_meta = related_containers_sub_req_meta.get_response(
                self.app
            )

            if related_containers_resp_meta.status_int // 100 == 2:
                read_acl = related_containers_resp_meta.headers.get(
                    "X-Container-Read", "None"
                )
                write_acl = related_containers_resp_meta.headers.get(
                    "X-Container-Write", "None"
                )
                total_bytes_used = (
                    int(
                        related_containers_resp_meta.headers.get(
                            "X-Container-Bytes-Used", 0
                        )
                    )
                    + resp_dict["total_bytes_used"]
                )
                resp_dict["read_acls"] = read_acl
                resp_dict["write_acls"] = write_acl
                resp_dict["bytes_used"] = bytes_used
                resp_dict["total_bytes_used"] = total_bytes_used
                resp_dict["related_containers"].append(path.split("/")[-1])
        resp_dict["related_containers"] = ",".join(resp_dict["related_containers"])
        updated_resp = {**container_resp_meta.headers, **resp_dict}
        return updated_resp


def filter_factory(global_conf, **local_conf):
    conf = global_conf.copy()
    conf.update(local_conf)

    def cont_aug_head_middleware_filter(app):
        return ContAugHeadMiddleware(app, conf)

    return cont_aug_head_middleware_filter
