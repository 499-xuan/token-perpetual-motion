"""本地网关: OpenAI 兼容 HTTP 网关。

路由:
  GET  /v1/models            列出服役池模型 + 分组伪模型 group/<分组名>
  POST /v1/chat/completions  按动态加权评分选上游, 失败自动转移, 支持 SSE 流式
  GET  /api/status           仪表盘数据 (JSON)
  GET  /dashboard            仪表盘页面

选组方式: model 写成 "group/<分组名>" 走指定分组 (用上游自己的首选模型);
         或请求头 X-TPM-Group: <分组名>; 都没有则用 config 的 default_group。
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .pool import Pool, Upstream

DASHBOARD_HTML = Path(__file__).resolve().parent / "dashboard.html"


def parse_group(model: str, header_group: str | None, config: dict) -> tuple[str, str | None]:
    """返回 (分组名, 实际模型名或 None)。model='group/xxx' 时实际模型为 None (用上游首选)。"""
    if model.startswith("group/"):
        gname = model[len("group/"):].strip("/")
        if gname in config["groups"]:
            return gname, None
        return config["default_group"], None
    if header_group and header_group in config["groups"]:
        return header_group, model
    return config["default_group"], model


class GatewayApp:
    def __init__(self, pool: Pool, config: dict):
        self.pool = pool
        self.config = config
        self.request_timeout = float(config.get("request_timeout", 120))

    # ---------- 上游调用 ----------
    def _open_upstream(self, up: Upstream, payload: dict):
        url = up.base_url + "/chat/completions"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {up.api_key}",
                "Accept": "text/event-stream" if payload.get("stream") else "application/json",
            },
            method="POST",
        )
        return urllib.request.urlopen(req, timeout=self.request_timeout)

    def chat_completion(self, body: dict, header_group: str | None):
        """返回 (status, headers, body_bytes 或 chunk 生成器, 上游名)。
        流式时 body 为生成器; 出错全部候选失败时抛 UpstreamError。"""
        model_in = str(body.get("model") or "")
        group, model = parse_group(model_in, header_group, self.config)
        candidates = self.pool.candidates_for(group, model)
        if not candidates:
            raise UpstreamError(503, {"error": {"message": "服役池为空或无可用上游, 请先用 butler test 晋升上游",
                                                 "type": "pool_empty"}})
        stream = bool(body.get("stream"))
        last_error: UpstreamError | None = None
        for up in candidates:
            payload = dict(body)
            payload["model"] = model if model else (up.models[0] if up.models else model_in)
            start = time.time()
            try:
                resp = self._open_upstream(up, payload)
            except urllib.error.HTTPError as e:
                err_body = e.read() if hasattr(e, "read") else b""
                latency = (time.time() - start) * 1000
                self.pool.record_request(up.name, False, latency, payload["model"], group, f"HTTP {e.code}")
                last_error = UpstreamError(e.code, _safe_json(err_body) or
                                           {"error": {"message": f"upstream HTTP {e.code}", "type": "upstream_error"}})
                continue
            except Exception as e:
                latency = (time.time() - start) * 1000
                self.pool.record_request(up.name, False, latency, payload["model"], group,
                                         f"{type(e).__name__}: {e}"[:200])
                last_error = UpstreamError(502, {"error": {"message": f"upstream unreachable: {e}",
                                                            "type": "upstream_error"}})
                continue
            latency = (time.time() - start) * 1000
            if stream:
                self.pool.record_request(up.name, True, latency, payload["model"], group)
                return 200, {"Content-Type": "text/event-stream"}, _stream_chunks(resp), up.name
            data = resp.read()
            self.pool.record_request(up.name, True, latency, payload["model"], group)
            return resp.status, {"Content-Type": "application/json"}, data, up.name
        assert last_error is not None
        raise last_error

    def models_list(self) -> dict:
        seen: dict[str, dict] = {}
        for up in self.pool.serving():
            for m in up.models:
                seen.setdefault(m, {"id": m, "object": "model", "owned_by": up.name})
        for gname in self.config["groups"]:
            gid = f"group/{gname}"
            seen[gid] = {"id": gid, "object": "model", "owned_by": "tpm-gateway"}
        return {"object": "list", "data": list(seen.values())}


class UpstreamError(Exception):
    def __init__(self, status: int, body: dict):
        super().__init__(body.get("error", {}).get("message", "upstream error"))
        self.status = status
        self.body = body


def _safe_json(data: bytes):
    try:
        return json.loads(data.decode("utf-8"))
    except Exception:
        return None


def _stream_chunks(resp):
    """把上游 SSE 响应逐块透传。"""
    try:
        while True:
            chunk = resp.read(4096)
            if not chunk:
                break
            yield chunk
    finally:
        resp.close()


def make_handler(app: GatewayApp):
    gateway_key = app.config["gateway"].get("gateway_key", "")

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):  # 静音默认访问日志
            pass

        # ----- 工具 -----
        def _send_json(self, status: int, obj: dict):
            data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _authorized(self) -> bool:
            if not gateway_key:
                return True
            return self.headers.get("Authorization", "") == f"Bearer {gateway_key}"

        # ----- 路由 -----
        def do_GET(self):
            path = self.path.split("?")[0]
            if path == "/v1/models":
                if not self._authorized():
                    return self._send_json(401, {"error": {"message": "invalid gateway key", "type": "auth"}})
                return self._send_json(200, app.models_list())
            if path == "/api/status":
                return self._send_json(200, app.pool.status())
            if path == "/api/radar":
                from .radar import load_radar_state
                return self._send_json(200, load_radar_state())
            if path in ("/dashboard", "/"):
                try:
                    html = DASHBOARD_HTML.read_bytes()
                except OSError:
                    return self._send_json(500, {"error": {"message": "dashboard.html missing"}})
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(html)))
                self.end_headers()
                self.wfile.write(html)
                return
            return self._send_json(404, {"error": {"message": f"not found: {path}", "type": "not_found"}})

        def do_POST(self):
            path = self.path.split("?")[0]
            if path != "/v1/chat/completions":
                return self._send_json(404, {"error": {"message": f"not found: {path}", "type": "not_found"}})
            if not self._authorized():
                return self._send_json(401, {"error": {"message": "invalid gateway key", "type": "auth"}})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            except Exception:
                return self._send_json(400, {"error": {"message": "invalid JSON body", "type": "bad_request"}})
            try:
                status, headers, payload, _up = app.chat_completion(
                    body, self.headers.get("X-TPM-Group"))
            except UpstreamError as e:
                return self._send_json(e.status, e.body)
            if isinstance(payload, (bytes, bytearray)):
                self.send_response(status)
                self.send_header("Content-Type", headers.get("Content-Type", "application/json"))
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            else:  # 流式生成器: 无 Content-Length, 发完关闭连接作为结束信号
                self.send_response(status)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "close")
                self.end_headers()
                self.close_connection = True
                try:
                    for chunk in payload:
                        self.wfile.write(chunk)
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass
            return

    return Handler


def serve(pool: Pool, config: dict) -> ThreadingHTTPServer:
    app = GatewayApp(pool, config)
    host = config["gateway"].get("host", "127.0.0.1")
    port = int(config["gateway"].get("port", 13425))
    server = ThreadingHTTPServer((host, port), make_handler(app))
    server.daemon_threads = True
    return server
