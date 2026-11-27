"""冒烟测试: 假上游 + 真网关, 全程只用标准库。

运行: python3 -m unittest discover -s tests -v
"""
import json
import sys
import threading
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tpm import scoring
from tpm.gateway import serve
from tpm.health import probe_all
from tpm.pool import Pool

# ---------------- 假上游 ----------------

class FakeUpstreamHandler(BaseHTTPRequestHandler):
    fail_next = 0  # 类变量: 让接下来的 N 次请求返回 500 (测故障转移)

    def log_message(self, *a):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length) or b"{}")
        if type(self).fail_next > 0:
            type(self).fail_next -= 1
            data = json.dumps({"error": {"message": "boom"}}).encode()
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if body.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for i, txt in enumerate(["Hello", " world"]):
                chunk = {"id": "x", "object": "chat.completion.chunk",
                         "choices": [{"index": 0, "delta": {"content": txt}}]}
                self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
                self.wfile.flush()
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
            return
        data = json.dumps({
            "id": "x", "object": "chat.completion",
            "model": body.get("model"),
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "pong"},
                         "finish_reason": "stop"}],
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def start_fake_upstream():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), FakeUpstreamHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/v1"


def make_config(url_a, url_b):
    return {
        "gateway": {"host": "127.0.0.1", "port": 0, "gateway_key": ""},
        "health_interval": 30, "probe_timeout": 5, "request_timeout": 10,
        "quarantine_after": 3, "default_group": "balanced",
        "groups": {
            "free-first": {"label": "免费优先", "weights": {"capability": 40, "health": 60, "cost": 0}},
            "balanced": {"label": "日常智能", "weights": {"capability": 40, "health": 40, "cost": 20}},
            "strongest": {"label": "能力最强", "weights": {"capability": 70, "health": 30, "cost": 0}},
        },
        "upstreams": [
            {"name": "fake-a", "base_url": url_a, "api_key": "k1",
             "models": ["model-a"], "capability": 60, "cost_tier": 100, "enabled": True},
            {"name": "fake-b", "base_url": url_b, "api_key": "k2",
             "models": ["model-b"], "capability": 90, "cost_tier": 40, "enabled": True},
        ],
    }


def http_json(url, payload=None, headers=None):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST" if payload is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, json.loads(resp.read().decode())


class ScoringTest(unittest.TestCase):
    def test_weighted_score(self):
        w = {"capability": 40, "health": 40, "cost": 20}
        self.assertAlmostEqual(scoring.weighted_score(100, 100, 100, w), 100.0)
        self.assertAlmostEqual(scoring.weighted_score(0, 0, 0, w), 0.0)
        # free-first 不看成本: 成本差不影响
        wf = {"capability": 40, "health": 60, "cost": 0}
        self.assertEqual(scoring.weighted_score(50, 50, 0, wf),
                         scoring.weighted_score(50, 50, 100, wf))

    def test_health_score_no_samples(self):
        self.assertEqual(scoring.health_score(1.0, None, 0), 50.0)


class GatewaySmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake_a, url_a = start_fake_upstream()
        cls.fake_b, url_b = start_fake_upstream()
        cls.config = make_config(url_a, url_b)
        import tempfile, os
        cls.tmp = tempfile.mkdtemp()
        cls.pool = Pool(cls.config, state_path=Path(cls.tmp) / "state.json")
        cls.gateway = serve(cls.pool, cls.config)
        cls.port = cls.gateway.server_address[1]
        threading.Thread(target=cls.gateway.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.gateway.shutdown()
        cls.fake_a.shutdown()
        cls.fake_b.shutdown()

    def test_1_promotion_via_probe(self):
        results = probe_all(self.pool, timeout=5)
        self.assertEqual(results["fake-a"], "serving")
        self.assertEqual(results["fake-b"], "serving")

    def test_2_models(self):
        status, data = http_json(self.base + "/v1/models")
        self.assertEqual(status, 200)
        ids = {m["id"] for m in data["data"]}
        self.assertIn("model-a", ids)
        self.assertIn("group/balanced", ids)

    def test_3_chat_completion(self):
        status, data = http_json(self.base + "/v1/chat/completions",
                                 {"model": "model-a",
                                  "messages": [{"role": "user", "content": "hi"}]})
        self.assertEqual(status, 200)
        self.assertEqual(data["choices"][0]["message"]["content"], "pong")

    def test_4_group_routing(self):
        status, data = http_json(self.base + "/v1/chat/completions",
                                 {"model": "group/strongest",
                                  "messages": [{"role": "user", "content": "hi"}]})
        self.assertEqual(status, 200)
        # strongest 权重偏能力, fake-b 能力 90 应排第一并被选中 → 模型应是 model-b
        self.assertEqual(data["model"], "model-b")

    def test_5_streaming(self):
        req = urllib.request.Request(
            self.base + "/v1/chat/completions",
            data=json.dumps({"model": "model-a", "stream": True,
                             "messages": [{"role": "user", "content": "hi"}]}).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode()
        self.assertIn("Hello", body)
        self.assertIn("[DONE]", body)

    def test_6_failover(self):
        FakeUpstreamHandler.fail_next = 1  # 下一个请求 500, 网关应转移到另一个上游
        try:
            status, data = http_json(self.base + "/v1/chat/completions",
                                     {"model": "group/balanced",
                                      "messages": [{"role": "user", "content": "hi"}]})
            self.assertEqual(status, 200)
            self.assertEqual(data["choices"][0]["message"]["content"], "pong")
        finally:
            FakeUpstreamHandler.fail_next = 0

    def test_7_status_and_dashboard(self):
        status, data = http_json(self.base + "/api/status")
        self.assertEqual(status, 200)
        self.assertEqual(data["counts"]["serving"], 2)
        self.assertIn("balanced", data["groups"])
        req = urllib.request.Request(self.base + "/dashboard")
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode()
        self.assertIn("Token 永动机", html)

    def test_8_quarantine_after_failures(self):
        # 坏上游连续失败 3 次 → 隔离
        bad_cfg = dict(self.config)
        bad_cfg["upstreams"] = [{"name": "bad", "base_url": "http://127.0.0.1:1/v1",
                                 "api_key": "x", "models": ["m"], "capability": 10,
                                 "cost_tier": 10, "enabled": True}]
        import tempfile
        pool = Pool(bad_cfg, state_path=Path(tempfile.mkdtemp()) / "s.json")
        for _ in range(3):
            probe_all(pool, timeout=2)
        self.assertEqual(pool.upstreams["bad"].state, "quarantined")
        self.assertTrue(pool.upstreams["bad"].quarantine_reason)


if __name__ == "__main__":
    unittest.main()
