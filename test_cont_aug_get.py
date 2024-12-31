import json
import unittest
from unittest.mock import MagicMock, patch
from swift.common.swob import Request, Response
from cont_aug_get import ContAugGetMiddleware, filter_factory


class FakeApp:
    def __call__(self, env, start_response):
        resp = Response(body=b"OK", status="200 OK")
        return resp(env, start_response)


class TestContAugGetMiddleware(unittest.TestCase):
    def setUp(self):
        self.fake_app = FakeApp()
        self.conf = {}
        self.middleware = ContAugGetMiddleware(self.fake_app, self.conf)

    @patch("cont_aug_get.make_subrequest")
    def test_get_without_x_list_object_metadata(self, mock_make_subrequest):
        env = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/v1/AUTH_test/cont1",
        }
        req = Request(env)
        resp = req.get_response(self.middleware)
        self.assertEqual(resp.body, b"OK")

    @patch("cont_aug_get.make_subrequest")
    def test_get_with_x_list_object_metadata(self, mock_make_subrequest):
        env = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/v1/AUTH_test/cont1",
            "HTTP_X_LIST_OBJECT_METADATA": "true",
        }
        mock_make_subrequest.return_value.get_response.return_value = Response(
            body=json.dumps([{"name": "obj1"}, {"name": "obj2"}]).encode("utf-8"),
            status="200 OK",
        )
        req = Request(env)
        resp = req.get_response(self.middleware)
        self.assertEqual(resp.status_int, 200)
        self.assertEqual(resp.content_type, "application/json")
        self.assertIn(b"obj1", resp.body)
        self.assertIn(b"obj2", resp.body)

    @patch("cont_aug_get.make_subrequest")
    def test_get_container_objects_success(self, mock_make_subrequest):
        env = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/v1/AUTH_test/cont1",
        }
        mock_make_subrequest.return_value.get_response.return_value = Response(
            body=json.dumps([{"name": "obj1"}, {"name": "obj2"}]).encode("utf-8"),
            status="200 OK",
        )
        objects = self.middleware.get_container_objects(env, "/v1/AUTH_test/cont1")
        self.assertEqual(
            objects, json.dumps([{"name": "obj1"}, {"name": "obj2"}]).encode("utf-8")
        )

    @patch("cont_aug_get.make_subrequest")
    def test_get_container_objects_failure(self, mock_make_subrequest):
        env = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/v1/AUTH_test/cont1",
        }
        mock_response = Response(body=b"Not Found", status="404 Not Found")
        mock_response.app_iter = MagicMock()
        mock_make_subrequest.return_value.get_response.return_value = mock_response
        objects = self.middleware.get_container_objects(env, "/v1/AUTH_test/cont1")
        self.assertEqual(objects, [])

    @patch("cont_aug_get.make_subrequest")
    def test_get_object_metadata_success(self, mock_make_subrequest):
        env = {
            "REQUEST_METHOD": "HEAD",
            "PATH_INFO": "/v1/AUTH_test/cont1/obj1",
        }
        mock_response = Response(status="200 OK")
        mock_response.headers = {"X-Object-Meta-Test": "value"}
        mock_make_subrequest.return_value.get_response.return_value = mock_response
        metadata = self.middleware.get_object_metadata(env, "/v1/AUTH_test/cont1/obj1")
        self.assertEqual(metadata, {"X-Object-Meta-Test": "value"})

    @patch("cont_aug_get.make_subrequest")
    def test_get_object_metadata_failure(self, mock_make_subrequest):
        env = {
            "REQUEST_METHOD": "HEAD",
            "PATH_INFO": "/v1/AUTH_test/cont1/obj1",
        }
        mock_response = Response(status="404 Not Found")
        mock_response.app_iter = MagicMock()
        mock_make_subrequest.return_value.get_response.return_value = mock_response
        metadata = self.middleware.get_object_metadata(env, "/v1/AUTH_test/cont1/obj1")
        self.assertEqual(metadata, {})

    def test_filter_factory(self):
        global_conf = {"key1": "value1"}
        local_conf = {"key2": "value2"}
        app = FakeApp()
        middleware = filter_factory(global_conf, **local_conf)(app)
        self.assertIsInstance(middleware, ContAugGetMiddleware)
        self.assertEqual(middleware.logger.name, "cont_aug_get")


if __name__ == "__main__":
    unittest.main()
