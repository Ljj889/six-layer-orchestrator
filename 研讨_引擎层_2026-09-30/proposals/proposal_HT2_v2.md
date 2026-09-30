# HT-实现者 · Round 2（交叉互审 + 回应修订）

> 视角：可行性（技术坑 / 依赖 / 工期 / 成本 / Windows 环境现实）
> 纪律：**不许无证据翻转（K10）**。本文件的每一次立场变动都附 S1-S4 或实测命令结果；不动摇的都写"不变 + 为什么没被说服"。
> 本轮新增实测 8 条（编号 [复测1]…[复测8]），见文末《Round 2 实测证据附录》。

---

## §A 信息引导（K11，先答后审）

### A1. 我从实现者视角看到、别人可能还没考虑到的关键信息

**① 「谁调 LLM」这个问题决定了 D-11 的整个规模，而四家都没正面回答它。**
- 我 R1 实测：子 Agent 走 **WorkBuddy 原生 Agent 工具**调用 LLM，**绕过引擎**；rule 56 自己写明"当前 WorkBuddy 版由**提示词驱动**，迁移时替换为 Python 硬代码"。
- 推论：如果 P2 **不**把子 Agent 的 LLM 调用改成"走 `cli.py llm`"，那么引擎侧那套完整 SSE 客户端**几乎没有消费者**——唯一可能需要它的是 **rule 83 的 LC3 摘要**（compress）。
- 后果：一个"写了但没有调用点"的 LLM 层，正是框架 **rule 72「僵尸能力红线」**要防的东西。→ **D-11 的规模不是技术问题，是"调用方是谁"的架构问题**（HT3 在 F2 里问对了，但没人答）。

**② in-process 与 subprocess 的成本差是 13 倍，且会叠加。** [复测5]
- 实测：`subprocess` 转发一次 = **416 ms**；`import + 调 main()` = **31 ms**（[复测1]，0.031s）。
- 且 `six_layer_check.py` **内部自己还 spawn subprocess**（self-test 会起子进程）；subprocess 转发会**嵌套叠加**。
- 这个数字直接改变了我 R1 对 D-15 的建议（见 §C）。

**③ `/models` 给的是"天花板"，不是"本次消耗"——分母陷阱没被 S1 完全揭开。**
- S1 说"D-13 的预算分母可从接口读，不必硬编码"，**部分成立**：[复测8] 确认 `/models` 返回 `context_window=1048576`、`max_output_tokens=393216`、`effort.supported_levels=["low","high","max"]`。
- **但**：`context_window` 是**上限**，不是**会话实际消耗**。rule 83 的伴学教训**恰恰是**"分母用 API 上限 → 差 127 倍 → 永不触发"。→ 若把 `context_window` 当触发分母，就是**第 N 次重犯**。详见 F3。

### A2. 我希望哪个 HT 回答我什么

1. **问 HT3（用户）**：**过去 30 天框架被真实用了几次？**（HT3 自己的漏项①）——这是我 F1 工时账的**分母**，也是 D-11"值不值得做"的前提。没有这个数，"做不做 P2"无法收敛。
2. **问 HT1（设计者）**：D-02(c) 提前到 P2（`cli.py status append`），**是否接受我 R1 实测的"并发写丢更新"隐患**（`checkpoint.py:28-40` 是 `load→改→全量 save`）？若不接受，为什么敢提前？（详见 §B 质疑 1）
3. **问 HT4（风险官）**：D-11 的"无网不可自测"死结，是否接受我给的解法——**"录制真实字节重放（测逻辑）+ live smoke（测通道）"双轨，不算 mock**？（详见 §B 质疑 2）

---

## §B 交叉互审质疑（K3 六要素）

### 质疑 1｜点名 HT1：D-02(c) 提前到 P2，会把"并发写丢更新"引进 P2

- **问题**：HT1 主张把 D-02 的 (c)「状态板引擎化」**提前到 P2**（`cli.py status append|check`）。但 `status append` 写 `PROJECT_STATUS.md`，与 `checkpoint`/`lifecycle` 写 `progress.json` 是**同一种 read-modify-write 模式**——多窗口并行下**后写覆盖先写**。
- **影响**：状态板会在**最需要它的多窗口场景**下静默丢事件——恰好废掉它（D-02）存在的理由。
- **等级**：**P1**
- **证据**：[复测2][复测3] 全模块可 import 且顶层零副作用——但 **main() 内部**仍是 `load_state()→改内存→save_state()` **全量覆盖**（`checkpoint.py:28-40`、`lifecycle.py:56-69`）；`checkpoint.py:38-40` 的 save 是 `path.write_text(...)`，**非原子**。多窗口是框架核心场景（D-02/D-03 因此而生，task-brief §1）。
- **建议**：若提前，**必须同批**给状态板写路径加 **`os.replace()` 原子写 + append-only 事件日志**（事件只追加、不覆盖）。
- **证据增益**：避免把并发 bug 提前一期固化——否则 P2 交付的"状态板"反而是新的假绿源。

### 质疑 2｜点名 HT4：D-11"与 D-04 冲突"是 P0——但有解，且不违反 D-04

- **问题**：HT4 说"D-11 无网不可自测，唯一自测办法是 mock socket = 正好违反刚立的 D-04（通道不可 mock）"。这个观察**方向对**，但**结论过强**——它把"录制的**真实字节**重放"和"**伪造平台通道**"混为一谈。
- **影响**：若按 HT4 结论把 D-11 推后/砍掉，会**连带砍掉 rule 83 LC3 的唯一实现路径**（compress 的 LLM 层）。
- **等级**：**P1**
- **证据**：D-04 的原文边界是"**平台通道**（`plus.android` 等）替身 = 伪造被测对象 = 假绿"。HTTP 客户端天然分两层：**通道**（socket/TLS/代理）+ **逻辑**（SSE 解析/重试/usage 提取）。我 R1 已实测拿到**真实 SSE 字节**（[附录E]：11 帧、`data: {json}`、`[DONE]`、usage 在末帧）；[复测8] 又拿到真实 `/models` JSON。→ 这些**真实捕获**可固化为 fixture，重放它测**逻辑**；**通道**另做 **live smoke**（我实测 0.4–0.8s 通过）。
- **建议**：D-11 自测 = **fixture 重放（测逻辑，必跑，离线）+ live smoke（测通道，不可达则 skip 记未验证）** 双轨。**录制的真实响应不是 mock**。
- **证据增益**：解开 HT4 的 P0 死结，让 D-11 **可离线测**，而非"不能测所以不做"。

### 质疑 3｜点名 HT1：D-12③"挂 D-11 之上"，挂的是**死代码**

- **问题**：HT1 主张 D-12③（分阶段温度）"挂 D-11 之上（先有调用层再谈温度）"。但 [S1] 给出**官方原文级**证据：`temperature` "Has no effect in thinking mode"，而 **thinking 默认 enabled**。
- **影响**：把一条**必然静默失效**的能力挂进依赖链，会污染 P2 的验收口（且它长得像"有效功能"）。
- **等级**：**P1**
- **证据**：[S1] 官方原文；[复测8] 我的机器补证——`/models` 返回 `effort.supported_levels=["low","high","max"]`，`models.json` 注册 `supportedEfforts=["high","max"]` → **有效的档位旋钮是 `reasoning_effort`，不是 temperature**；[S4] "`assert` 可被 `-O` 关掉"是同类静默失效；rule 83"分母错死代码"是框架自己的先例。
- **建议**：D-12③ **改机制**：驳回 temperature，改用 `reasoning_effort`——分阶段 = `high`（框架/拆解、求稳）vs `max`（反思）。
- **证据增益**：把一条死代码换成**经过接口实证**的有效机制。

---

## §C 回应与修订

### C1. 立场变动（每条附触发证据）

- **[D-15 cli.py 形态]** 原：**subprocess 转发** → 新：**in-process 包裹（`import` + argv 置换 + 归一化）**｜触发证据：[S3]（7 模块 import 0.032s、顶层零副作用）+ **[复测1]**（0.031s，全部有 `if __name__=="__main__"` 守卫）+ **[复测3]**（顶层无 `main()`/`sys.exit`）+ **[复测4]**（main() 契约：**成功返回 None；失败 `SystemExit(1)`；six_layer_check 成功 `SystemExit(0)`**）+ **原型实测 [复测9]**（6/6 保住 Gate 退出码）+ **[复测5]**（subprocess 416ms vs in-process 31ms）｜**翻转依据**：HT2-R1 说"main() 直接 sys.exit **不可 import**"**不精确**——模块**可以** import；我真正担心的是"main() 契约不一致导致 Gate 语义丢失"，而 S3 已把它定位、我用**原型证明 ~10 行归一化可解决**。**这是证据迫使我改，不是附和**。
  - **保留警示**（未消解）：必须**捕获 SystemExit + None→0**，且必须有一条 **cli 级自测**证明"失败命令 → cli 返回 1"。否则就是 S3 说的"**永远返回 0，Gate 语义直接失效**"。

- **[D-11 形态]** 原：**(a) 零依赖手写** → 新：**(d) vendor `sseclient-py`（仅 SSE 解析）+ 自写重试/超时/代理/usage/`/models` 核对**｜触发证据：[S2]（Apache-2.0 / 8.2KB / 纯 Python 单文件 / 0 运行期依赖 / 源码只 `import logging` / 自带忽略 `: keep-alive` 注释行）+ [S1]（keep-alive 是**注释行**，手写易漏）｜**翻转依据**：SSE 规范的边界（多行 data / 注释行 / 空行分派）正是**手写最容易静默错解析**的地方——即框架最怕的失效类型；vendor 一个已审计的 0 依赖单文件，**审计成本 < 手写错解析的风险**。
  - **但成本影像不变**：vendor 只省"解析"（~40-80 行），**不省**我 R1 指出的成本大头（重试/退避/代理/超时/usage 提取/`/models` 双向核对）→ **F2 的工时几乎不变**。
  - **前提**：vendor 必须**冻结**（保留 LICENSE + 版本钉 + `# vendored from sseclient-py@x.y, DO NOT EDIT` 标记），**不得**变成 pip 依赖。

- **[D-12③ 分阶段温度]** 原：采纳 + 探针 → 新：**驳回 temperature，改 `reasoning_effort`**｜触发证据：[S1]（官方原文）+ [复测8]（接口有 effort 字段）｜**翻转依据**：S1 是官方原文级证据，我机器补证接口有 `effort` 旋钮；这是"探针"的**结果**，不是放弃探针。

- **[D-02/D-03 升框架级标配]** 原：(a) + 校验器 → 新：**(a) 降级为"模板 + 规则 + 条件触发"，标 `[假设]`**（多窗口项目才建，不"每个项目根自动建"）｜触发证据：HT4 质疑（违反判据 3）+ HT3（样本=1）+ task-brief §4.3 **判据 3**（跨项目成立吗）+ task-brief §2.8（样本=1）｜**翻转依据**：判据 3 是**本方案自己列的判据**，"框架级标配"在 sample=1 下是**过度声称**；但"推荐模板 + 规则"仍成立，故**非全驳，是降级**。

### C2. 立场不变（+ 为什么别人没说服我）

- **[D-13 enforcement]** 维持 **(b) 告警 + (c) 问人；真熔断推 P3**｜**未被说服的原因**：HT1"真熔断 + P2"**没有提供新证据**反驳我 R1 的"三前提一条都不成立"（真实 usage 回写 / 校准窗口 / 调用必经引擎）。HT4"分母改 provider usage"我**接受为补充**（我 R1 已把"真实 usage 回写"列为前提），但那**正说明前提尚未具备**，反而支持"推 P3"。**部分吸收 S1**：分母可从 `/models` 读**上限**——但见 F3 的陷阱。

- **[F1 P2 工时 4-6 轮]** 维持（细化为 5-6 轮）｜**未被说服的原因**：HT1"一条链一次做完"讲的是**顺序**，我讲的是**规模**，两者不矛盾。S3 把 cli.py 成本降了约 0.25 轮（我认账），但 **LLM 层的 retry/proxy/timeout/usage/核对成本未变**——无人拿出"更小"的证据。

- **[D-05 / D-06 / D-07 / D-12①② / D-17 / D-18 / D-19 / D-21 / D-22]** 维持 R1 结论｜**未被说服的原因**：无人针对这些条目提出新证据；其中 D-12①（需 Phase 级状态）、D-12②（防分发漂移）经 [复测1-3] 复核仍成立（模块可 import，但 Phase 概念确实不在 `progress.json` 里）。

---

## §D 修订后的五个焦点结论

### F1｜P2 的范围与形态：**接受 HT1 的依赖链顺序，但坚持"拆 P2a/P2b"** ｜置信度：**中高**

**依赖链形状（收 HT1）**：`token_ledger（新建）→ D-11 → {D-12③', D-13, compress-LC3}`；`cli 包裹` 与 `route_error` 是**旁支**（不挂在脊上）。

**真实工时账（逐环节，依据 = 代码形状 + 接口实测 + D-16 硬 Gate 的 fixture 乘数）**：

| 环节 | 内容 | 工时 | 依赖 | 能否离线验证 |
|---|---|---|---|---|
| **L0 token_ledger** | 机读 token 账本：读 `/models` 取**上限**，从响应 `usage` 回写**实际** | **0.5 轮** | — | ✅ 可（用 [复测8] 真实 JSON + R1 真实 usage fixture） |
| **L1 D-11 LLM 层** | vendor SSE 解析 + 自写 retry/退避/代理/超时/usage 提取 + `/models` 双向核对 | **1.5 轮** | L0 | ✅ 部分（逻辑 fixture 重放；通道 live smoke） |
| **L2 D-12③'** | ~~温度~~→ `reasoning_effort` 分阶段 | **0.2 轮** | L1 | ✅ 可 |
| **L3 D-13 enforcement** | 累计用量查表 + 超限问人 | **0.5 轮** | L0+L1 | ✅ 可 |
| **L4 compress（rule 83）** | LC1/LC2 无 LLM（便宜）+ LC3 摘要（吃 L1） | **1.0 轮** | L1 | ⚠ LC3 需 LLM |
| **L5 D-14 route_error** | 纯规则函数 + 最小回归集 | **0.5 轮** | 独立 | ✅ 可 |
| **L6 cli 包裹** | in-process 归一化 + `--project` 适配 + 编码/退出码自测 | **0.5 轮** | 可先做（原型已验证 [复测9]） | ✅ 可 |
| **L7 自测网扩项** | 新命令 × 正/反/边界 fixture | **0.5–1.0 轮** | 全程 | ✅ 可 |
| **合计** | | **5–6 轮** | 串行脊 L0→L1→{L2,L3,L4} | |

**判据（借 HT4 的"能否离线验证"，我把它变成可执行）**：
- **必须先做**：**L0 + L1**（脊；L2/L3/L4 全挂在它们上）。
- **可以推迟**：**D-13 真熔断（→P3）**、**L4 的 LC3 摘要**（compress 的非 LLM 部分可先交）。
- **P2a = L0 + L1 + L2 + L5 + L6 + L7（全部可离线 fixture 验证）**；**P2b = L3(告警/问人) + L4**（吃 L1，但 LC3 依赖真网络）。
- **拆的理由**：HT1 的"一次做完"会让**不可离线验证的 LC3**卡住可交付的 P2a。

### F2｜D-11 形态：**(d) vendor（仅解析）+ 自写其余** ｜置信度：**中（卡在一个没人答的问题上）**

- **技术判断**：vendor `sseclient-py`（[S2]：Apache-2.0/8.2KB/0 依赖/单文件）**略优**于纯手写——SSE 边界解析是手写最易静默出错处；但**收益有限**（只省解析那 ~40-80 行），成本大头（retry/proxy/timeout/usage/核对）**照样自己写**。
- **规模判断（更关键）**：真正决定 D-11 大小的是 **A1①「谁调 LLM」**：
  - 若 **Agent 继续走原生工具**（现状）→ 引擎 LLM 层**只有 compress-LC3 一个消费者** → 应**大幅缩水**为"one-shot 非流式 + usage 提取"，完整 SSE **可能是 rule 72 僵尸能力**。
  - 若 **P2 要子 Agent 改走 `cli.py llm`** → 才需要完整 SSE。**这是架构决策，不是技术选型**。
- **我的主张**：**先把 L1 缩到"能支撑 compress-LC3 的最小形态"**（非流式 one-shot 即可），SSE 流式**等"谁调"有答案再加**。→ 若如此，L1 工时从 1.5 轮降到 **0.75 轮**。

### F3｜D-13 enforcement：**能读接口拿"天花板"，但拿不到"本次消耗"** ｜置信度：**高**

- **S1 对了一半**：`/models` 确实给分母来源（[复测8]：`context_window=1048576`、`max_output_tokens=393216`、`effort.supported_levels`）。
- **但**：那是**上限**，不是**会话实际消耗**。**触发分母必须用"校准窗口"，禁用 `context_window`**——否则**重犯 rule 83**（伴学：分母用 API 上限 → 差 127 倍 → 永不触发）。
- **实际消耗的唯一可信来源 = 每次响应的 `usage`**（[复测8]+R1）：注意 [S1] 指出 **usage 无独立块**（附在**最后内容块**），照抄 OpenAI 的 `choices:[]` 判据会**漏**——我 R1 实测同为"usage 在末帧内容块"。→ 解析器必须**从最后一个非-DONE 内容帧取 usage**。
- **落地**：token_ledger = **`/models` 取上限（做硬天花板告警） + `usage` 回写取实际（做校准窗口分母）**，两者**不能互换**。

### F4｜D-12③ 分阶段温度：**驳回，改 `reasoning_effort`** ｜置信度：**高**

- [S1] 官方原文 "Has no effect in thinking mode" + thinking 默认 enabled → temperature 方案是死代码。
- [复测8] 接口实证有效旋钮是 `effort.supported_levels=["low","high","max"]`，`models.json` 注册 `["high","max"]` → **分阶段 = `high`（框架/拆解）vs `max`（反思）**。
- **注**：`/models` 说支持 `low`，`models.json` 只列 `high/max`——**两者不一致，落地前须再核**（登记为 P2 待核项）。

### F5｜D-02/D-03 是否升"框架级标配"：**降级为"模板 + 规则 + 条件触发 + `[假设]`"** ｜置信度：**中高**

- **答 HT4**：你说它违反判据 3——我**同意**，因为判据 3 是**本方案自己列的**，而样本=1 是事实 → "框架级标配（每个多窗口项目根自动建）"是**过度声称**。
- **答 HT3**：你的"条件触发"我**部分采纳**——触发条件 = **检测到多窗口/多 Agent 并行**才建；单窗项目不建。
- **保留**：**模板 + 规则**仍应进 `references/`（零成本、纯提示词件），只是**标 `[假设]`**、不声称"标配"。→ 即 **D-02：P1 出模板+规则（`[假设]`）｜D-03：同上，条件触发**。**引擎化（D-02-c）不进 P2**（见质疑 1 的并发隐患）。

---

## Round 2 实测证据附录

**[复测1] 7 模块一次性 import（裁决 S3 vs HT2-R1 的表面矛盾）**
```
python -c "import sys; sys.path.insert(0,'scripts'); import checkpoint,cost_log,lifecycle,runtime_probe,read_knowledge,validate_output,six_layer_check"
→ import OK elapsed=0.031s    EXIT=0
```
**裁决**：扫描员 B **对**——7 模块**可** import。我 R1 "不可 import"**表述不精确**；我的真实保留点是"main() 契约"，见 [复测4]。

**[复测2] `__main__` 守卫**：7 个脚本**全部**有 `if __name__ == "__main__":`（checkpoint:137 / cost_log:203 / lifecycle:172 / runtime_probe:159 / read_knowledge:139 / validate_output:96 / six_layer_check:1636）。

**[复测3] 顶层副作用**：脚本内**无**顶层 `main()`/`sys.exit` 调用（全在 `__main__` 块内）→ 顶层零副作用，与 S3 一致。

**[复测4] main() 契约（决定 cli 包裹写法）**——import 后直接调 `main()`：
```
checkpoint 成功        → 返回 None（隐式 0）
checkpoint 失败(非法状态) → SystemExit(1)
cost_log   成功        → 返回 None
cost_log   失败(非法档位) → SystemExit(1)
lifecycle  失败(非法转移) → SystemExit(1)
six_layer_check 成功   → SystemExit(0)
```
→ **契约不一致**：成功多为 `None`，失败全 `SystemExit(1)`，而 `six_layer_check` 成功也 `SystemExit(0)`。**S3 的警告成立**：不归一化 → cli 永远返回 0。

**[复测5] subprocess vs in-process 开销**：`subprocess` 转发 `checkpoint status` = **416 ms/次**；in-process import+调用 = **31 ms**（13×）。

**[复测6] `-O` 关掉 assert（S4 正确）**：`python -c "assert False"` → exit 1；`python -O -c "assert False"` → **exit 0**（被静默关掉）。

**[复测7] 现有脚本无裸 assert（S4 正确）**：`grep -nE "^\s*assert " scripts/*.py` → **无命中** ✓。

**[复测8] `/models` 富字段（F3 依据）**：`id=deepseek-flash, context_window=1048576, max_output_tokens=393216, effort.supported_levels=["low","high","max"], default_level="high", api_capabilities.anthropic_messages...`。

**[复测9] in-process 包裹原型（直接裁决 D-15）**——`importlib.import_module` + `sys.argv` 置换 + `try: mod.main() except SystemExit` + `None→0`：
```
checkpoint 成功        exit=0 ✓期望0
checkpoint 失败(非法状态) exit=1 ✓期望1
cost_log   成功        exit=0 ✓期望0
cost_log   失败(非法档位) exit=1 ✓期望1
lifecycle  失败(非法转移) exit=1 ✓期望1
six_layer_check 成功   exit=0 ✓期望0
→ 6/6 保住 Gate 语义
```
→ **in-process 包裹可行**，代价 = ~10 行归一化 + 1 条 cli 级退出码自测。

---

## 一句话总结

**对 F1 的最终主张**：P2 是一条**串行脊** `token_ledger → D-11 → {D-13, compress-LC3}` + 两条旁支（cli 包裹、route_error）；**必须拆 P2a/P2b**——P2a 只交"能用真实录制 fixture 离线验证"的部分（L0/L1/L2/L5/L6/L7），把依赖真网络的 LC3 与真熔断留给 P2b/P3。**工时 5-6 轮**。

**还剩哪些未消解分歧**：
1. **「谁调 LLM」（A1①）—— 无人回答**。它决定 D-11 是"完整 SSE"还是"缩水 one-shot"（可能差 0.75 轮 + 一个僵尸能力）。**卡在 HT3**。
2. **真熔断是否 P3**——HT1"真熔断+P2" vs 我"推 P3"；需 HT1 正面回应"三前提（真实 usage 回写/校准窗口/调用必经引擎）当前一条都不成立"。
3. **cli 形态 in-process vs subprocess**——我用 6/6 原型证明 in-process 保得住 Gate 语义且快 13×；但若 HT4 坚持"隔离/故障不污染主进程"的顾虑，需其给证据。
