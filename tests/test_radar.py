"""雷达层测试: 注册表完整性 + 主动扫描 (本地假端点)。"""
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from tpm import radar


class TestRegistry(unittest.TestCase):
    def test_unique_ids_and_fields(self):
        ids = [s["id"] for s in radar.RADAR_SOURCES]
        self.assertEqual(len(ids), len(set(ids)), "来源 id 必须唯一")
        self.assertGreaterEqual(len(ids), 24, "雷达来源应不少于 24 个")
        for s in radar.RADAR_SOURCES:
            for field in ("name", "signup_url", "base_url", "free_tier", "models",
                          "capability", "cost_tier"):
                self.assertIn(field, s, f"{s['id']} 缺字段 {field}")
            self.assertTrue(s["base_url"].startswith("https://"), s["id"])


class _ModelsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.endswith("/models"):
            body = json.dumps({"data": [{"id": "m-alpha"}, {"id": "m-beta"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):
        pass


class TestScan(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), _ModelsHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_scan_open_endpoint_discovers_models(self):
        src = {"id": "fake", "name": "Fake", "signup_url": "https://example.com",
               "base_url": f"http://127.0.0.1:{self.port}/v1",
               "free_tier": "test", "models": ["m-alpha", "m-missing"],
               "capability": 50, "cost_tier": 100}
        report = radar.scan_radar(config=None, timeout=3.0, sources=[src], state_path=None)
        r = report["results"][0]
        self.assertEqual(r["status"], "open")
        self.assertEqual(r["models_found_count"], 2)
        self.assertEqual(r["registry_models_present"], ["m-alpha"])
        self.assertEqual(report["counts"].get("open"), 1)

    def test_scan_unreachable(self):
        src = {"id": "dead", "name": "Dead", "signup_url": "https://example.com",
               "base_url": "http://127.0.0.1:1/v1",
               "free_tier": "test", "models": [], "capability": 50, "cost_tier": 100}
        report = radar.scan_radar(config=None, timeout=2.0, sources=[src], state_path=None)
        self.assertEqual(report["results"][0]["status"], "unreachable")


if __name__ == "__main__":
    unittest.main()
