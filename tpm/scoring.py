"""动态加权评分: 总分 = 能力分×wC + 健康分×wH + 成本分×wP (权重和为 100)。

健康分由实时探针得出: 成功率占 70 分, 延迟占 30 分。
延迟分: 0ms=30 分起按比例衰减, >=3000ms 归零。
"""
from __future__ import annotations


def health_score(success_rate: float, avg_latency_ms: float | None, samples: int) -> float:
    """success_rate: 0.0~1.0; 无样本时给中性分 50。"""
    if samples <= 0 or avg_latency_ms is None:
        return 50.0
    rate_part = success_rate * 70.0
    latency_part = max(0.0, 30.0 * (1.0 - min(avg_latency_ms, 3000.0) / 3000.0))
    return round(rate_part + latency_part, 2)


def weighted_score(capability: float, health: float, cost_tier: float, weights: dict) -> float:
    wc = float(weights.get("capability", 0))
    wh = float(weights.get("health", 0))
    wp = float(weights.get("cost", 0))
    total = wc + wh + wp
    if total <= 0:
        return 0.0
    return round((capability * wc + health * wh + cost_tier * wp) / total, 2)


def rank(members: list[dict], weights: dict) -> list[dict]:
    """members: [{name, capability, health, cost_tier, ...}] → 按总分降序, 附 score 字段。"""
    out = []
    for m in members:
        item = dict(m)
        item["score"] = weighted_score(m["capability"], m["health"], m["cost_tier"], weights)
        out.append(item)
    out.sort(key=lambda x: x["score"], reverse=True)
    return out
