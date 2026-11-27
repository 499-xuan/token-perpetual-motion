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
]


def find_source(source_id: str) -> dict | None:
    for s in RADAR_SOURCES:
        if s["id"] == source_id:
            return dict(s)
    return None
