"""健康探针: 对每个上游发一条极小的 chat completion, 验证可用性并测延迟。"""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request

from .pool import Pool, Upstream


def probe_upstream(up: Upstream, timeout: float = 15) -> tuple[bool, float | None, str]:
    """返回 (是否成功, 延迟ms, 错误信息)。"""
    if not up.models:
        return False, None, "未配置 models"
    url = up.base_url + "/chat/completions"
    payload = {
        "model": up.models[0],
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
        "stream": False,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {up.api_key}",
        },
        method="POST",
    )
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read()
        return True, (time.time() - start) * 1000, ""
    except urllib.error.HTTPError as e:
        return False, (time.time() - start) * 1000, f"HTTP {e.code}"
    except Exception as e:  # 网络错误/超时/DNS 等
        return False, None, f"{type(e).__name__}: {e}"[:200]


def probe_all(pool: Pool, timeout: float = 15) -> dict[str, str]:
    """同步探一轮全部启用的上游, 返回 {name: 新状态}。"""
    results = {}
    for up in list(pool.upstreams.values()):
        if not up.enabled:
            continue
        ok, latency, error = probe_upstream(up, timeout=timeout)
        results[up.name] = pool.apply_probe(up.name, ok, latency, error)
    return results


class HealthLoop(threading.Thread):
    """后台健康检查线程: 每 interval 秒探一轮。"""

    def __init__(self, pool: Pool, interval: float = 45, timeout: float = 15):
        super().__init__(daemon=True, name="tpm-health")
        self.pool = pool
        self.interval = max(5.0, float(interval))
        self.timeout = timeout
        self._stop = threading.Event()

    def run(self):
        while not self._stop.is_set():
            try:
                probe_all(self.pool, timeout=self.timeout)
            except Exception:
                pass  # 单轮失败不退出线程
            self._stop.wait(self.interval)

    def stop(self):
        self._stop.set()
