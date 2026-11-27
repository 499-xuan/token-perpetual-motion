#!/usr/bin/env python3
"""Token 永动机入口: 启动本地网关 + 后台健康检查。

用法: python3 run.py [--config path]
仪表盘: http://127.0.0.1:13425/dashboard
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tpm.config import load_config
from tpm.gateway import serve
from tpm.health import HealthLoop
from tpm.pool import Pool


def main():
    ap = argparse.ArgumentParser(description="Token 永动机 — 本地 LLM 网关")
    ap.add_argument("--config", default=None, help="配置文件路径 (默认 config.json, 缺失时用 config.example.json)")
    args = ap.parse_args()

    config = load_config(Path(args.config) if args.config else None)
    pool = Pool(config)
    health = HealthLoop(pool, interval=float(config.get("health_interval", 45)),
                        timeout=float(config.get("probe_timeout", 15)))
    health.start()
    server = serve(pool, config)
    host, port = server.server_address[0], server.server_address[1]
    print(f"⚙️  Token 永动机网关已启动: http://{host}:{port}/v1")
    print(f"📊 仪表盘: http://{host}:{port}/dashboard")
    print(f"🧭 默认分组: {config['default_group']} · 上游 {len(pool.upstreams)} 个 (先观察, 探针通过后自动晋升服役池)")
    print("Ctrl+C 退出")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n正在退出...")
    finally:
        health.stop()
        pool.save_state()
        server.shutdown()


if __name__ == "__main__":
    main()
