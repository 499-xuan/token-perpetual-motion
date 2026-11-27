# Token 永动机 (Token Perpetual Motion)

> 把各家免费 / 低价 LLM API 额度聚合成一个本地 OpenAI 兼容网关: 自动探活、动态评分选路、坏了自动换家, 让额度像永动机一样转起来。

纯 Python 标准库实现 (Python 3.11+), **零 pip 依赖**, 下载下来就能跑。

## 四层架构

```
┌──────────────────────────────────────────────────────────────┐
│ ④ Token 管家 (butler)      CLI: 加源 / 探活 / 看池 / 看统计     │
├──────────────────────────────────────────────────────────────┤
│ ① 雷达层 (radar)           已知免费/低价来源注册表             │
│      Groq / OpenRouter / Cloudflare / 智谱 / 硅基流动 /       │
│      DeepSeek / Moonshot / 火山方舟 / Gemini / GitHub Models  │
├──────────────────────────────────────────────────────────────┤
│ ② 观察与服役区 (pool)      新上游先进观察区, 探针通过才晋升     │
│      服役池; 连续失败进隔离区 (附原因), 恢复后自动重新晋升     │
├──────────────────────────────────────────────────────────────┤
│ ③ 本地网关 (gateway)       OpenAI 兼容接口, 动态加权评分路由   │
│      总分 = 能力分×wC + 健康分×wH + 成本分×wP, 失败自动转移   │
├──────────────────────────────────────────────────────────────┤
│ 📊 仪表盘 (dashboard)      网关内置单页, 5 秒自动刷新          │
└──────────────────────────────────────────────────────────────┘
```

- **雷达层** (`tpm/radar.py`): 登记 24 个来源的注册地址、免费额度说明、base_url、推荐模型与经验评分。用 `butler sources` 查看清单, 用 `butler scan` **主动探测**: 并发请求每个来源的 `/models` 端点, 区分 开放可达 / 可达·需Key / 已带Key验证 / 不可达, 已配置的来源还会解析出真实可用模型并核对登记模型是否命中; 结果写入 `radar_state.json`, 仪表盘有「雷达扫描」专区 (数据来自 `/api/radar`)。
- **观察与服役区** (`tpm/pool.py` + `tpm/health.py`): 后台每 30~60 秒 (可配) 对每个上游发一条极小的 chat 请求探活, 记录成功率与延迟; 通过进服役池, 连续失败 (默认 3 次) 进隔离区。
- **本地网关** (`tpm/gateway.py`): 对外提供 `GET /v1/models`、`POST /v1/chat/completions` (含 SSE 流式透传)。健康分 = 成功率×70 + 延迟分×30, 实时计算。
- **Token 管家** (`tpm/butler.py`): 日常运维 CLI, 见下方。
- **仪表盘**: 浏览器打开 `http://127.0.0.1:13425/dashboard`, 看分组排名、健康状态、池子计数与最近请求 (数据来自 `/api/status`)。

## 快速开始

```bash
git clone <this-repo> && cd token-perpetual-motion

# 1) 准备配置 (把示例里的 Key 换成你自己的, 或用环境变量)
cp config.example.json config.json
export GROQ_API_KEY=你的key        # config 里写了 api_key_env 的上游从环境变量读
# 或者直接编辑 config.json, 在上游里填 "api_key": "..."

# 2) 先探一轮, 把能用的上游晋升到服役池
python3 butler.py test

# 3) 启动网关 (含后台健康检查)
python3 run.py
# ⚙️  网关:   http://127.0.0.1:13425/v1
# 📊 仪表盘: http://127.0.0.1:13425/dashboard
```

## 让客户端连上网关

任何支持 OpenAI 接口的客户端, 把 base_url 指到 `http://127.0.0.1:13425/v1` 即可, API Key 随便填 (网关没设 `gateway_key` 时不校验; 设了就填那个值)。

**Claude Code:**

```bash
export ANTHROPIC_BASE_URL=http://127.0.0.1:13425   # 注: 需客户端支持 OpenAI 兼容端点时用对应变量
export OPENAI_BASE_URL=http://127.0.0.1:13425/v1
export OPENAI_API_KEY=sk-tpm
```

**OpenCode / 通用 OpenAI 客户端:**

```jsonc
// 配置里的 provider 指向本地网关
{ "baseURL": "http://127.0.0.1:13425/v1", "apiKey": "sk-tpm" }
```

**curl:**

```bash
curl http://127.0.0.1:13425/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model": "group/balanced", "messages": [{"role": "user", "content": "你好"}]}'
```

## 路由分组

请求时用 `model` 选择策略:

| 写法 | 含义 |
|---|---|
| `"model": "group/free-first"` | 免费优先组 (能力:健康:成本 = 40:60:0), 用各上游自己的首选模型 |
| `"model": "group/balanced"` | 日常智能组 (40:40:20), 默认组 |
| `"model": "group/strongest"` | 能力最强组 (70:30:0) |
| `"model": "deepseek-chat"` | 指定模型: 在声明了该模型的服役上游里按默认组评分选路 |
| 请求头 `X-TPM-Group: strongest` | 临时指定分组 (model 仍按模型名选上游) |

每次请求按总分从高到低依次尝试, 某家报错自动转移到下一家, 全部失败才把错误返回给客户端。分组与权重都可以在 `config.json` 的 `groups` 里改, 也可以加自己的组。

## 配置说明 (config.json)

```jsonc
{
  "gateway": { "host": "127.0.0.1", "port": 13425, "gateway_key": "" },
  // host 改 "0.0.0.0" 可供局域网访问 (建议同时设置 gateway_key)
  // gateway_key 非空时, /v1 接口要求 Authorization: Bearer <gateway_key>
  "health_interval": 45,        // 后台探活间隔秒
  "probe_timeout": 15,          // 单次探针超时秒
  "quarantine_after": 3,        // 连续失败几次进隔离区
  "default_group": "balanced",
  "groups": { "balanced": { "label": "日常智能",
              "weights": { "capability": 40, "health": 40, "cost": 20 } } },
  "upstreams": [
    {
      "name": "groq",
      "base_url": "https://api.groq.com/openai/v1",
      "api_key_env": "GROQ_API_KEY",   // 从环境变量读 Key (推荐)
      // "api_key": "sk-...",          // 或直接写明文 (config.json 已被 .gitignore 排除)
      "models": ["llama-3.3-70b-versatile"],
      "capability": 72,                // 能力分 0-100
      "cost_tier": 100,                // 成本分 0-100, 越高越便宜 (免费=100)
      "enabled": true
    }
  ]
}
```

运行时状态 (健康历史、池状态、请求统计) 保存在项目目录的 `state.json` (已 gitignore), 重启网关自动恢复。

## 管家命令

```bash
python3 butler.py sources            # 雷达注册表 + 已配置来源
python3 butler.py scan               # 雷达主动扫描: 探测全部 24 个来源并写入 radar_state.json
python3 butler.py add --from groq --name my-groq --api-key-env GROQ_API_KEY
python3 butler.py add --name my-api --base-url https://example.com/v1 \
                      --api-key sk-xxx --models model-1,model-2 \
                      --capability 70 --cost-tier 80
python3 butler.py test               # 探一轮全部上游, 晋升/隔离并写入 state.json
python3 butler.py status             # 池状态 + 各分组排名
python3 butler.py stats              # 最近请求统计
# 等价写法: python3 -m tpm.butler <命令>
```

## 测试

```bash
python3 -m unittest discover -s tests -v
```

冒烟测试会起一个假上游和真网关, 覆盖: 探针晋升、模型列表、普通/流式对话、分组路由、故障转移、状态接口与仪表盘、连续失败隔离、评分函数。

## 目录结构

```
token-perpetual-motion/
├── run.py                  # 入口: 网关 + 健康检查
├── butler.py               # 管家 CLI 快捷入口
├── config.example.json     # 示例配置 (复制为 config.json 使用)
├── tpm/
│   ├── radar.py            # ① 雷达层: 来源注册表
│   ├── pool.py             # ② 观察与服役区: 池状态/统计/持久化
│   ├── health.py           #    探针与后台健康循环
│   ├── scoring.py          #    动态加权评分
│   ├── gateway.py          # ③ 本地网关: OpenAI 兼容 HTTP 服务
│   ├── butler.py           # ④ Token 管家 CLI
│   └── dashboard.html      # 📊 仪表盘单页
└── tests/test_smoke.py     # 冒烟测试 (假上游)
```

## License

MIT
