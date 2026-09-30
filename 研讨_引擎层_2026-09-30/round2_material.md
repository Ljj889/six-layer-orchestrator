# Round 2 材料 · 轮间摘要 + 扫描回灌（K7 + K6b）

> 本件喂给全部 4 个 HT（公共材料，只写一次）。**不许全量重读别人提案**——摘要在此，需要细节再按路径查。

---

## 一、Round 1 四家立场摘要（各 ≤6 条）

### HT-设计者（采纳 7 / 改 15 / 驳 0）
1. **主张把 P2 做成"一条有向依赖链一次做完"**：`token_ledger（新建）→ D-11 → D-12③/D-13/compress`；D-14 独立（先用合成样本跑语法级单测）。
2. D-01 **改**：语义收，但反对新开 rule 84（与"近三版 0 新 rule"惯例冲突）→ 并入 rule 43。
3. D-02 **改**：采 (a)，但把 (c) 从"三期后"**提前到 P2**（`cli.py status append|check`），与 D-22(b) 合并。
4. D-04 **改载体**：主载体进 `references/real-source-repro`（它是"测试设计判断"不是"可 grep 检查"）。
5. D-10 **改**：P1 拆 P1a（规则修订）/P1b（升版+分发）；每期补"回滚动作"。
6. 漏项：① 「项目根」单一定义 + 框架自举 ② 运行时用哪个平台副本的引擎 ③ 「审查 FAIL 真伪甄别」从 D-14 剥离。

### HT-实现者（采纳 13 / 改 9 / 驳 0）★ 带 8 条实测
1. **实测：`/models` 白名单只有 `deepseek-flash`/`deepseek-v4-pro`；本机注册的 `deepseek-v4-flash` 不在白名单 → POST 返回 200，响应 `model` 静默变回 `deepseek-flash`。★200 假绿活体★**
2. **D-15 改：cli.py 用 subprocess 转发**（实测 7 脚本三种调用约定、main() 直接 sys.exit 不可 import）。
3. **D-13 改：P2 只做 (b) 告警 + (c) 问人；真熔断 (a) 推 P3**（三个前提实测一条都不成立）。
4. D-12 **三条各自改**：①要 Phase 级状态 ②重定义为"防分发漂移" ③加温度生效探针。
5. D-10 **改**：P2 拆 P2a/P2b，真实工期 **4-6 轮**（非 2-3）。
6. 漏项：① 同项目多脚本并发写丢更新（需 `os.replace()` 原子写）② cli.py 子进程必须显式 `encoding="utf-8"` ③ token 预估缺失是 D-11/D-13/compress 共同隐含前提。
7. 实测：3.14.3 全模块 import OK；`six_layer_check self-test` = **26 PASS/0 FAIL/1 SKIP**（3.14.3 与 3.13.12 一致）。

### HT-用户（大量"砍/降级"）
1. **P0：P2 引擎层整体"为框架而框架"**；最高优先项目（家具店运营）几乎不走框架。
2. **P0：样本=1 过度泛化**——D-01/02/03 全来自伴学一个项目一轮，却要动编号体系/升框架级标配。
3. **P0：四条"多做一步"（D-02/13/16/21）叠加 = 确认疲劳**；建议准入线"每周额外 ≤5 分钟"。
4. **直接砍**：D-19 母板 / D-22(b) 入口页 / D-13 降为只告警 / D-17(c) UI / D-02(c) 三期后引擎化。
5. 漏项：① 过去 30 天框架被真实用了几次（决定 P2 做不做的第一数据）② 家俊时间预算 ③ 回退/停用预案。

### HT-风险官（异构降级位 · 12 条隐含假设表）
1. **P0：「引擎化=更可靠」是地基，但检查器本身会说谎**（v3.19.0 `re.S` 让 84KB 合规闸把 24 个 handler 全看没，既假红又假阴）。
2. **P0：D-11 无网不可自测，且与方案自己的 D-04 冲突**（唯一自测办法是 mock socket = 正好违反刚立的规则）。
3. **P1：D-02/D-03 升格标配违反方案自己的判据 3 与 rule 5/rule 47 B1**。
4. D-12③ **驳回**：唯一模型 `supportsReasoning:true`，reasoning 模型**普遍静默忽略 temperature** → 假绿。
5. D-13 **改数据源**：分母改 provider `usage`；引擎自身调用计入；漏账 fail-closed。
6. D-08 **必须同批改 sync 脚本版本抽检锚点**，否则剪 banner = sync Gate 静默失效（A10）。
7. 漏项：① 引擎自身失败模式与回滚路径（P0）② 代码↔规则漂移检测 ③ 有网/无网双模式边界。

---

## 二、扫描回灌（K6b · 只列能改变裁决的硬证据，带 URL）

### ★ S1 · DeepSeek API 事实（推翻了两条提议的前提）
- **模型白名单已换代**：`deepseek-chat`/`deepseek-reasoner` **2026-07-24 已停用**；现行 **`deepseek-flash`（=V4.1-Flash）/ `deepseek-v4-pro`**。本机 `models.json` 的 `deepseek-v4-flash` 是"退休别名"（仍可用但路由到 V4.1-Flash）。→ **印证 HT2 的 200 假绿实测**。
- **★ `temperature` 在 thinking mode 无效**：官方原文 "Has no effect in thinking mode"，而 **thinking 默认 enabled**。→ **D-12③「分阶段温度 0.0/0.3」若无 `thinking:{type:"disabled"}` 就是静默失效死代码**（= 框架最怕的失效类型）。有效的档位差异应用 `reasoning_effort`（none/low/high/max）。
- **`GET /models` 可用**，返回字段比旧版富（`context_window`/`max_output_tokens`/`effort.supported_levels`/`api_capabilities`）→ **D-13 的预算分母可从接口读，不必硬编码**。
- **SSE**：`data: [DONE]` 结尾；**usage 无独立块**（附在最后内容块，照抄 OpenAI 的 `choices:[]` 判据会漏）；流式保活是 **`: keep-alive` 注释行**。
- 来源：https://api-docs.deepseek.com/ 、/quick_start/pricing 、/api/list-models 、/api/create-chat-completion 、/updates 、/quick_start/token_usage

### ★ S2 · D-11 的第四条路（HT1/HT2/HT3/HT4 都没提）
- **`sseclient-py`：Apache-2.0、最新 2026-01-02、8.2 KB、0 运行期依赖、纯 Python 单文件、源码只 `import logging`**，能直接吃 urllib response，且自带"忽略冒号注释行"（正好接住 `: keep-alive`）。
- → 选项从"手写 vs 引库"扩为 **(d) vendor 一个 0 依赖文件**。
- 同时：`httpx-sse` 自标 beta+需 httpx（❌）；`eventsource` **GPLv3**（❌）；`tiktoken` 词表是 OpenAI 的、估 DeepSeek 中文不可靠（三个口径打架：准确/低估10-15%/高估20.9%）。

### ★ S3 · D-15 的实测（扫描员 B）
- **7 模块全量 import 0.032s；全部 import=OK、顶层零副作用** → cli.py **可零依赖、零改动包住 7 脚本**（只需 `sys.argv = ["x"] + argv`）。
- ⚠️ **但**：`checkpoint`/`cost_log`/`lifecycle` 的 `main()` **大多不调 `sys.exit()`** → 包装层不显式处理则 **cli.py 永远返回 0，Gate 语义直接失效**（原型实测）。
- `argparse` 闭包 **0**；`click` 闭包 **1**；`typer`/`cyclopts`/`cappa` 闭包 **8**（被 rich 绑）。
- **`progress.json` plain dict 与 Apache Burr 官方主打的 "state is a plain dictionary you can inspect, persist, and replay" 是同一设计选择** → 现在方案不是"简陋版"。
- **CrewAI**：`requires_python <3.14` → **本机 3.14.3 装不上**；**141 包**；且 Phase/Wave/三态/Gate/账本/五态/蒸馏 **一样都没有** → 回退=降级。**当思想来源读值得，当运行时依赖不值得**。
- LangGraph `langgraph-checkpoint` 单独也要 **37 包**（硬依赖 langchain-core + langsmith）→ **"借它的检查点"这条路不存在**。
- 唯一"命中状态机+持久化恢复+HITL 且零依赖"的是 **Apache Burr**（Apache-2.0、纯 Python、闭包 1 包、pushed 2026-09-29）：`@action(reads,writes)` + 不可变 State + `halt_after` + `.with_state_persister()` → **四件事都能人肉搬进 cli.py**。

### ★ S4 · D-16 自测网（扫描员 C）
- **stdlib `unittest` + `subTest`**：25 条 fixture 表**1:1 平移**（subTest 失败后继续跑完，正好要这个）。**pytest 6 包 ≈1.74 MB 全纯 Python**（可作 dev-only，不该作主 Gate 依赖）。
- **★ `assert` 是可被 `-O`/`PYTHONOPTIMIZE` 静默关掉的空操作** → **Gate 必须用 `if...raise/exit`，禁止裸 assert**（好消息：实测现有 7 脚本无裸 assert）。
- **★ 现有自测网的"用例 7"是低门槛假绿教科书样本**：它只跑 `bash -n`（官方明说只解析语法，对引号/误用命令/可移植性"没什么可说的"）。**25 条网里就有一条是形式通过而非实质通过**。
- **fixture 实测是 25 条，不是讨论文档写的 24 条**（订正）。
- **pydantic-core 是 Rust 二进制（1.99 MB）+ 精确版本锁**（闭包 5 包 ≈2.47 MB）→ 与"零依赖可移植"目标直接冲突；**`jsonschema` 的 `rpds-py` 也是 Rust**（❌）；唯一保住"纯 Python"的是 **`fastjsonschema`（1 包、26.8 KB、BSD-3）**。
- **★ `json-repair` 恰好制造 D-12① 要防的"静默回退"**：默认流程「先试 `json.loads()`，失败则回退修复解析器」且**回退透明**，**无 API 告诉你"修过没有"**，超级损坏时**返回空字符串**；README 自承把**合法** JSON 喂进去也可能"修"它并改结构。
- **LLMLingua 与 rule 83 是两个品类**：LLMLingua-2 是抽取式 token 剪枝（输出必是原文子序列），而 LC3 要**抽象重写的六字段摘要**——它的优点恰是它做不到的原因；另需 torch + 已停更 2.5 年。
- **D-13 直接回答**：证据支持"手写 20 行完胜引库"（`pyrate-limiter`/`limits`/`circuitbreaker` 分别在语义/依赖链/触发源上错位），**但手写必须自带自测用例**，否则就是第 8 个可能出假绿的脚本。

---

## 三、Round 2 你必须回答的五个焦点（P0/P1）

| # | 焦点 | 分歧现状 |
|---|---|---|
| **F1** | **P2 的范围与形态** | HT1：一条依赖链一次做完 ／ HT2：拆 P2a/P2b、4-6 轮 ／ HT3：只剩 cli 串联+自测网 ／ HT4：拆 P2.5/P3 按"能否离线验证"切 |
| **F2** | **D-11 LLM 调用层形态** | HT1/HT2：(a) 零依赖手写 ／ HT3：待定（先答"谁需要脚本自己调 LLM"）／ HT4：先探针 ／ **S2 新增：(d) vendor sseclient-py** |
| **F3** | **D-13 enforcement** | HT1：(a) 真熔断+P2 ／ HT2：(b)+(c)、真熔断推 P3 ／ HT3：驳→只告警 ／ HT4：改数据源为 provider usage + fail-closed ／ **S1：分母可从 /models 读** |
| **F4** | **D-12③ 分阶段温度** | HT1：挂 D-11 之上 ／ HT2：采纳+探针 ／ HT4：**驳回** ／ **S1 实证支持驳回（thinking mode 下 temperature 无效）** |
| **F5** | **D-02/D-03 是否升"框架级标配"** | HT1：(a) ／ HT2：(a)+校验器 ／ HT3：条件触发 ／ HT4：降级 B1（违反方案自己的判据 3） |

> **裁决纪律**：质疑与修订**必须引用 S1-S4 的具体条目**（写 `[S1]`…`[S4]`）；无新证据的立场翻转 = 不当翻转（K10），调度器打回。

---

## 四、Round 2 输出格式（每 HT 一份，落盘 `proposal_HTx_v2.md`）

**§A 信息引导（K11，先答后审）**
1. 我从我的视角看到、**别人可能还没考虑到的**关键信息或经验是什么？（≥1 条）
2. 我希望**哪个 HT** 回答我什么问题，才能补全我的判断？

**§B 交叉互审质疑**（对其他 HT 最可疑处，K3 六要素格式：问题/影响/等级/证据/建议/证据增益）
- 至少 2 条 P1+，**必须点名是哪个 HT 的哪条**。

**§C 回应与修订**
- 逐条列出"我 Round 1 立场 → v2 立场"，格式：`[条目] 原立场 → 新立场｜触发证据（引用 S1-S4 或某 HT 的质疑）｜翻转依据`
- **立场不变也要写"不变 + 为什么别人没说服我"**。

**§D 修订后的五个焦点结论**（F1-F5 各一句 + 置信度 高/中/低）
