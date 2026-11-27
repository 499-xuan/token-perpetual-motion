"""Token 永动机 (Token Perpetual Motion) — 本地 LLM API 额度聚合网关。

四层架构:
  1. 雷达层 (radar)      —— 已知免费/低价 LLM API 来源注册表
  2. 观察与服役区 (pool)  —— 候选上游先试岗, 通过探针才进服役池
  3. 本地网关 (gateway)   —— OpenAI 兼容网关, 动态加权评分路由 + 自动故障转移
  4. Token 管家 (butler)  —— 日常运维 CLI
外加仪表盘 (dashboard)  —— 网关内置的单页状态面板。
"""

__version__ = "0.1.0"
