# 扫描报告 A · LLM 调用层 / 错误路由 / 结构化输出

> 扫描员：**A**（LLM 调用层 / 错误路由 / 结构化输出）
> 日期：**2026-09-30**｜对应议题：**D-11 / D-12 / D-13 / D-14**
> 纪律：每条含 方案名 / 是什么 / 为什么可用 / 接入成本 / 风险 / 是否适合本项目（三值）/ URL + 来源分级；**≥2 条反转性发现**；查不到写 ❓，**不编造 API/版本号/价格**。
> **本件只出证据与表，不替 HT 拍板。**

---

## 0. 方法与证据可复现（先看这个）

**真的上网查了**：所有事实来自 WebSearch / WebFetch + 本机 curl/urllib 实测。来源分级：`[官方文档] > [官方仓库] > [活跃仓库] > [社区帖]`。

**本目录下可复现的实测件**：

| 文件 | 作用 | 怎么跑 |
|---|---|---|
| `_pypi_probe_A.py` → `_pypi_A_out.txt` | 批量拉 PyPI JSON：license / license_expression / 运行期依赖数 / 版本 | `python _pypi_probe_A.py` |
| `_pypi_dates_A.py` | 补测首次/最新发版日期、包名核对 | 同上 |
| `_pypi_size_A.py` | 实测 wheel/sdist 体积 | 同上 |

**License 实测口径**：优先读 PyPI JSON 的 `info.license_expression`（新式 SPDX），其次 `info.license` 文本、`classifiers` 里的 `License ::`，再与官方仓库核对。**注意**：本次 `urls[].upload_time` 字段在当前 PyPI JSON 返回中为空，故发版时间改用 `releases[ver][].upload_time_iso_8601`（脚本已修正）。

**已知环境坑复核**：本机 Python 3.14.3 可用；`curl` 在 Git Bash 下可用（本次成功下载 DeepSeek 官方 tokenizer zip，1.9 MB）。

---

## 1. DeepSeek API 事实核实（③，带 URL）

> 全部来自 **官方文档**（最高级）。**结论先行：网上流传/课程里常见的 `deepseek-chat` / `deepseek-reasoner` 已下线，当前白名单是 `deepseek-flash` / `deepseek-v4-pro`。**

| # | 事实 | 值（原样） | 来源 | 分级 |
|---|---|---|---|---|
| F1 | OpenAI 兼容 base_url | `https://api.deepseek.com` | [官方文档](https://api-docs.deepseek.com/) | 官方文档 |
| F2 | Anthropic 兼容 base_url | `https://api.deepseek.com/anthropic` | [官方文档](https://api-docs.deepseek.com/) | 官方文档 |
| F3 | **当前模型 id 白名单** | `deepseek-flash`（=DeepSeek-V4.1-Flash）、`deepseek-v4-pro`（=DeepSeek-V4-Pro-0813） | [Models & Pricing](https://api-docs.deepseek.com/quick_start/pricing) | 官方文档 |
| F4 | **旧名 `deepseek-v4-flash` / `deepseek-v4-flash-vision-exp`** | 仍接受，但对应模型已**退休**，请求被路由到 V4.1-Flash 并按 Flash 价计费（**向后兼容别名，非独立模型**） | 同上（脚注 1） | 官方文档 |
| F5 | **`deepseek-chat` / `deepseek-reasoner`** | **2026-07-24 已停用**（2026-04-24 公告给 3 个月过渡期） | [Change Log](https://api-docs.deepseek.com/updates)（Date: 2026-04-24） | 官方文档 |
| F6 | 是否有 v4 系列 | 有：V4.1-Flash（2026-09-10 发布）、V4-Pro（2026-08-13 GA）、V4-Flash（2026-07-31）、V4（2026-04-24） | [Change Log](https://api-docs.deepseek.com/updates) | 官方文档 |
| F7 | `GET /models` 可用 | 有。`GET https://api.deepseek.com/models`，返回 `{object:"list", data:[...]}` | [Lists Models](https://api-docs.deepseek.com/api/list-models) | 官方文档 |
| F8 | `/models` 返回字段（**比旧的只有 id 富得多**） | 每项：`id` / `object` / `owned_by` / `name` / `context_window` / `max_output_tokens` / `input_modalities` / `output_modalities` / `effort.supported_levels` / `effort.default_level` / `api_capabilities.anthropic_messages.system_prompt_update`（`leading-only` \| `in-history`） | [Lists Models](https://api-docs.deepseek.com/api/list-models) | 官方文档 |
| F8a | `/models` **实际返回哪些 id** | ❓ **未实测**（需 API Key，本机无凭据；官方页面只给 schema 与 curl 示例，未列 example 值） | — | ❓ |
| F9 | SSE 流式 | `stream:true` → `text/event-stream`，`data:` 行逐块给增量的 JSON，**以字面量 `data: [DONE]` 结尾**（该行不是 JSON） | [Chat Completions API](https://api-docs.deepseek.com/api/create-chat-completion) | 官方文档 |
| F10 | `usage` 在流式何时返回 | ① `stream_options.include_usage=true` → **所有块都带 usage 字段**，除最后一块外值均为 `null`；② 不设/`false` → 除最后一块外都不含 usage 字段；③ **无论是否设置，`data: [DONE]` 之前的最后一块都带整包 token 统计** | 同上（`stream_options.include_usage`） | 官方文档 |
| F11 | **是否单独发一个 usage-only 块** | **否**（与 OpenAI 不同！）：「不会单独下发一个只含 usage 的块：统计信息**附加在最后一个内容块上**，该块的 `choices` 数组始终只含一个元素、不含新增内容且 `finish_reason` 非 null」 | 同上 | 官方文档 |
| F12 | `usage` 字段清单 | `prompt_tokens`（=hit+miss）/ `completion_tokens` / `total_tokens` / `prompt_cache_hit_tokens` / `prompt_cache_miss_tokens` / `prompt_tokens_details.cached_tokens` / `completion_tokens_details.reasoning_tokens` | 同上 | 官方文档 |
| F13 | **`temperature` 在思考模式下无效** | 「**Has no effect in thinking mode.**」（默认 `thinking.type = enabled`） | 同上 | 官方文档 |
| F14 | `top_p` 生效范围 | 仅思考模式生效，有效区间 0.95–1.0（<0.95 按 0.95）；**非思考模式固定 1.0、传入被忽略** | 同上 | 官方文档 |
| F15 | 思考模式开关 | `thinking:{type: enabled\|disabled}`（默认 `enabled`）；或 `reasoning_effort: none\|low\|high\|max`（默认 `high`；`minimal→low`、`medium/xhigh→high` 兼容映射） | 同上 | 官方文档 |
| F16 | 上下文/输出上限 | 上下文 **1M**；`max_tokens` 取值 1–**384K**（默认 8K 非思考 / 64K 思考 / 128K 当 `reasoning_effort=max`） | [Models & Pricing](https://api-docs.deepseek.com/quick_start/pricing) | 官方文档 |
| F17 | 价格（peak/off-peak，每 1M token） | deepseek-flash：输入 cache-hit $0.003/$0.006，cache-miss $0.15/$0.30，输出 $0.6/$1.2；v4-pro：$0.022/$0.044、$0.66/$1.32、$1.98/$3.96。**off-peak 为 peak 一半**（peak = UTC 周一至五 01:00–04:00 与 06:00–10:00） | 同上 | 官方文档 |
| F18 | 并发上限 | flash 2500 / v4-pro 500（账号级，超限 429） | [Rate Limit](https://api-docs.deepseek.com/quick_start/rate_limit) | 官方文档 |
| F19 | **保活机制（手写解析必读）** | 等待期：**非流式**持续返回**空行**；**流式**持续返回 **`: keep-alive` 注释行（以冒号开头）**；请求 10 分钟未开始推理则服务端关连接 | 同上 | 官方文档 |
| F20 | JSON 输出 | `response_format:{type:"json_object"}`，**必须同时在 system/user 里明确要求 JSON**，否则可能狂吐空白直到截断；`finish_reason="length"` 时内容可能被截断 | [Chat Completions API](https://api-docs.deepseek.com/api/create-chat-completion) | 官方文档 |
| F21 | 已废弃参数 | `frequency_penalty` / `presence_penalty` **不再支持**，传入无效 | 同上 | 官方文档 |
| F22 | 中文 token 换算（官方） | **1 英文 ≈ 0.3 token；1 中文 ≈ 0.6 token**（仅粗估） | [Token & Token Usage](https://api-docs.deepseek.com/quick_start/token_usage) | 官方文档 |
| F23 | **官方离线 tokenizer** | 提供下载：`https://cdn.deepseek.com/api-docs/deepseek_v4_tokenizer.zip`（本次实测可下载，1.9 MB，含 `tokenizer.json` 6.37 MB + `tokenizer_config.json` + `deepseek_tokenizer.py`） | 同上 | 官方文档 + **本机实测** |
| F23a | 该 tokenizer 的依赖 | `deepseek_tokenizer.py` **仅 277 字节**，内容是 `import transformers; AutoTokenizer.from_pretrained(..., trust_remote_code=True)`，`tokenizer_class = LlamaTokenizerFast` → **必须装 `transformers`（重）** | 本机下载解压实测 | **本机实测** |
| F24 | 响应里还有个独立字段 | 思考模式下 `message.reasoning_content`（独立于 `content`） | [Chat Completions API](https://api-docs.deepseek.com/api/create-chat-completion) | 官方文档 |

> **对 D-11「必须打 /models 核对、防 200 假绿」的补充证据**：`/models` 现在返回的字段足以**直接读出 `context_window` / `max_output_tokens` / `effort.supported_levels`**——也就是说，D-13 的预算分母与 F16 的输出上限**不必硬编码**，可从 `/models` 拉取。这比"只核对 id 白名单"更强。

---

## 2. 逐条产出

### [A-01] sseclient-py
- **是什么**：纯 Python 的 SSE 客户端，把一个已连接的二进制响应流解析成 SSE 事件。
- **为什么可用**：正是 D-11「stdlib urllib + SSE 解析」的现成参照——构造函数接受任意二进制流（文档写「通常实现 `io.BinaryIOBase`，如 httplib 或 urllib3 的 HTTPResponse 对象」），**可以直接喂 `urllib.request.urlopen(...)` 的返回**；内部已处理跨 HTTP chunk 拼接（按 `\r\r`/`\n\n`/`\r\n\r\n` 切事件）、**忽略以冒号开头的注释行**（正好覆盖 F19 的 `: keep-alive`）、data 多行拼接。
- **接入成本**：**0 个运行期依赖**（PyPI `requires_dist` 实测为空）；**纯 Python**；wheel **8.2 KB**；源码实际只有一个 `__init__.py`，`import` 段只有 `import logging`。可整文件 vendor 进项目，不破坏「零依赖」。
- **License**：**Apache-2.0**（PyPI `license` = "Apache Software License v2"；GitHub 仓库页亦标 Apache-2.0）。
- **维护活跃度**：最新版 **1.9.0**，PyPI 上传 **2026-01-02**；首次发布 2016-03-11；仓库 2026-01 才迁移到 uv/hatch/ruff（"Modernize project infrastructure"），说明**仍在维护**（非纯停维）。
- **风险**：单维护者；**不处理 `data: [DONE]`**（这是 OpenAI 方言而非 SSE 规范，需调用方自己判哨兵）；不做重连（对 LLM 流式反而正确——流到一半静默重连会丢 token）。
- **是否适合本项目**：**适合**（作为"手写还是引库"的第三选项：**vendor 一个 0 依赖纯 Python 文件**）。
- **URL**：https://github.com/mpetazzoni/sseclient ｜ https://pypi.org/project/sseclient-py/ （分级：**官方仓库**）

### [A-02] httpx-sse
- **是什么**：给 HTTPX 加 SSE 解析的薄封装（`connect_sse` + `iter_sse`）。
- **为什么可用**：如果未来改用 httpx，这是标准做法；`SSE` 字段解析（event/data/id/retry）成熟。
- **接入成本**：**自身 0 运行期依赖**，但**必须已装 httpx**（否则无意义）；纯 Python；wheel 8.8 KB。
- **License**：**MIT**。
- **维护活跃度**：最新版 **0.4.3**，上传 **2025-10-10**；PyPI 明确标注「This is beta software. Please be sure to pin your dependencies.」仓库活跃但发版间隔偏长。
- **风险**：**自标 beta**、建议锁 `0.4.*`；引入 httpx 等于引入 4 个依赖（anyio/certifi/httpcore/idna），与 D-11 零依赖方向冲突。
- **是否适合本项目**：**不适合**（本项目已定 urllib 路线；已装 httpx 时才需考虑）。
- **URL**：https://pypi.org/project/httpx-sse/ ｜ https://github.com/florimondmanca/httpx-sse （分级：官方仓库）

### [A-03] LiteLLM
- **是什么**：100+ provider 的 OpenAI 形状统一客户端（外加可选 proxy）。
- **为什么可用**：若未来要"DeepSeek + GLM 多 provider"，它把差异收敛到一个 `completion()`。
- **接入成本**：**16 个运行期依赖**（实测 `requires_dist`：`fastuuid`、`httpx[http2]`、`openai`、`python-dotenv`、`tiktoken`、`importlib-metadata`、`tokenizers`、`click`、`jinja2`、`aiohttp`、`pydantic`、`pydantic-settings`、`jsonschema`、**`boto3`** 等，共 87 条声明规则）；**win_amd64 wheel 实测 27.5 MB**（sdist 18.5 MB）；含编译件（tiktoken/tokenizers 拖入）。**纯 Python 但依赖不纯**。
- **License**：**MIT**（`license_expression` 实测 = MIT）；⚠️ **但 LICENSE 文件明写 `enterprise/` 目录另用其专属许可**（"All content that resides under the enterprise/ directory ... is licensed under enterprise/LICENSE"）——自用/非商业无碍，**商用需注意**。
- **维护活跃度**：最新版 **1.103.1**，上传 **2026-09-29**；906 个带文件版本；PyPI 月下载量数百万级（社区帖称 #46）。
- **风险**：**体积/依赖最重**；版本迭代极快（900+ 发版）→ API 面变动风险；官方文档定位偏"网关/企业"，与"单人本地 CLI 零依赖"目标背离。
- **是否适合本项目**：**不适合整体引入，需实测**（若确要"借鉴其 provider 差异映射与错误码归一表"可只读源码）。
- **URL**：https://github.com/BerriAI/litellm ｜ https://www.litellm.ai/ （分级：官方仓库）

### [A-04] openai 官方 Python SDK
- **是什么**：OpenAI 官方 SDK，DeepSeek **完全兼容**（改 base_url 即可）。
- **为什么可用**：F1 已证 DeepSeek 用 OpenAI 格式；用它可以**不手写 SSE**、直接拿到 `chunk.usage`。
- **接入成本**：**6 个运行期依赖**（实测：`anyio`、`httpx2`、`jiter`、`pydantic`、`sniffio`、`typing-extensions`）；纯 Python；wheel **2.0 MB**。
- **License**：**Apache-2.0**（`license_expression` 实测 = Apache-2.0）。
- **维护活跃度**：最新版 **3.22.1**，上传 **2026-09-30**（当天）；439 个版本。极活跃。
- **风险**：**与"引擎要能在只有 stdlib 的机器上跑"直接冲突**（6 依赖 + pydantic-core 编译件）；但对"零依赖只是长寿偏好、不是硬约束"的场景是**最省心**选项。
- **是否适合本项目**：**需实测**（D-11 若选 (c) 混合模式，这是可选 SDK；若死守 (a) 零依赖则不采纳）。
- **URL**：https://pypi.org/project/openai/ ｜ https://github.com/openai/openai-python （分级：官方仓库）

### [A-05] aisuite
- **是什么**：跨 provider 的统一 Chat Completions API（现还带 Agents API）。
- **为什么可用**：轻量多 provider 抽象，换 provider 只改一个字符串。
- **接入成本**：**3 个运行期依赖**（实测：`docstring-parser`、`httpx`、`pydantic`）；纯 Python；wheel **222.9 KB**；provider SDK 走 extras（`pip install 'aisuite[anthropic]'`，base 包不含）。
- **License**：**MIT**（GitHub 仓库页原文 "Released under the MIT License"；⚠️ **PyPI JSON 的 license 字段为空**，以仓库页为准）。
- **维护活跃度**：最新版 **0.2.0**，上传 **2026-09-18**；仓库最新提交 2026-09-18（release-0.2.0）。**注意**：另一开源件 any-llm 的 README 公开吐槽 "AISuite ... lacks active maintenance"——但实测 0.2.0 是 12 天前发的，**该吐槽此刻不成立**（转录冲突，标 ❓ 供 HT 注意）。
- **风险**：仍在 0.x，API 面可能变；base 包虽轻，但真用某 provider 仍会拉对应官方 SDK。
- **是否适合本项目**：**需实测**（想轻量多 provider 时是候选；单 DeepSeek 一家则过重）。
- **URL**：https://github.com/andrewyng/aisuite （分级：官方仓库）

### [A-06] any-llm（PyPI 名 `any-llm-sdk`）
- **是什么**：Mozilla AI 出的统一 provider 接口，**复用官方 SDK**、无代理。
- **为什么可用**：**有 `deepseek` extra**（PyPI extras 实测列出 `deepseek`）；也支持"自定义 OpenAI 兼容端点"。定位正是"轻 wrapper + 官方 SDK 保兼容"。
- **接入成本**：base wheel **295 KB**、纯 Python；**要求 Python ≥3.11**（本机 3.13/3.14 满足）；但每个 provider 走 extra，**实装某 provider 时会拉其官方 SDK**（N 依赖）。
- **License**：**Apache-2.0**（PyPI 页 + 仓库页均确认）。
- **维护活跃度**：最新版 **1.29.0**，上传 **2026-09-24**；首次 2025-07-15，**85 个版本**；GitHub ~2206 stars。很活跃。
- **风险**：包名易混（GitHub 叫 any-llm，PyPI 叫 `any-llm-sdk`，`pip install any-llm` 实测 **404**）；不同 provider extra 的依赖量不同；生态较新。
- **是否适合本项目**：**需实测**（若确定"多 provider 且想复用官方 SDK"，它比 litellm 轻）。
- **URL**：https://github.com/mozilla-ai/any-llm ｜ https://docs.mozilla.ai/any-llm/ （分级：官方仓库）

### [A-07] pydantic v2
- **是什么**：Python 类型校验/序列化库，`BaseModel` 定义 schema。
- **为什么可用**：D-12「解析失败绝不静默回退」的最直接落法——`Model.model_validate_json(raw)` 失败即抛 `ValidationError`；`model_json_schema()` 可把 schema 喂给 `response_format`。
- **接入成本**：**4 个运行期依赖**（`annotated-types`、`pydantic-core`、`typing-extensions`、`typing-inspection`）；**pydantic-core 是编译件**（win_amd64 wheel 实测 **2.08 MB**）；pydantic 本体 wheel 461.5 KB。`requires_python >=3.9`。
- **License**：**MIT**（`license_expression` 实测 = MIT）。
- **维护活跃度**：最新版 **2.13.5**，上传 **2026-08-28**；206 个版本。极活跃。
- **风险**：pydantic-core 是 Rust 编译件 → **破坏"纯 stdlib 可移植"**；v1→v2 有破坏性变更（老库可能卡 v1）。
- **是否适合本项目**：**需实测**（是否愿意为校验引入一个编译依赖；若不愿，见 A-09）。
- **URL**：https://github.com/pydantic/pydantic ｜ https://docs.pydantic.dev/ （分级：官方仓库）

### [A-08] jsonschema
- **是什么**：JSON Schema 的参考实现（校验器）。
- **为什么可用**：若坚持"零/少依赖"，它可以只做 schema 校验那一步（不引入 pydantic 的编译件体系）。
- **接入成本**：**4 个运行期依赖**（`attrs`、`jsonschema-specifications`、`referencing`、**`rpds-py`**）；`rpds-py` 是**编译件**（win_amd64 wheel 实测 215 KB）；jsonschema 本体纯 Python wheel 88.5 KB。
- **License**：**MIT**（`license_expression` 实测 = MIT）。
- **维护活跃度**：最新版 **4.26.0**，上传 **2026-01-07**；109 个版本。
- **风险**：仍带编译件（rpds-py）；纯 Python 的部分只有本体。
- **是否适合本项目**：**需实测**（要 JSON Schema 校验、又接受一个 215 KB 编译依赖时的中庸选项）。
- **URL**：https://github.com/python-jsonschema/jsonschema （分级：官方仓库）

### [A-09] fastjsonschema
- **是什么**：把 JSON Schema **编译成 Python 校验函数**，纯 Python 实现。
- **为什么可用**：**0 运行期依赖 + 纯 Python**，能同时满足"要 schema 校验"与"零依赖"。比 A-07/A-08 更贴 D-11。
- **接入成本**：**0 个运行期依赖**（实测空）；纯 Python；wheel **26.8 KB**；`requires_python >=3.10`。
- **License**：**BSD-3-Clause**（实测 `license` = "BSD-3-Clause"，classifier 亦为 BSD）。
- **维护活跃度**：最新版 **2.22.2**，上传 **2026-08-15**；首次 2016-10-05；48 个版本，仍维护。
- **风险**：功能子集（对最新 JSON Schema draft 的覆盖不如 jsonschema 全）；编译式校验对**动态 schema** 不友好（要每次编译）。
- **是否适合本项目**：**适合**（当 D-12 只要"结构断言"而非"完整 draft 支持"时，这是最省依赖的选择）。
- **URL**：https://pypi.org/project/fastjsonschema/ ｜ https://github.com/horejsek/python-fastjsonschema （分级：活跃仓库）

### [A-10] Instructor
- **是什么**：`response_model=Pydantic类` → 拿回已校验对象的封装，**校验失败自动回灌错误并重试**。
- **为什么可用**：把"JSON 出不来就重试"这套循环做成现成件。
- **接入成本**：**18 个运行期依赖**（实测：`aiohttp`、`click`、`docstring-parser`、`idna`、`jinja2`、`jiter`、`openai`、`pydantic-core`、`pydantic`、`regex`、`requests`、`rich`、`tenacity`、`typer`、`urllib3` …）；wheel 263 KB，**但 sdist 68 MB**（含测试素材）；纯 Python 本体。
- **License**：**MIT**（实测 `license` = MIT）。
- **维护活跃度**：最新版 **1.17.0**，上传 **2026-09-09**；首次 2023-07-28；98 个版本。很活跃（社区帖称 ~3M 下载/月、13k stars）。
- **风险**：**18 依赖，且强绑 `openai` SDK 与 pydantic**；库自带"自动重试"可能**与 D-12「绝不静默回退」语义打架**（要显式限制重试次数并在耗尽时硬失败）。
- **是否适合本项目**：**需实测**（更值得做法是**只抄它的"校验失败→回灌→重试N次→抛错"循环结构**，不引库）。
- **URL**：https://github.com/567-labs/instructor ｜ https://python.useinstructor.com/ （分级：官方仓库）

### [A-11] Outlines
- **是什么**：约束式生成（把正则/JSON Schema/CFG 编译成 logits 掩码，模型只能吐合法 token）。
- **为什么可用**：在**自托管模型**上保证 100% schema 合规。
- **接入成本**：**9 个运行期依赖**（`jinja2`、`cloudpickle`、`diskcache`、`pydantic`、`jsonschema`、**`pillow`**、`typing_extensions`、`outlines_core`、`genson`）；wheel 112 KB；`requires_python <3.14`（**注意：本机 3.14.3 不满足上界**）。
- **License**：**Apache-2.0**（实测）。
- **维护活跃度**：最新版 **1.3.3**（发版日期未单独实测 ⏳，仓库活跃）。
- **风险**：**面向本地/自托管模型**（要 logits 访问）；本项目走 **DeepSeek API**，拿不到 logits → **核心能力用不上**；且 `requires_python <3.14` 与本机 3.14.3 冲突。
- **是否适合本项目**：**不适合**。
- **URL**：https://github.com/dottxt-ai/outlines ｜ https://dottxt-ai.github.io/outlines/ （分级：官方仓库）

### [A-12] json-repair
- **是什么**：修复 LLM 产出的坏 JSON（缺引号/逗号/括号、被 markdown 包裹、截断、夹带散文）。
- **为什么可用**：解决"JSON 被 ```json 包裹""尾逗号""截断"等高频形态问题。
- **接入成本**：**0 个运行期依赖**（实测空）；纯 Python；wheel **50.1 KB**；`requires_python >=3.10`。
- **License**：**MIT**（`license_expression` 实测 = MIT）。
- **维护活跃度**：最新版 **0.63.5**，上传 **2026-09-22**；2023 起 **180 个版本**（发版极密）。很活跃。
- **风险**：**默认行为是"静默修复"——与 D-12「解析失败绝不静默回退」直接语义冲突**。官方文档提供了 `strict=True`（遇结构问题**抛 `ValueError` 而非修复**）；另有 schema 引导修复（beta）与 `stream_stable`（流式局部 JSON）。
- **是否适合本项目**：**需实测**（推荐用法：**默认关"自动修复"，只在 `strict=True` 下当"更友好的校验器"；或仅用它把坏 JSON 归一化后再交给 pydantic/fastjsonschema 硬校验**——绝不能拿它当"解析失败的兜底"）。
- **URL**：https://github.com/mangiucugna/json_repair ｜ https://pypi.org/project/json-repair/ （分级：官方仓库）

### [A-13] tiktoken
- **是什么**：OpenAI 的 BPE 分词器（`cl100k_base` / `o200k_base`）。
- **为什么可用**：本地估算 OpenAI 系 token。
- **接入成本**：**2 个运行期依赖**（`regex`、`requests`）+ **编译件**（win_amd64 wheel 实测 **~0.92 MB**）。
- **License**：**MIT**。
- **维护活跃度**：最新版 **0.14.0**，上传 **2026-08-17**；20 个版本。
- **风险**：**它的词表是 OpenAI 的，不是 DeepSeek 的** → 用于 DeepSeek 预算会**系统性偏差**（多篇资料指中文场景偏差显著，实测研究称 cl100k 中文约 1.16 token/字 vs DeepSeek 官方 0.6 token/字，**约 2 倍高估**）。高估会**误触发** D-13 熔断。
- **是否适合本项目**：**不适合**（作为 DeepSeek 预估算器）。
- **URL**：https://github.com/openai/tiktoken （分级：官方仓库）

### [A-14] DeepSeek 官方离线 tokenizer（tokenizer.json 包）
- **是什么**：官方提供的 DeepSeek V4 tokenizer 文件包 + 使用示例。
- **为什么可用**：**唯一"与计费口径对齐"的本地 token 计数方式**（F23）。
- **接入成本**：zip 实测 1.9 MB，解包含 `tokenizer.json` **6.37 MB** + `tokenizer_config.json` 3 KB + `deepseek_tokenizer.py` **277 字节**；该 py **只做 `transformers.AutoTokenizer.from_pretrained(...)`** → **必须装 `transformers`**（实测 requires：`huggingface-hub`、`numpy`、`packaging`、`pyyaml`、`regex`、`tokenizers`、`typer`、`safetensors`、`tqdm` 共 9 依赖，含编译件 `tokenizers` ~2.8 MB）。**非零依赖**。
- **License**：❓ **该 zip 内未附 LICENSE 文件**（仅三个文件）；tokenizer 文件的再分发条款**未在包内声明**，需查 DeepSeek 服务条款（未核实）。
- **维护活跃度**：随模型版本更新（F23 链接指向 v4 tokenizer）；无独立版本号。
- **风险**：**拖入 transformers 全家桶**（破坏零依赖）；6.4 MB 词表 + 编码开销对"调用前快速估算"过重；再分发许可不明。
- **是否适合本项目**：**需实测**（本轮更合理的姿势见反转 R4：**用官方比例粗估 + `usage` 回写校准**，把离线 tokenizer 当作"按需可选的高精度模式"）。
- **URL**：https://api-docs.deepseek.com/quick_start/token_usage （官方文档，含 zip 链接）（分级：**官方文档**）

### [A-15] simpleeval
- **是什么**：单文件、基于 `ast` 的安全表达式求值器（`simple_eval("21+21")`）。
- **为什么可用**：若想把 `route_error` 的规则写成"可配置表达式"而非硬编码关键词，它提供 0 依赖的安全求值。
- **接入成本**：**0 个运行期依赖**（实测空）；纯 Python；wheel **18.5 KB**；单文件。
- **License**：**MIT**（实测 `license` = MIT，classifier 亦 MIT）。
- **维护活跃度**：最新版 **1.0.8**，上传 **2026-09-12**；首次 2014；27 个版本。近期有安全修复（1.0.5 修 CVE-2026-32640 沙箱逃逸），**在维护**。
- **风险**：它是**表达式求值器，不是分类器/路由器**——解决不了"D-14 是文本→分类"这个本问题；且项目自陈存在 DoS 面（长表达式/大内存）。
- **是否适合本项目**：**不适合**（除非真要做"规则可配置化"，那也属过度设计；见下表 ❌ 与反转 R6 的分析）。
- **URL**：https://github.com/danthedeckie/simpleeval （分级：官方仓库）

### [A-16] durable-rules
- **是什么**：Python 规则引擎（Rete 算法，事件驱动）。
- **为什么可用**：名义上是"通用规则引擎"。
- **接入成本**：**0 个运行期依赖**（实测空）；sdist 56.2 KB；纯 Python。
- **License**：**MIT**（实测）。
- **维护活跃度**：最新版 **2.0.28**，上传 **2020-06-07** —— **已停更约 6 年**（首次 2016-02-13，103 个版本后归零）。
- **风险**：**长期停维**；Rete 引擎对"D-14 三分类关键词命中计数"属**杀鸡用牛刀**。
- **是否适合本项目**：**不适合**（停维 + 过度设计，见反转 R6）。
- **URL**：https://pypi.org/project/durable-rules/ （分级：活跃仓库/已停维）

### [A-17] tenacity / backoff（重试与退避）
- **是什么**：通用重试/退避/抖动装饰器。
- **为什么可用**：LLM 调用层需要"429/5xx 指数退避重试"（F18 有 429；流式中断后不应静默重连）。
- **接入成本**：tenacity **0 依赖**、纯 Python、wheel 28.2 KB；backoff **0 依赖**、轮子更小。均纯 Python。
- **License**：tenacity **Apache-2.0**；backoff **MIT**（均实测）。
- **维护活跃度**：tenacity 最新 **9.1.4**（发版日期见下注）；backoff 最新 **2.2.1**。均常青库。
- **风险**：对"POST 前的 429/503 重试"很合适；**但流式已开始后不可自动重连**（会丢 token），这层语义必须**手写策略**，库只提供机械重试。
- **是否适合本项目**：**需实测**（也可手写 <20 行退避，见反转 R3 的同思路：能 0 依赖手写就别引）。
- **URL**：https://github.com/jd/tenacity ｜ https://github.com/litl/backoff （分级：官方仓库）

> 注：本轮实测中 tenacity/backoff 的**精确发版日期**未单独回填（脚本按版本匹配时受 `releases` 字段影响），标 ⏳；版本号 9.1.4 / 2.2.1 为 PyPI 实测。

### [A-18] 手写 SSE 解析器（对照基线，非项目）
- **是什么**：约 40–80 行 stdlib 代码：`urllib.request` + `for raw in resp:` + 按 `\n\n` 切帧 + 跳过 `:` 开头注释行 + 剥 `data:` 前缀 + 判 `[DONE]` + 累积 buffer 再 `json.loads`。
- **为什么可用**：**完全贴合 D-11(a)**，且对 DeepSeek 的三个"方言坑"（F19 keep-alive、F9 `[DONE]`、F11 usage 无独立块）有**完全控制权**。
- **接入成本**：**0 依赖**；纯 Python；体积≈0。
- **License**：N/A（自研）。
- **维护活跃度**：N/A。
- **风险**：**边界要自己兜全**：跨 chunk 帧拼接、UTF-8 多字节被切、心跳帧、10 分钟连接关闭（F19）、`data:` 冒号后空格剥除、多行 data 拼接、usage 落在最后内容块（F11，**照抄 OpenAI 会漏**）。
- **是否适合本项目**：**适合**（作为基线；但**先看 A-01——它已把这套边界实现好且 0 依赖**）。
- **URL**：踩坑清单见 [Handling SSE from LLM APIs in Python](https://n4n.ai/blog/handling-server-sent-events-from-llm-apis-in-python)（社区帖）｜ [DeepSeek SSE 形状](https://dev.to/multigrid/the-streaming-response-shape-of-the-deepseek-api-3dej)（社区帖）

---

## 3. 三张表（供 HT 取用，不代拍板）

### ✅ 可直接拿来用（0 依赖 / 纯 Python / 许可宽松 / 成熟）

| 编号 | 名称 | 用途 | License | 最新发版 | 体积 | 依赖 |
|---|---|---|---|---|---|---|
| A-01 | **sseclient-py** | SSE 解析（喂 urllib 响应） | Apache-2.0 | 2026-01-02 | 8.2 KB | **0** |
| A-09 | **fastjsonschema** | JSON Schema 校验 | BSD-3-Clause | 2026-08-15 | 26.8 KB | **0** |
| A-12 | **json-repair**（**仅 strict 用法**） | 坏 JSON 归一/报错 | MIT | 2026-09-22 | 50.1 KB | **0** |
| A-17 | **tenacity / backoff** | 429/5xx 退避重试 | Apache-2.0 / MIT | — | 28 KB / 小 | **0** |

> 说明：这四件都是"**引进来也不破坏零依赖**"的（自身 0 运行期依赖、纯 Python、体积 KB 级）。**A-01 可直接 vendor 单文件**。

### ⏳ 需改造后自用

| 编号 | 名称 | 改造点 | License | 最新发版 | 依赖/体积 |
|---|---|---|---|---|---|
| A-03 | LiteLLM | 只借鉴 provider 差异映射/错误码归一，**整体不引** | MIT（enterprise 目录另许可） | 2026-09-29 | 16 依赖 / 27.5 MB |
| A-04 | openai SDK | 作 D-11(c) 可选 SDK（base_url→DeepSeek） | Apache-2.0 | 2026-09-30 | 6 依赖 / 2.0 MB |
| A-05 | aisuite | 轻量多 provider 抽象候选 | MIT | 2026-09-18 | 3 依赖 / 223 KB |
| A-06 | any-llm-sdk | 有 `deepseek` extra；复用官方 SDK | Apache-2.0 | 2026-09-24 | base 0 拉 SDK，装 provider 才拉 / 295 KB |
| A-07 | pydantic v2 | 校验；或只抄"失败抛错"语义 | MIT | 2026-08-28 | 4 依赖（含编译件）/ 461 KB + 2.08 MB |
| A-08 | jsonschema | 要完整 draft 支持时 | MIT | 2026-01-07 | 4 依赖（含 rpds 编译件）/ 88.5 KB |
| A-10 | Instructor | 只抄"校验失败→回灌→重试→抛错"循环 | MIT | 2026-09-09 | 18 依赖 / 263 KB |
| A-14 | DeepSeek 官方 tokenizer zip | 高精度本地计数（按需） | ❓ 包内无 LICENSE | 随模型 | 6.4 MB 词表 + 需 transformers |

### ❌ 不采纳（本项目当前形态下）

| 编号 | 名称 | 不采纳理由 | 依据 |
|---|---|---|---|
| A-11 | **Outlines** | 面向自托管模型（需 logits）；本项目走 API；且 `requires_python <3.14` 与本机 3.14.3 **冲突** | 实测 requires_dist |
| A-15 | **simpleeval** | 是"表达式求值器"不是"分类/路由器"，解决不了 D-14 本问题 | 官方 README |
| A-16 | **durable-rules** | **2020-06-07 停更**；Rete 引擎对"关键词计数分类"过度设计 | 实测发版日期 |
| A-02 | **httpx-sse** | **自标 beta** + 需 httpx（与零依赖路线冲突） | PyPI 项目页 |
| A-13 | **tiktoken** | 词表是 OpenAI 的，用于 DeepSeek 预算**系统性偏差（中文约 2× 高估）** | F22 vs 社区实测 |
| — | **eventsource** | **GPLv3**（本机实测）——许可传染风险，规避 | PyPI `license` 实测 |
| — | **sse-starlette** | 服务端实现，本项目是**客户端** | PyPI 描述 |

---

## 4. 反转性发现（≥2 条，本件给 6 条）

### R1（反转 D-11 前提）**"模型 id 白名单"已换代，网上/课程里的 `deepseek-chat`/`deepseek-reasoner` 是过时信息**
- **证据**：官方 Change Log（2026-04-24）明确 `deepseek-chat`/`deepseek-reasoner` **2026-07-24 停用**；现行白名单是 **`deepseek-flash`（V4.1-Flash）/ `deepseek-v4-pro`**（F3/F5/F6）。
- **影响**：① 任何"先接 deepseek-chat"的方案**直接踩空**；② 任务书提到**本机 `~/.workbuddy/models.json` 注册的 `deepseek-v4-flash` 已是"退休别名"**（仍可用，但服务端会路由到 V4.1-Flash 计费）——**"本机配的就是对的"这个假设不成立**；③ D-11「探活前置」必须改为**打 `/models` 读真实白名单**，且白名单会随代际漂移。
- **来源**：[官方 Change Log](https://api-docs.deepseek.com/updates)、[Models & Pricing](https://api-docs.deepseek.com/quick_start/pricing)

### R2（反转 D-12 的一条硬拦截）**"分阶段温度 0.0/0.3"在 DeepSeek 上是潜在死代码**
- **证据**：官方 API 文档原文 "**Has no effect in thinking mode.**"，而 `thinking.type` **默认 = enabled**（F13/F15）；`top_p` 也是"非思考模式固定 1.0、传入被忽略"（F14）。
- **影响**：D-12 三件套里的第③条「分阶段温度（框架 0.0 / 反思 0.3）」**若不先显式 `thinking:{type:"disabled"}` 或 `reasoning_effort:"none"`，会被静默忽略**——属于框架自己最怕的"静默失效"类故障。**要么**在非思考模式下调温度，**要么**承认温度档位在思考模式不可用、改用 `reasoning_effort`（none/low/high/max）做"档位差异"。
- **附**：异步"异构降级"里想用"推理档位差异"替代模型异构——**这条恰好可行**（`reasoning_effort` 是官方支持的档位旋钮）。
- **来源**：[Chat Completions API](https://api-docs.deepseek.com/api/create-chat-completion)

### R3（反转"零依赖=只能手写")**存在"零依赖但也成熟"的现成件：sseclient-py（8 KB、纯 Python、0 依赖、可直接喂 urllib）**
- **证据**：A-01 实测 —— 0 运行期依赖、源码只 `import logging`、构造函数接受任意二进制流（文档点名 urllib3/httplib 的 HTTPResponse）、内置跨 chunk 拼接与**"以冒号开头的行为注释、忽略"**（正好接住 DeepSeek 的 `: keep-alive`）。
- **影响**：D-11 的选项应**从"手写 vs 引库"二分，扩为三分**——**(d) vendor 一个 0 依赖纯 Python 单文件**：既不破坏"零依赖"，又省掉手写边界。**但**`data: [DONE]` 与 "usage 落在最后内容块"仍是**调用方责任**（A-01 不管），所以"零依赖"下也**不可能完全零手写**。
- **来源**：本机 PyPI 实测 + https://github.com/mpetazzoni/sseclient

### R4（反转"没有官方分词器 → 只能 tiktoken"）**官方给了离线 tokenizer，但它是"零依赖陷阱"；正确姿势是"官方比例估算 + usage 回写"**
- **证据**：F22/F23/F23a —— 官方提供 `deepseek_v4_tokenizer.zip`（本机实测可下载），**但其示例脚本必须 `transformers`**，且词表 6.4 MB；官方同时给出粗估比例 **EN 0.3 / CN 0.6 token/字**。
- **影响**：D-13 的"调用前 enforcement"**不该**为了算 token 去引 `transformers`（重）或 `tiktoken`（错）——**最省且最准的组合是**：调用前用**官方比例粗估**（可对历史 `usage` 做线性校准），调用后用 **`usage.prompt_tokens` 回写**修正（这正是 `context_compression.md` §2「校准回写」的同一思想）。把离线 tokenizer 降级为"按需高精度模式"，**默认关闭**。
- **来源**：[Token & Token Usage](https://api-docs.deepseek.com/quick_start/token_usage) + 本机下载解压实测

### R5（手写解析器的隐藏坑）**DeepSeek 流式的 `usage` 没有独立 usage-only 块，与 OpenAI 惯例不同**
- **证据**：F11 官方原文——「不会单独下发一个只含 usage 的块：统计信息附加在**最后一个内容块**上，该块 `choices` 只有 1 个元素、无新增内容且 `finish_reason` 非 null」。（对照：OpenAI 习惯是发一个 `choices:[]` 的 usage 块；多篇社区帖给的示例正是 `choices:[]`，**照抄会漏 usage**。）
- **影响**：手写 SSE 解析器**不能用"`choices` 为空即 usage 块"这条 OpenAI 判据**；必须在**收到 `finish_reason != null` 的那一块**里取 `usage`。**这条正好可做成 D-12 的"import 后核对核心函数存在"之外的第四条硬拦截：解析器必须对 "usage 缺失" 显式报错**。
- **来源**：[Chat Completions API](https://api-docs.deepseek.com/api/create-chat-completion)

### R6（对 D-14 的诚实反证）**`route_error` 引"规则引擎"是负收益；30 行关键词计数 >> durable-rules/simpleeval**
- **证据**：durable-rules **停更于 2020**（A-16）；simpleeval 是表达式求值器（A-15），都不解"文本→分类"。
- **影响**：D-14 的核心是**"命中计数 + 优先级"**（见 `references/error_routing.md`：三组关键词计数、合约优先、无法判断→human），**这正是 20–30 行 `dict`+`sum` 的形态**，用任何引擎都要额外抽象却不增能力。**结论倾向**：**自研**（本件只举证，不替 HT 拍板）。
- **来源**：本机 PyPI 实测 + 现有 `references/error_routing.md`

---

## 5. 未证实项清单（❓，禁止脑补）

| # | 未证实项 | 为什么没证实 | 建议怎么证实 |
|---|---|---|---|
| ❓1 | `GET /models` **实际返回的 id 列表** | 需 API Key，本机无凭据；官方页只给 schema 不给 example 值 | 用户提供 Key 后 `curl -H "Authorization: Bearer $KEY" https://api.deepseek.com/models` |
| ❓2 | `/models` 返回的**具体字段值**（如 flash 的 `max_output_tokens`、`effort.supported_levels`） | 同上 | 同上 |
| ❓3 | DeepSeek 官方 tokenizer zip 的 **`LICENSE`/再分发条款** | 包内**无 LICENSE 文件**，DeepSeek 服务条款未查 | 查 DeepSeek 服务条款页 / 需用户确认 |
| ❓4 | `deepseek-chat`/`deepseek-reasoner` **实测是否已彻底 404** | 未调真实接口 | 用户 Key 探活（预期 2026-07-24 后失效） |
| ❓5 | aisuite 是否"缺乏维护"（any-llm README 公开吐槽） | 与实测（0.2.0 @2026-09-18）**冲突** | 观察后续 3 个月发版节奏 |
| ❓6 | tenacity 9.1.4 / backoff 2.2.1 的**精确发版日期** | 本轮脚本该字段未回填 | 重跑 `_pypi_dates_A.py` 或 PyPI 页面 |
| ❓7 | outlines 1.3.3 的精确发版日期 | 同上 | 同上（但已被 ❌，非关键） |
| ❓8 | 用 tiktoken 估 DeepSeek 中文的**精确偏差系数** | 只有社区实测（1.16 vs 0.6 token/字），非官方 | 用 F23 官方 tokenizer 对同一语料对拍（需先装 transformers） |
| ❓9 | DeepSeek Responses API 的 usage 事件形状（F 里我只覆盖了 Chat Completions） | 本轮未逐字核 Responses 页 | 若 D-11 考虑 Responses API，需补查官方 Responses 文档 |

---

## 6. 给 D-11～D-14 的证据小结（**只列证据，不拍板**）

| 议题 | 本件提供的可用证据 | 相关编号 |
|---|---|---|
| **D-11** 零依赖 LLM 调用层 | ① 存在"0 依赖纯 Python SSE"（A-01）→选项应含"(d) vendor"；② 手写基线的 5 个 DeepSeek 方言坑（F9/F11/F19）；③ 多 provider 各方案的依赖/体积/License 全表（A-03～A-06）；④ `/models` 可读白名单 + 上限（F7/F8） | A-01,A-18,A-03~A-06,F7~F11,F19 |
| **D-12** 硬拦截三件套 | ① 「分阶段温度」在思考模式**无效**（R2）→ 第③条需改设计；② "解析失败不静默回退"的落地件：pydantic/fastjsonschema/json-repair(strict)（A-07/A-09/A-12）；③ json-repair **默认静默修复**与规则冲突（A-12 风险） | A-07,A-09,A-12,F13,F15,R2 |
| **D-13** 调用前 token 预算 | ① tiktoken **不适合** DeepSeek（A-13）；② 官方 tokenizer **非零依赖**（A-14/R4）；③ 官方粗估比例 EN0.3/CN0.6（F22）；④ `usage` 字段清单与回写口径（F12/F11） | A-13,A-14,F11,F12,F22,R4 |
| **D-14** `route_error` | ① 现成规则引擎要么停维要么错配（A-15/A-16）；② 现有 `references/error_routing.md` 的"计数+优先级"属 30 行形态（R6） | A-15,A-16,R6 |

---

*（附：本件所有 PyPI License/依赖/体积均为**本机 curl/urllib 实测**，原始输出见同目录 `_pypi_A_out.txt`；DeepSeek 事实均出自官方文档并附 URL；未证实项已集中列于 §5。）*
