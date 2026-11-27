"""Token 管家 CLI: 日常运维。

用法:
  python3 -m tpm.butler sources                 雷达注册表 + 已配置来源
  python3 -m tpm.butler add --name x --base-url URL --api-key KEY --models a,b [--from groq]
  python3 -m tpm.butler test                    探一轮全部上游, 晋升/隔离, 结果写入 state.json
  python3 -m tpm.butler status                  池状态 + 各分组排名 (读 state.json)
  python3 -m tpm.butler stats                   最近请求统计
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from . import radar
from .config import CONFIG_PATH, load_config
from .health import probe_all
from .pool import Pool

STATE_ZH = {"serving": "服役中", "observing": "观察区", "quarantined": "隔离区"}


def _pool() -> Pool:
    return Pool(load_config())


def cmd_sources(_args):
    cfg = load_config()
    configured = {u["name"] for u in cfg.get("upstreams", [])}
    print("== 雷达注册表 (已知免费/低价来源) ==")
    for s in radar.RADAR_SOURCES:
        mark = "✓已配置" if s["id"] in configured else " 未配置"
        print(f"[{mark}] {s['id']:<14} {s['name']}")
        print(f"         注册: {s['signup_url']}")
        print(f"         额度: {s['free_tier']}")
        print(f"         base_url: {s['base_url']}  模型: {', '.join(s['models'])}")
    print("\n== config.json 已配置上游 ==")
    for u in cfg.get("upstreams", []):
        key_src = f"env:{u['api_key_env']}" if u.get("api_key_env") else ("已填Key" if u.get("api_key") else "无Key")
        print(f"- {u['name']:<14} {u['base_url']}  [{key_src}]  模型: {', '.join(u.get('models', []))}")


def cmd_add(args):
    path = CONFIG_PATH
    cfg = {}
    if path.exists():
        cfg = json.loads(path.read_text(encoding="utf-8"))
    cfg.setdefault("upstreams", [])
    entry = {"name": args.name, "base_url": args.base_url.rstrip("/"),
             "models": [m.strip() for m in (args.models or "").split(",") if m.strip()]}
    if args.from_radar:
        src = radar.find_source(args.from_radar)
        if not src:
            print(f"雷达里没有 '{args.from_radar}', 先看 butler sources")
            return 1
        entry["base_url"] = entry["base_url"] or src["base_url"]
        entry["models"] = entry["models"] or src["models"]
        entry.setdefault("capability", src["capability"])
        entry.setdefault("cost_tier", src["cost_tier"])
    if not entry["base_url"] or not entry["models"]:
        print("必须提供 --base-url 和 --models (或用 --from 从雷达带出)")
        return 1
    if args.api_key:
        entry["api_key"] = args.api_key
    if args.api_key_env:
        entry["api_key_env"] = args.api_key_env
    entry.setdefault("capability", args.capability)
    entry.setdefault("cost_tier", args.cost_tier)
    entry["enabled"] = True
    cfg["upstreams"] = [u for u in cfg["upstreams"] if u.get("name") != args.name] + [entry]
    path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写入 {path}: {args.name} ({entry['base_url']})")
    print("下一步: python3 -m tpm.butler test   # 探活并晋升到服役池")
    return 0


def cmd_test(_args):
    cfg = load_config()
    pool = Pool(cfg)
    print(f"开始探针 (超时 {cfg.get('probe_timeout', 15)}s/个)...")
    results = probe_all(pool, timeout=float(cfg.get("probe_timeout", 15)))
    for name, state in results.items():
        up = pool.upstreams[name]
        lat = up.avg_latency_ms()
        print(f"- {name:<14} → {STATE_ZH.get(state, state)}"
              f"  健康分 {up.health()}  延迟 {'%.0fms' % lat if lat else '-'}"
              f"{('  原因: ' + up.quarantine_reason) if up.quarantine_reason else ''}")
    pool.save_state()
    print("结果已写入 state.json")
    return 0


def cmd_status(_args):
    pool = _pool()
    st = pool.status()
    print(f"池概览: 服役 {st['counts'].get('serving', 0)} · 观察 {st['counts'].get('observing', 0)}"
          f" · 隔离 {st['counts'].get('quarantined', 0)}")
    for u in st["upstreams"]:
        print(f"- {u['name']:<14} {STATE_ZH.get(u['state'], u['state'])} 健康 {u['health']}"
              f" 成功率 {u['success_rate']:.0%} 延迟 {u['avg_latency_ms']}ms"
              f" 请求 {u['requests_ok']}/{u['requests_total']}"
              f"{('  隔离原因: ' + u['quarantine_reason']) if u['quarantine_reason'] else ''}")
    for gname, g in st["groups"].items():
        w = g["weights"]
        print(f"\n分组 {gname} ({g['label']}, 权重 能力{w['capability']}/健康{w['health']}/成本{w['cost']}):")
        if not g["members"]:
            print("  (服役池为空)")
        for i, m in enumerate(g["members"], 1):
            print(f"  {i}. {m['name']:<14} 总分 {m['score']} (能力 {m['capability']} / 健康 {m['health']} / 成本 {m['cost_tier']})")
    return 0


def cmd_stats(_args):
    pool = _pool()
    st = pool.status()
    rows = st["recent_requests"]
    if not rows:
        print("暂无请求记录 (网关还没接到请求, 或状态文件为空)")
        return 0
    for r in rows[-20:]:
        ts = time.strftime("%H:%M:%S", time.localtime(r["ts"]))
        ok = "成功" if r["ok"] else f"失败 {r.get('error', '')}"
        lat = f"{r['latency_ms']:.0f}ms" if r.get("latency_ms") else "-"
        print(f"{ts}  {r['upstream']:<14} {r['model']:<28} [{r['group']}] {ok} {lat}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="butler", description="Token 管家 — Token 永动机运维 CLI")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sources", help="雷达注册表 + 已配置来源")
    pa = sub.add_parser("add", help="添加/更新一个上游到 config.json")
    pa.add_argument("--name", required=True)
    pa.add_argument("--base-url", default="")
    pa.add_argument("--api-key", default="")
    pa.add_argument("--api-key-env", default="")
    pa.add_argument("--models", default="")
    pa.add_argument("--from", dest="from_radar", default="", help="从雷达预设带出 base_url/models/评分")
    pa.add_argument("--capability", type=float, default=50)
    pa.add_argument("--cost-tier", type=float, default=50)
    sub.add_parser("test", help="探一轮全部上游并晋升/隔离")
    sub.add_parser("status", help="池状态与分组排名")
    sub.add_parser("stats", help="最近请求统计")
    args = p.parse_args(argv)
    return {"sources": cmd_sources, "add": cmd_add, "test": cmd_test,
            "status": cmd_status, "stats": cmd_stats}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
