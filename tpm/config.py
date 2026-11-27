"""配置加载: 单一 config.json, API Key 支持环境变量引用。"""
from __future__ import annotations

import json
import os
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_DIR / "config.json"
EXAMPLE_PATH = PROJECT_DIR / "config.example.json"
STATE_PATH = PROJECT_DIR / "state.json"

DEFAULT_GROUPS = {
    "free-first": {"label": "免费优先", "weights": {"capability": 40, "health": 60, "cost": 0}},
    "balanced": {"label": "日常智能", "weights": {"capability": 40, "health": 40, "cost": 20}},
    "strongest": {"label": "能力最强", "weights": {"capability": 70, "health": 30, "cost": 0}},
}


def load_config(path: Path | None = None) -> dict:
    """优先读 config.json, 不存在则读 config.example.json, 再不行用内置默认。"""
    candidates = [path] if path else [CONFIG_PATH, EXAMPLE_PATH]
    cfg: dict = {}
    for p in candidates:
        if p and Path(p).exists():
            with open(p, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            break
    cfg.setdefault("gateway", {})
    cfg["gateway"].setdefault("host", "127.0.0.1")
    cfg["gateway"].setdefault("port", 13425)
    cfg["gateway"].setdefault("gateway_key", "")
    cfg.setdefault("health_interval", 45)
    cfg.setdefault("probe_timeout", 15)
    cfg.setdefault("request_timeout", 120)
    cfg.setdefault("quarantine_after", 3)  # 连续失败几次后隔离
    cfg.setdefault("default_group", "balanced")
    groups = dict(DEFAULT_GROUPS)
    groups.update(cfg.get("groups") or {})
    cfg["groups"] = groups
    cfg.setdefault("upstreams", [])
    return cfg


def resolve_api_key(upstream: dict) -> str:
    """api_key_env 优先 (从环境变量读), 否则用 api_key 明文字段。"""
    env_name = upstream.get("api_key_env")
    if env_name:
        val = os.environ.get(env_name, "")
        if val:
            return val
    return upstream.get("api_key", "") or ""
