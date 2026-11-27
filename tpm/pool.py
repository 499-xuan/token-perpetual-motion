"""观察与服役区: 上游池状态管理 (线程安全, JSON 状态文件持久化)。

每个上游处于三种状态之一:
  observing   观察区 —— 刚加入/待验证, 不接流量
  serving     服役池 —— 探针通过, 正式接流量
  quarantined 隔离区 —— 连续失败达到阈值, 附隔离原因; 探针恢复后可重新晋升
"""
from __future__ import annotations

import json
import threading
import time
from collections import deque
from pathlib import Path

from . import scoring
from .config import STATE_PATH, resolve_api_key

OBSERVING = "observing"
SERVING = "serving"
QUARANTINED = "quarantined"
HISTORY_LEN = 50          # 每个上游保留的探针历史条数
RECENT_REQUESTS = 100     # 最近请求统计保留条数


class Upstream:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.name = cfg["name"]
        self.base_url = cfg["base_url"].rstrip("/")
        self.models = list(cfg.get("models") or [])
        self.capability = float(cfg.get("capability", 50))
        self.cost_tier = float(cfg.get("cost_tier", 50))
        self.enabled = bool(cfg.get("enabled", True))
        self.state = OBSERVING
        self.quarantine_reason = ""
        self.history: deque = deque(maxlen=HISTORY_LEN)  # {ts, ok, latency_ms, error}
        self.consecutive_failures = 0
        self.requests_total = 0
        self.requests_ok = 0
        self.last_error = ""

    @property
    def api_key(self) -> str:
        return resolve_api_key(self.cfg)

    def record_probe(self, ok: bool, latency_ms: float | None, error: str = ""):
        self.history.append(
            {"ts": time.time(), "ok": ok, "latency_ms": latency_ms, "error": error}
        )
        if ok:
            self.consecutive_failures = 0
        else:
            self.consecutive_failures += 1
            self.last_error = error

    def record_request(self, ok: bool, error: str = ""):
        self.requests_total += 1
        if ok:
            self.requests_ok += 1
        else:
            self.last_error = error

    def success_rate(self) -> float:
        if not self.history:
            return 1.0
        ok = sum(1 for h in self.history if h["ok"])
        return ok / len(self.history)

    def avg_latency_ms(self) -> float | None:
        lats = [h["latency_ms"] for h in self.history if h["ok"] and h["latency_ms"] is not None]
        return sum(lats) / len(lats) if lats else None

    def health(self) -> float:
        return scoring.health_score(self.success_rate(), self.avg_latency_ms(), len(self.history))

    def to_status(self) -> dict:
        return {
            "name": self.name,
            "base_url": self.base_url,
            "models": self.models,
            "state": self.state,
            "enabled": self.enabled,
            "capability": self.capability,
            "cost_tier": self.cost_tier,
            "health": self.health(),
            "success_rate": round(self.success_rate(), 3),
            "avg_latency_ms": (round(self.avg_latency_ms(), 1) if self.avg_latency_ms() is not None else None),
            "consecutive_failures": self.consecutive_failures,
            "quarantine_reason": self.quarantine_reason,
            "last_error": self.last_error,
            "requests_total": self.requests_total,
            "requests_ok": self.requests_ok,
            "probes": len(self.history),
        }


class Pool:
    """全部上游 + 分组排名 + 请求统计, 一把大锁保平安。"""

    def __init__(self, config: dict, state_path: Path | None = None):
        self.config = config
        self.state_path = Path(state_path) if state_path else STATE_PATH
        self.lock = threading.RLock()
        self.upstreams: dict[str, Upstream] = {}
        for ucfg in config.get("upstreams", []):
            if ucfg.get("name"):
                self.upstreams[ucfg["name"]] = Upstream(ucfg)
        self.recent_requests: deque = deque(maxlen=RECENT_REQUESTS)
        self.started_at = time.time()
        self._load_state()

    # ---------- 池状态流转 ----------
    def apply_probe(self, name: str, ok: bool, latency_ms: float | None, error: str = ""):
        """探针结果驱动晋升/隔离。返回新状态。"""
        with self.lock:
            up = self.upstreams.get(name)
            if up is None:
                return ""
            up.record_probe(ok, latency_ms, error)
            threshold = int(self.config.get("quarantine_after", 3))
            if ok:
                if up.state in (OBSERVING, QUARANTINED):
                    up.state = SERVING
                    up.quarantine_reason = ""
            else:
                if up.state == SERVING and up.consecutive_failures >= threshold:
                    up.state = QUARANTINED
                    up.quarantine_reason = f"连续失败 {up.consecutive_failures} 次: {error}"[:200]
                elif up.state == OBSERVING and up.consecutive_failures >= threshold:
                    up.state = QUARANTINED
                    up.quarantine_reason = f"观察期连续失败 {up.consecutive_failures} 次: {error}"[:200]
            self._save_state_locked()
            return up.state

    def record_request(self, name: str, ok: bool, latency_ms: float | None,
                       model: str = "", group: str = "", error: str = ""):
        with self.lock:
            up = self.upstreams.get(name)
            if up is not None:
                up.record_request(ok, error)
            self.recent_requests.append({
                "ts": time.time(), "upstream": name, "model": model,
                "group": group, "ok": ok, "latency_ms": latency_ms, "error": error,
            })

    # ---------- 查询 ----------
    def serving(self) -> list[Upstream]:
        with self.lock:
            return [u for u in self.upstreams.values() if u.enabled and u.state == SERVING]

    def ranked(self, group: str) -> list[dict]:
        """某分组下服役池的排名 (含总分)。"""
        gcfg = self.config["groups"].get(group) or self.config["groups"][self.config["default_group"]]
        members = [{
            "name": u.name, "capability": u.capability, "health": u.health(),
            "cost_tier": u.cost_tier, "models": u.models, "base_url": u.base_url,
        } for u in self.serving()]
        return scoring.rank(members, gcfg["weights"])

    def candidates_for(self, group: str, model: str | None) -> list[Upstream]:
        """按分组排名给出候选上游 (故障转移顺序)。指定 model 时优先选声明了该模型的上游。"""
        ranked = self.ranked(group)
        by_name = {u.name: u for u in self.serving()}
        ordered = [by_name[r["name"]] for r in ranked]
        if model:
            with_model = [u for u in ordered if model in u.models]
            if with_model:
                return with_model
        return ordered

    def status(self) -> dict:
        with self.lock:
            ups = [u.to_status() for u in self.upstreams.values()]
            counts = {OBSERVING: 0, SERVING: 0, QUARANTINED: 0}
            for u in ups:
                counts[u["state"]] = counts.get(u["state"], 0) + 1
            groups = {}
            for gname, gcfg in self.config["groups"].items():
                groups[gname] = {
                    "label": gcfg.get("label", gname),
                    "weights": gcfg["weights"],
                    "members": self.ranked(gname),
                }
            return {
                "started_at": self.started_at,
                "uptime_s": round(time.time() - self.started_at, 1),
                "default_group": self.config["default_group"],
                "counts": counts,
                "upstreams": ups,
                "groups": groups,
                "recent_requests": list(self.recent_requests)[-20:],
            }

    # ---------- 持久化 (只存可恢复的状态摘要, 不存 Key) ----------
    def _save_state_locked(self):
        data = {
            "saved_at": time.time(),
            "upstreams": {
                name: {
                    "state": u.state,
                    "quarantine_reason": u.quarantine_reason,
                    "history": list(u.history),
                    "requests_total": u.requests_total,
                    "requests_ok": u.requests_ok,
                } for name, u in self.upstreams.items()
            },
            "recent_requests": list(self.recent_requests),
        }
        try:
            tmp = self.state_path.with_suffix(".json.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            tmp.replace(self.state_path)
        except OSError:
            pass  # 状态文件写失败不影响网关运行

    def save_state(self):
        with self.lock:
            self._save_state_locked()

    def _load_state(self):
        try:
            if not self.state_path.exists():
                return
            with open(self.state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for name, saved in (data.get("upstreams") or {}).items():
                up = self.upstreams.get(name)
                if up is None:
                    continue
                up.state = saved.get("state", OBSERVING)
                up.quarantine_reason = saved.get("quarantine_reason", "")
                up.requests_total = int(saved.get("requests_total", 0))
                up.requests_ok = int(saved.get("requests_ok", 0))
                for h in saved.get("history", []):
                    up.history.append(h)
                    if not h.get("ok"):
                        up.consecutive_failures += 1
                    else:
                        up.consecutive_failures = 0
            for r in data.get("recent_requests", []):
                self.recent_requests.append(r)
        except (OSError, ValueError):
            pass
