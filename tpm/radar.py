"""雷达层: 已知免费 / 低价 LLM API 来源注册表。

这里只登记公开已知的来源信息 (注册地址、免费额度说明、OpenAI 兼容 base_url、
推荐模型)。真正的 Key 由用户自己注册后填进 config.json。
capability: 能力分 0-100 (经验值, 可在 config 里覆盖)
cost_tier:  成本分 0-100, 越高越便宜 (免费=100, 低价=60~80, 付费=20~40)
"""
from __future__ import annotations

RADAR_SOURCES = [
    {
        "id": "groq",
        "name": "Groq",
        "signup_url": "https://console.groq.com/keys",
        "base_url": "https://api.groq.com/openai/v1",
        "free_tier": "免费额度大方, 速率限制按天计算, 推理速度极快",
        "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
        "capability": 72,
        "cost_tier": 100,
    },
    {
        "id": "openrouter",
        "name": "OpenRouter (免费模型)",
        "signup_url": "https://openrouter.ai/keys",
        "base_url": "https://openrouter.ai/api/v1",
        "free_tier": "带 :free 后缀的模型免费, 每日有请求数上限",
        "models": ["meta-llama/llama-3.3-70b-instruct:free", "deepseek/deepseek-chat-v3-0324:free"],
        "capability": 75,
        "cost_tier": 100,
    },
    {
        "id": "cloudflare",
        "name": "Cloudflare Workers AI",
        "signup_url": "https://dash.cloudflare.com/?to=/:account/ai",
        "base_url": "https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/v1",
        "free_tier": "每天 10,000 神经元免费额度; base_url 需把 {ACCOUNT_ID} 换成你的账户 ID",
        "models": ["@cf/meta/llama-3.1-8b-instruct"],
        "capability": 55,
        "cost_tier": 100,
    },
    {
        "id": "zhipu",
        "name": "智谱 AI (GLM)",
        "signup_url": "https://open.bigmodel.cn/usercenter/apikeys",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "free_tier": "GLM-4-Flash 免费, 新用户有赠送额度",
        "models": ["glm-4-flash"],
        "capability": 62,
        "cost_tier": 100,
    },
    {
        "id": "siliconflow",
        "name": "硅基流动 SiliconFlow",
        "signup_url": "https://cloud.siliconflow.cn/account/ak",
        "base_url": "https://api.siliconflow.cn/v1",
        "free_tier": "部分小模型免费 (如 Qwen2.5-7B), 注册送额度",
        "models": ["Qwen/Qwen2.5-7B-Instruct", "deepseek-ai/DeepSeek-V3"],
        "capability": 68,
        "cost_tier": 90,
    },
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "signup_url": "https://platform.deepseek.com/api_keys",
        "base_url": "https://api.deepseek.com/v1",
        "free_tier": "无长期免费层, 但价格极低; 新用户曾送额度",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "capability": 88,
        "cost_tier": 70,
    },
    {
        "id": "moonshot",
        "name": "Moonshot (Kimi)",
        "signup_url": "https://platform.moonshot.cn/console/api-keys",
        "base_url": "https://api.moonshot.cn/v1",
        "free_tier": "新用户赠送代金券, 长上下文见长",
        "models": ["moonshot-v1-8k"],
        "capability": 74,
        "cost_tier": 50,
    },
    {
        "id": "volcengine",
        "name": "火山方舟 (豆包)",
        "signup_url": "https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "free_tier": "每个模型有免费推理额度 (需在控制台开通模型并填接入点/模型名)",
        "models": ["doubao-seed-1-6-flash-250615"],
        "capability": 70,
        "cost_tier": 85,
    },
    {
        "id": "gemini",
        "name": "Google Gemini (AI Studio)",
        "signup_url": "https://aistudio.google.com/apikey",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "free_tier": "AI Studio 免费层每日有配额, Flash 模型免费额度较宽松",
        "models": ["gemini-2.0-flash"],
        "capability": 82,
        "cost_tier": 100,
    },
    {
        "id": "github-models",
        "name": "GitHub Models",
        "signup_url": "https://github.com/marketplace/models",
        "base_url": "https://models.inference.ai.azure.com",
        "free_tier": "GitHub 账号即可用, 免费层有速率限制 (用 GitHub PAT 作 Key)",
        "models": ["gpt-4o-mini", "Meta-Llama-3.1-405B-Instruct"],
        "capability": 80,
        "cost_tier": 100,
    },
    {
        "id": "cerebras",
        "name": "Cerebras",
        "signup_url": "https://cloud.cerebras.ai/",
        "base_url": "https://api.cerebras.ai/v1",
        "free_tier": "免费层额度大方, 推理速度极快 (晶圆级芯片), 按分钟/天限速",
        "models": ["llama-3.3-70b", "qwen-3-32b"],
        "capability": 74,
        "cost_tier": 100,
    },
    {
        "id": "sambanova",
        "name": "SambaNova Cloud",
        "signup_url": "https://cloud.sambanova.ai/apis",
        "base_url": "https://api.sambanova.ai/v1",
        "free_tier": "注册送免费额度, 70B 模型速度快",
        "models": ["Meta-Llama-3.3-70B-Instruct", "DeepSeek-V3.1"],
        "capability": 76,
        "cost_tier": 95,
    },
    {
        "id": "nvidia",
        "name": "NVIDIA NIM (build.nvidia.com)",
        "signup_url": "https://build.nvidia.com/explore/discover",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "free_tier": "注册送 1000 次免费调用额度, 可再申请追加",
        "models": ["meta/llama-3.3-70b-instruct", "deepseek-ai/deepseek-r1"],
        "capability": 76,
        "cost_tier": 95,
    },
    {
        "id": "mistral",
        "name": "Mistral AI",
        "signup_url": "https://console.mistral.ai/api-keys",
        "base_url": "https://api.mistral.ai/v1",
        "free_tier": "La Plateforme 有免费实验层 (需绑手机验证), 按月限额",
        "models": ["mistral-small-latest", "codestral-latest"],
        "capability": 72,
        "cost_tier": 90,
    },
    {
        "id": "cohere",
        "name": "Cohere",
        "signup_url": "https://dashboard.cohere.com/api-keys",
        "base_url": "https://api.cohere.ai/compatibility/v1",
        "free_tier": "Trial Key 免费, 每月 1000 次调用 (不可商用)",
        "models": ["command-r-08-2024", "command-r-plus-08-2024"],
        "capability": 66,
        "cost_tier": 90,
    },
    {
        "id": "huggingface",
        "name": "Hugging Face Inference",
        "signup_url": "https://huggingface.co/settings/tokens",
        "base_url": "https://router.huggingface.co/v1",
        "free_tier": "免费账号每月送少量推理额度, 模型种类最全",
        "models": ["meta-llama/Llama-3.3-70B-Instruct", "Qwen/Qwen2.5-72B-Instruct"],
        "capability": 70,
        "cost_tier": 95,
    },
    {
        "id": "together",
        "name": "Together AI",
        "signup_url": "https://api.together.ai/settings/api-keys",
        "base_url": "https://api.together.xyz/v1",
        "free_tier": "新用户送试用额度, 部分模型有免费档",
        "models": ["meta-llama/Llama-3.3-70B-Instruct-Turbo", "deepseek-ai/DeepSeek-V3"],
        "capability": 74,
        "cost_tier": 80,
    },
    {
        "id": "fireworks",
        "name": "Fireworks AI",
        "signup_url": "https://fireworks.ai/account/api-keys",
        "base_url": "https://api.fireworks.ai/inference/v1",
        "free_tier": "新用户送试用额度",
        "models": ["accounts/fireworks/models/llama-v3p3-70b-instruct", "accounts/fireworks/models/deepseek-v3"],
        "capability": 74,
        "cost_tier": 80,
    },
    {
        "id": "qianfan",
        "name": "百度千帆 (文心)",
        "signup_url": "https://console.bce.baidu.com/qianfan/ais/console/apiKey",
        "base_url": "https://qianfan.baidubce.com/v2",
        "free_tier": "ERNIE-Speed / ERNIE-Lite 系列长期免费, 其他模型有试用额度",
        "models": ["ernie-speed-8k", "ernie-lite-8k"],
        "capability": 58,
        "cost_tier": 100,
    },
    {
        "id": "dashscope",
        "name": "阿里云百炼 (通义千问)",
        "signup_url": "https://bailian.console.aliyun.com/?apiKey=1#/api-key",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "free_tier": "新用户每个模型有免费额度 (如 100 万 tokens, 有效期 90 天)",
        "models": ["qwen-turbo", "qwen-flash", "qwen-plus"],
        "capability": 70,
        "cost_tier": 95,
    },
    {
        "id": "hunyuan",
        "name": "腾讯混元",
        "signup_url": "https://console.cloud.tencent.com/hunyuan/api-key",
        "base_url": "https://api.hunyuan.cloud.tencent.com/v1",
        "free_tier": "新用户 100 万 tokens 免费额度包; hunyuan-lite 免费",
        "models": ["hunyuan-lite", "hunyuan-turbo"],
        "capability": 60,
        "cost_tier": 95,
    },
    {
        "id": "spark",
        "name": "讯飞星火",
        "signup_url": "https://console.xfyun.cn/services/bm35",
        "base_url": "https://spark-api-open.xf-yun.com/v1",
        "free_tier": "Spark Lite 长期免费, 其他版本有免费试用包",
        "models": ["lite", "generalv3.5"],
        "capability": 55,
        "cost_tier": 100,
    },
    {
        "id": "minimax",
        "name": "MiniMax",
        "signup_url": "https://platform.minimaxi.com/user-center/basic-information/interface-key",
        "base_url": "https://api.minimax.chat/v1",
        "free_tier": "新用户有试用额度包",
        "models": ["abab6.5s-chat", "MiniMax-Text-01"],
        "capability": 68,
        "cost_tier": 70,
    },
    {
        "id": "stepfun",
        "name": "阶跃星辰 StepFun",
        "signup_url": "https://platform.stepfun.com/interface-key",
        "base_url": "https://api.stepfun.com/v1",
        "free_tier": "新用户送体验额度",
        "models": ["step-1-flash", "step-2-16k"],
        "capability": 68,
        "cost_tier": 80,
    },
]


def find_source(source_id: str) -> dict | None:
    for s in RADAR_SOURCES:
        if s["id"] == source_id:
            return dict(s)
    return None


# ---------------------------------------------------------------------------
# 主动探测: 不再只是静态清单。扫描会实际请求每个来源的 /models 端点:
#   - 无 Key 探测: 200=开放可达, 401/403=服务活着但需要 Key, 其他/超时=不可达
#   - 带 Key 探测 (config.json 里已配置的来源): 200 时解析出真实可用模型清单,
#     并核对注册表里登记的模型是否真的存在。
# 结果写入 radar_state.json, 仪表盘 /api/radar 读取展示。
# ---------------------------------------------------------------------------
import json
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RADAR_STATE_PATH = Path(__file__).resolve().parent.parent / "radar_state.json"

_STATUS_ZH = {
    "open": "开放可达",
    "verified": "已带Key验证",
    "reachable": "可达·需Key",
    "unreachable": "不可达",
}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise RuntimeError("redirect refused")


def probe_models_endpoint(base_url: str, api_key: str = "", timeout: float = 8.0) -> dict:
    """探测一个 OpenAI 兼容端点的 /models。返回状态/延迟/模型清单。"""
    url = base_url.rstrip("/") + "/models"
    req = urllib.request.Request(url, method="GET")
    req.add_header("User-Agent", "token-perpetual-motion/radar")
    req.add_header("Accept", "application/json")
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")
    started = time.time()
    try:
        with urllib.request.build_opener(_NoRedirect()).open(req, timeout=timeout) as resp:
            latency = (time.time() - started) * 1000
            models = []
            try:
                data = json.loads(resp.read().decode("utf-8", "replace"))
                models = [m.get("id", "") for m in data.get("data", []) if m.get("id")]
            except (ValueError, AttributeError):
                pass
            return {"status": "verified" if api_key else "open", "http": resp.status,
                    "latency_ms": round(latency), "models_found": models, "error": ""}
    except urllib.error.HTTPError as e:
        latency = (time.time() - started) * 1000
        if e.code in (401, 403):
            status = "unreachable" if api_key else "reachable"
            error = f"HTTP {e.code} (Key 被拒绝)" if api_key else f"HTTP {e.code} (需要 Key)"
            return {"status": status, "http": e.code, "latency_ms": round(latency),
                    "models_found": [], "error": error}
        if e.code in (404, 405):
            # 服务本身活着, 只是 /models 路径/方法对不上 (如需在 base_url 里填账户 ID)
            return {"status": "reachable", "http": e.code, "latency_ms": round(latency),
                    "models_found": [], "error": f"HTTP {e.code} (服务可达, /models 路径需核对)"}
        return {"status": "unreachable", "http": e.code, "latency_ms": round(latency),
                "models_found": [], "error": f"HTTP {e.code}"}
    except Exception as e:  # 超时 / DNS / 连接失败等
        return {"status": "unreachable", "http": None,
                "latency_ms": round((time.time() - started) * 1000),
                "models_found": [], "error": f"{type(e).__name__}: {e}"[:120]}


def scan_radar(config: dict | None = None, timeout: float = 8.0,
               sources: list | None = None, state_path: Path | None = RADAR_STATE_PATH) -> dict:
    """全量扫描: 注册表逐个无 Key 探测 + 已配置上游带 Key 探测。并发执行。"""
    registry = sources if sources is not None else RADAR_SOURCES
    configured = {}
    if config:
        for up in config.get("upstreams", []):
            key = up.get("api_key") or ""
            if not key and up.get("api_key_env"):
                import os
                key = os.environ.get(up["api_key_env"], "")
            configured[up.get("name", "")] = {"base_url": up.get("base_url", ""), "api_key": key}

    def scan_one(src: dict) -> dict:
        entry = {"id": src["id"], "name": src["name"], "base_url": src["base_url"],
                 "signup_url": src["signup_url"], "free_tier": src["free_tier"],
                 "configured": src["id"] in configured}
        conf = configured.get(src["id"])
        if conf and conf["api_key"]:
            probe = probe_models_endpoint(conf["base_url"] or src["base_url"],
                                          api_key=conf["api_key"], timeout=timeout)
            entry["probe_mode"] = "with_key"
        else:
            probe = probe_models_endpoint(src["base_url"], timeout=timeout)
            entry["probe_mode"] = "no_key"
        entry.update(probe)
        entry["status_zh"] = _STATUS_ZH.get(entry["status"], entry["status"])
        found = set(entry["models_found"])
        entry["registry_models_present"] = [m for m in src.get("models", []) if m in found]
        entry["models_found_count"] = len(found)
        return entry

    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(scan_one, registry))

    counts = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    report = {"scanned_at": time.time(), "timeout_s": timeout,
              "total": len(results), "counts": counts, "results": results}
    if state_path is not None:
        state_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def load_radar_state() -> dict:
    try:
        return json.loads(RADAR_STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"scanned_at": None, "total": len(RADAR_SOURCES), "counts": {}, "results": []}
