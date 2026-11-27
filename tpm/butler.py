"""Token 管家 CLI: 日常运维。

用法:
  python3 -m tpm.butler sources                 雷达注册表 + 已配置来源
  python3 -m tpm.butler scan                    雷达主动扫描: 逐个探测全部来源的 /models 端点
  python3 -m tpm.butler claim                   领取清单: 未领来源 + Key 地址 + 配置命令
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


def cmd_scan(args):
    cfg = load_config()
    timeout = float(getattr(args, "timeout", 8.0) or 8.0)
    print(f"雷达扫描中: {len(radar.RADAR_SOURCES)} 个来源并发探测 (超时 {timeout:.0f}s/个)...")
    report = radar.scan_radar(cfg, timeout=timeout)
    for r in report["results"]:
        extra = ""
        if r["models_found_count"]:
            extra = f"  发现模型 {r['models_found_count']} 个"
            if r["registry_models_present"]:
                extra += f", 登记模型命中: {', '.join(r['registry_models_present'])}"
        if r["error"]:
            extra += f"  ({r['error']})"
        print(f"- {r['id']:<14} {r['status_zh']:<10} 延迟 {r['latency_ms']}ms"
              f"{'  ✓已配置' if r['configured'] else ''}{extra}")
    c = report["counts"]
    print(f"\n汇总: 共 {report['total']} 个 · 开放可达 {c.get('open', 0)} · 已带Key验证 {c.get('verified', 0)}"
          f" · 可达需Key {c.get('reachable', 0)} · 不可达 {c.get('unreachable', 0)}")
    print("结果已写入 radar_state.json (仪表盘 /api/radar 可看)")
    return 0


def cmd_claim(_args):
    cfg = load_config()
    configured = {u["name"] for u in cfg.get("upstreams", [])}
    todo = [s for s in radar.RADAR_SOURCES if s["id"] not in configured]
    print(f"== 领取清单: 已配置 {len(radar.RADAR_SOURCES) - len(todo)} / {len(radar.RADAR_SOURCES)} ==")
    for s in radar.RADAR_SOURCES:
        if s["id"] in configured:
            print(f"✓ {s['id']:<14} {s['name']} — 已领取并配置")
    for s in todo:
        print(f"○ {s['id']:<14} {s['name']}")
        print(f"    领 Key: {s['signup_url']}")
        print(f"    额度: {s['free_tier']}")
        print(f"    领到后一条命令搞定 (自动验证+发现模型): "
              f"python3 butler.py add --from {s['id']} --name {s['id']} --api-key 你的Key")
    return 0


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
    if args.api_key:
        entry["api_key"] = args.api_key
    if args.api_key_env:
        entry["api_key_env"] = args.api_key_env
    _has_key = bool(args.api_key or args.api_key_env)
    if not entry["base_url"] or (not entry["models"] and not _has_key):
        print("必须提供 --base-url 和 --models (或用 --from 从雷达带出; 有 Key 时可省略 --models, 将自动发现)")
        return 1
    entry.setdefault("capability", args.capability)
    entry.setdefault("cost_tier", args.cost_tier)
    entry["enabled"] = True

    # 有 Key 就当场验证 + 自动发现真实模型, 不用再手动对清单
    key = entry.get("api_key") or ""
    if not key and entry.get("api_key_env"):
        import os
        key = os.environ.get(entry["api_key_env"], "")
    if key:
        probe = radar.probe_models_endpoint(entry["base_url"], api_key=key,
                                            timeout=float(load_config().get("probe_timeout", 15)))
        if probe["status"] == "verified":
            found = probe["models_found"]
            print(f"Key 验证通过 ✓ 该账号实际可用模型 {len(found)} 个")
            if not args.models and not args.from_radar:
                if len(found) > 30:
                    free = [m for m in found if "free" in m.lower()]
                    entry["models"] = free[:30] if free else found[:30]
                    print(f"已自动写入 {len(entry['models'])} 个模型 (优先免费档; 完整清单 {len(found)} 个)")
                elif found:
                    entry["models"] = found
                    print(f"已自动写入模型: {', '.join(found)}")
            elif args.from_radar and found:
                hit = [m for m in entry["models"] if m in set(found)]
                print(f"雷达登记模型命中: {', '.join(hit) if hit else '无 (可改用发现到的模型)'}")
        else:
            print(f"⚠ Key 验证未通过: {probe['error']} (配置已保存, 修好 Key 后跑 butler test)")
    if not entry["models"]:
        print("没有可用模型清单, 先补 --models 或换个有效 Key 再 add")
        return 1

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
    ps = sub.add_parser("scan", help="雷达主动扫描全部来源")
    ps.add_argument("--timeout", type=float, default=8.0, help="每个来源探测超时秒数")
    sub.add_parser("claim", help="领取清单: 还没领的 Key + 领取地址 + 一条命令配置")
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
    return {"sources": cmd_sources, "scan": cmd_scan, "claim": cmd_claim, "add": cmd_add,
            "test": cmd_test, "status": cmd_status, "stats": cmd_stats}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
