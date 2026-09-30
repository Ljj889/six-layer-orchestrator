# HT-实现者 · Round 1 独立盲写提案

> 视角：可行性（技术坑 / 依赖 / 工期 / 成本 / Windows 环境现实）
> 默认立场：专挑「做不出来 / 做歪 / 工时被低估」
> 纪律：默认怀疑其他人的推理，只有证据迫使我同意时才同意。本提案所有工期与风险判断**尽量附实测证据**，见文末《实测证据附录》。

---

## §0 退一步

这个方案真正要解决的是：**把「靠 Agent 自觉遵守 SKILL.md」里能被机械判定的那部分，下沉成 Python 脚本硬闸**，让「跑一下就知道缺什么」替代「多轮对话里被稀释的记忆」。它**不是**要造平台——上限明确锁在「规则层 + 引擎层」，UI/多租户/计费全砍（D-17/D-19/§七）。

作为实现者，我的核心判断是：**方案方向对，但「零依赖」四个字被当成了免费午餐**。实测证明零依赖 SSE 客户端**本机能跑通**（0.4–0.8s 拿到流，见附录 E），所以我**不用"做不出来"来反对它**；我要反对的是原文档的**成本影像**——它把"SSE 本来就要自己写"当成轻描淡写，而真正的成本大头是**重试/退避/代理/超时/容错/无 tokenizer**这六块，原文档一块没提。同时 P2 被写成"2-3 轮"，按我的拆解它含**强串行依赖**（LLM 层 → usage 回写 → enforcement → compress 复述测试），真实工时**4-6 轮**，**P2 是会爆炸的那一期**。

什么情况下这个方案会失败：① 把「调用前 enforcement」（D-13）当 P2 硬做，但真实 usage 回写、校准窗口、调用必经引擎三个前提**一个都不成立** → 做出"假熔断"，比没有更危险；② 把 `cli.py`（D-15）当"import 一下 7 脚本"来估工时，忽略三者调用约定不同 → 返工；③ 把"分阶段温度"（D-12③）当免费，但 DeepSeek reasoning 模型可能忽略 temperature → 与 rule 83「分母错」同类的**静默失效**死代码。

---

## §1 逐条裁决表（D-01…D-22 全覆盖）

| 编号 | 我的结论 | 一句理由 | 若"改"→改成什么 |
|---|---|---|---|
| **D-01** | 采纳(a) | 纯规则，零技术成本；但"变成单测断言"需测试载体 | 补硬话：**测试载体必须是 stdlib（unittest 或纯 assert 脚本），禁止把 pytest 提为前置依赖**（违零依赖） |
| **D-02** | 改：P1 采纳(a)，P2 只做**校验器**、不做**生成器** | 脚本**无法知道**"用户做没做某动作"，只能判断"文件改没改"；"自动生成事件流"是伪需求 | (c) 降级为「结构完整性 + 事件流 append-only（单调不减）校验」；"自动生成"删掉 |
| **D-03** | 采纳(a) | 纯提示词件，无技术坑 | 模板进 `references/` 时**给最小骨架**，防每次从零写（否则确认疲劳） |
| **D-04** | 采纳(b) | 它确是"假绿家族"成员，并进 rule 79 语义最顺 | framework-skills 的"接缝替身模板"**只留一份**，防文件膨胀 |
| **D-05** | 采纳(a) | **已有引擎底座**（product-assert 命令实测在册），只需扩规则表述 | P2 给 product-assert 增「0 字节 → SKIP/FAIL 区分」用例（"拿不到字节记跳过"需引擎支持） |
| **D-06** | 采纳(a) | 纯规则，零成本 | 无 |
| **D-07** | 采纳(b) | cost_log 是定长行（已 9 列），再加第 10 列会继续膨胀；references 轻量做法正确 | 无 |
| **D-08** | 采纳(a)，**强支持** | 实测 banner 行 32–40 共 **8129 字符**，行 1–41 共 **12658 字符**（见附录 A），淹正文属实 | **必须连带改 `sync_to_platforms` 的文件数白名单**——新增 `CHANGELOG.md` 会让"逐目录文件数"校验红（见质疑 2 附带） |
| **D-09** | 改：采纳(a) + 降级留痕，但**判据以探针实测为准** | 实测同一 `bash`：**交互 Git Bash 可用**（`bash -n` OK），但 **python subprocess spawn bash 被沙箱拦**（wsl.exe blacklist，见附录 B）→ "工具在不在 PATH"不等于"能不能用" | 给 `runtime_probe` **加 bash 探针**（现在只有 node/python/py_launcher）；降级判据 = 探针结果，不靠 `which` |
| **D-10** | 改：P1 采纳；**P2 范围砍半、工期翻倍**；P3 同意后置 | P2 "2-3 轮"**严重低估**；真实 **4-6 轮**（拆解见 §2 质疑 2） | P2 拆两批：**P2a**（cli.py 转发 + LLM 层 + route_error + 自测网）先交；**P2b**（enforcement/compress/design）**待前置满足再排** |
| **D-11** | 采纳(a)，**但纠正成本影像** | 零依赖 SSE **实测能跑**（附录 E）；但"自己写"的**大头**是重试/退避/代理/超时/容错/无 tokenizer，非 SSE 解析 | ① 明确"零依赖"= 允许 **env proxy + 系统证书**，须处理"有/无/代理挂"三态；② **`/models` 双向核对升为硬 Gate**（附录 D 活体：200 假绿） |
| **D-12** | 采纳，但**三条各自改** | ① 需 Phase 级状态（现无）；② 零依赖下意义在"防分发漂移"非"防 import"；③ 温度是否生效**未验证** | ① 落地前把 **Phase 级状态**写进 `progress.json`；② 目标重定义为「防分发副本漂移」；③ 加**温度生效性探针**，不生效则不做 |
| **D-13** | **改：P2 只做 (b)+(c)，真熔断(a) 推迟** | 真熔断需"真实 usage 回写 + 校准窗口 + 调用必经引擎"**三条同时成立**，现在**一条都不成立** → 做出的是假熔断 | P2：(b) 告警 + (c) 超限问人；**真熔断列 P3**，且分母**禁用 API 上限**（防重犯 rule 83"分母错 127 倍"） |
| **D-14** | 改：采纳(a) 但**缩小范围** | route_error **函数本身极简单**；真成本在**人工标注回归集**（脏活）且样本可能很少 | 先做"关键词→角色"函数 + **5-10 条**最小回归用例；全量伴学 FAIL 回归集**列 P2 末或 P3** |
| **D-15** | 改：采纳"串联"，但**用 subprocess 转发** | 实测 7 脚本有**三种调用约定**（verb-first / dir-first / argparse，附录 C），且 main() 直接 `sys.exit` **不可 import** | cli.py = **subprocess 转发器**（不改脚本，合"只加不改"）；`design/compress` **先定 schema 再排期**，无 schema 不排 |
| **D-16** | 采纳(a)，但**加一条硬纪律** | 硬 Gate 对，但 LLM 层用例若打真网络则**不可移植**（违 D-20） | 硬纪律：**新命令自测必须能离线**；LLM 层用例用 **fake SSE 字节流**喂解析器，**禁止 self-test 打真网络** |
| **D-17** | 采纳(a) | UI 不产生闸的价值，判断对 | cli.py 须支持**从任意 cwd 调用**（用 `--project` 显式传参，别靠 cwd 推断） |
| **D-18** | 采纳(a) | 不止"人可读"——**规则下沉进代码会让每次改规则都变成"改码+跑自测+三平台同步"**，迭代变慢 | 无 |
| **D-19** | 采纳 | 隔离成本低（每项目已自持 progress.json/cost_log.md） | **补一条**：同项目内**多脚本并发写** `progress.json` 会丢更新（见 §4） |
| **D-20** | 改：采纳(b) 纪律，但**重定义边界** | 实测本机 `models.json` **明文存 apiKey**（附录 D）——"输入源无凭据"在本机**做不到** | 改为「**引擎输出物无凭据**」：cost_log/日志/progress **绝不写 key + 日志脱敏**（key 前缀打码）；输入源允许读 models.json/环境变量 |
| **D-21** | 采纳(a) | 流程件，零技术成本；本轮自己就是这个流程的实例 | 无 |
| **D-22** | 采纳(a)（(b) 列 P3 正确） | (b) 极简入口是**给一个已经能用的东西造新壳**——"说一句记一下"已是零成本入口 | 无 |

**小结**：22 条中，**采纳 13、改 9、驳 0、待定 0**。改动集中在 B 组（D-10/11/12/13/15/16）——**正是引擎层本体**，说明原文档的**方向对、工时与前提错**。

---

## §2 我的三条最强质疑（K3 六要素）

### 质疑 1｜D-13「调用前 enforcement」在三个前提全不成立时是"假熔断"，比没有更危险

- **问题**：原建议"(a) 默认拦截 + (c) 超限问人"。但"调用前查累计用量"要成立，必须同时满足：① 有**真实 token 回写**；② 预算是按**校准窗口**算的；③ 调用**必经引擎**。三条现在**一条都不满足**。
- **影响**：做出一个"永远不触发"或"拦不住真实调用"的假熔断，还会让调度器产生**"已熔断"的错觉** → 比不做更危险（同类于 rule 83 死代码，只是这次死的是熔断）。
- **等级**：**P1**（阻断 P2 验收）
- **证据**：
  1. 实测 `cost_log.py:58` 记录的是**字符串** `预估成本`，**不是**真实 token；`add` 的 cost 参数是任意字符串，无校验（`cost_log.py:43-63`）。
  2. rule 83 的**伴学先例**：分母用 API 上限 → 与真实会话差 **127 倍** → 压缩永不触发。D-13 若照抄"预算"字面、用 API 上限做分母，**必然重犯**。
  3. 本机 `~/.workbuddy/models.json` 只有 1 个模型；子 Agent 走 **WorkBuddy 原生 Agent 工具**调用，**不经过 cli.py** → 引擎**拦不住**。
- **建议**：P2 只做 **(b) 告警 + (c) 超限问人**；真熔断 **(a) 推迟到 P3**，且开通条件写死为"三条同时成立"；一旦做，**分母禁用 API 上限**，用校准窗口。
- **证据增益**：省掉一整轮"做了假熔断 → 验收发现拦不住 → 返工"的浪费。

### 质疑 2｜D-15「cli.py 串联 7 脚本」不是 import 是**适配三种调用约定**，`design/compress` 还缺前置规格

- **问题**：7 脚本**调用约定不统一**（实测附录 C），且每个 `main()` 直接 `sys.exit()`、**不可被 import 复用**。原建议"先做串联"把复杂度压成一句话；`design --finalize`（设计锁定 Gate）的**校验对象 schema 不存在**，`compress` 的复述测试（rule 83 §8 自认"尚无脚本化实现"）**依赖 LLM 调用层**。
- **影响**：cli.py 不是 0.5 轮而是 **1 轮+**；`design/compress` 若强上会做成**空壳命令**（有命令名、无实质校验），污染命令面。
- **等级**：**P1**
- **证据**（实测）：
  - `six_layer_check.py`：**手写 argv**，verb-first（`six_layer_check.py:1506` `argv = sys.argv[1:]`，verb 白名单硬编码在 1510 行）。
  - `checkpoint.py` / `cost_log.py` / `lifecycle.py`：**dir-first**（`<项目目录> <cmd>`，`checkpoint.py:118`）。
  - `runtime_probe.py` / `read_knowledge.py`：**argparse**（`runtime_probe.py:141`）。
  - 全部 `main()` 结尾 `sys.exit(...)` → import 后无法拿返回值，只能 subprocess。
  - `design` 命令：现有 7 脚本**没有任何设计产物 schema/校验器** → 要从零设计。
- **建议**：cli.py 用 **subprocess 转发**（`encoding="utf-8"` 必须显式，见 §4；exit code 透传；统一 `--project` 参数翻译成各脚本 argv）；`design/compress` **拆出"先定 schema 再实现"**，无 schema 不排期。
- **证据增益**：避免 cli.py 返工 + 避免两个空壳命令进命令面。

### 质疑 3｜D-11 的"探活"必须是**硬 Gate**——我实测到了"200 假绿"活体

- **问题**：原文档把"模型 id 探活前置"列为 D-11 的**待定细节**（一句"必须打 /models 白名单核对，防 200 假绿"）。实测证明：**不核对就一定会跑错模型且显示绿灯**；而 D-12③"分阶段温度"是否生效**根本没验证**。
- **影响**：① 引擎"以为在跑 A 模型，实际跑 B"；② 分阶段温度可能是 rule 83 同类的**静默失效死代码**。
- **等级**：**P1**
- **证据**（实测，附录 D）：
  - `/models` 白名单**只有 2 个 id**：`deepseek-flash`、`deepseek-v4-pro`。
  - 提交 **`deepseek-v4-flash`**（**不在白名单**，但**正是 `models.json` 里注册的 id**）→ **HTTP 200**，且响应 `model` **静默变成** `deepseek-flash`。
  - 即：**请求 id 不在白名单，服务端不报错、静默回落** → 这就是"200 假绿"。
- **建议**：
  1. `/models` 核对写成**双向硬 Gate**：`请求 id ∈ 白名单` **且** `响应 model == 请求 id`；启动时探活，不一致即 FAIL（不静默）。
  2. 修 `models.json` 的 id 或引擎做**别名映射**（`deepseek-v4-flash → deepseek-flash`）。
  3. 温度先做**生效性探针**，确认 DeepSeek 不忽略 temperature 再谈分阶段。
- **证据增益**：直接暴露一个真实"200 假绿"，把"待定细节"升为"必做硬 Gate"。

---

## §3 开源复用视角（我的角色下最该复用 / 最该自建）

1. **最该自建**：**SSE 客户端 + usage 回写 + `route_error()`**。这是框架的核心资产，且零依赖路径**实测可行**（附录 E）；外借会引入依赖与语义错配。但**范围要认清**——手写量约 **300-500 行 + 边界用例**（重试/退避/代理/超时/容错），不是"SSE 解析那 40 行"。
2. **最该复用（stdlib）**：**`argparse`** 统一新命令面（现 7 脚本解析风格三分裂，新 cli.py 用 argparse，零依赖）；**`unittest`** 做新命令自测（现 self-test 是自写的 `add(name, ok)` 累加器，非标准框架——**只加不改**，新命令才用 unittest）。
3. **最该"延迟决策"**：**tokenizer**。零依赖下**无可信 token 计数**（DeepSeek 非 tiktoken）。D-13 精度、rule 83 触发判据都吃这个。建议走 **D-11(c) 混合**：探测到 tiktoken 就用、没有就 `len/4` 粗估——**但粗估误差要在报告里显式标注**，防"看起来精确其实瞎猜"。
4. **最该"只借鉴不引依赖"**：**httpx / requests 的超时与重试参数模型**（连接超时 vs 读超时的区分）。urllib 的 `timeout` 是 **socket 级**，流式长响应期间**无数据就会误超时**——这是零依赖 SSE 的真坑，要照抄成熟库的"分读超时"思路自己实现，但**不引库**。

---

## §4 我认为原文档漏掉的议题（3 条）

### 补充 1｜同项目内多脚本**并发写**会丢更新（原子写缺失）

- **现状**：`checkpoint.py` / `lifecycle.py` 都是 `load_state() → 改内存 → save_state()` **全量覆盖**（`checkpoint.py:28-40`、`lifecycle.py:56-69`）。两个窗口/两个脚本**同时** `mark`/`transit` → **后写覆盖先写**，静默丢状态。
- **为什么本轮该提**：D-19 只谈"**项目间**隔离"，没谈"**同项目内**并发写"。而本框架**核心场景就是多窗口并行**（D-02 状态板、D-03 交接件都为此而生）。
- **建议**：写入走**「写临时文件 + `os.replace()` 原子替换」**（stdlib，零依赖）；或加**文件锁**。低成本，P2 顺手做。

### 补充 2｜cli.py 转发时的**子进程编码**（Windows GBK）

- **现状**：各脚本已加 `_force_utf8_stdio()`（`cost_log.py:161` 等），但那只管**脚本自身的 stdout**。cli.py 若用 `subprocess.run(..., capture_output=True)` **不显式 `encoding="utf-8"`**，Windows 默认 GBK 会**把转发内容变乱码**。
- **建议**：cli.py 所有 subprocess 调用**必须** `encoding="utf-8", errors="replace"`（与 `runtime_probe.py:42-43` 一致）。

### 补充 3｜**token 预估缺失**是 D-11/D-13/compress 三条的**共同隐含前提**

- **现状**：零依赖无 tokenizer；但 D-13 要"预算"、rule 83 要"触发判据"、LC3 摘要要"控制长度"——**全都要 token 数**。原文档当它是免费的。
- **建议**：把它显式登记为**横切前提**，P2 明确"**粗估 + 标注误差**"的降级方案，别让它变成三条功能下的静默地雷。

---

## 实测证据附录（我的差异化凭据）

> 全部在本机实跑，Python `C:\Users\one\.workbuddy\binaries\python\versions\3.14.3\python.exe`（另有 3.13.12）。命令与结果摘要如下。

**A. 环境与脚本现状**
- 3.14.3 `import urllib.request/argparse/json/ssl/http.client/unittest` 全 OK；`py_compile scripts/*.py` 全 OK。
- `six_layer_check.py self-test`：**26 PASS / 0 FAIL / 1 SKIP**（3.14.3 与 3.13.12 **结果一致**）。1 SKIP = `sync_to_platforms.sh` 的 `bash -n`「bash 不可用（WSL 无发行版 / 无 Git Bash）→ 记未验证」。
- `SKILL.md`：**总 525 行**；banner **行 32–40 = 8129 字符**，**行 1–41 = 12658 字符**。
- `read_knowledge.py "checkpoint" --top_k 2` → 命中 1 条 active 资产（`rules/R-005_checkpointer_transactional.md`）→ 该脚本**现状可跑**。

**B. 沙箱分层（D-09 的关键证据）**
- 交互 Bash（Git Bash）里 `bash -n sync_to_platforms.sh` → **OK**。
- 但 python 子进程 spawn bash 时被沙箱拦（`wsl.exe` 在 Program Blacklist）→ self-test 记 SKIP。
- 结论：**"工具能不能用"是分层/分父进程的，不能靠 `which` 判定**。

**C. 三种调用约定（D-15 的关键证据）**
- `six_layer_check.py`：手写 argv，**verb-first**（`argv=sys.argv[1:]` + verb 白名单硬编码，`six_layer_check.py:1506-1520`）；**不用 argparse**。
- `checkpoint.py:118` / `cost_log.py:177` / `lifecycle.py:139`：**dir-first** `<项目目录> <cmd>`。
- `runtime_probe.py:141` / `read_knowledge.py:119`：**argparse**。
- 全部 `main()` 以 `sys.exit()` 收尾 → 不可 import 复用。

**D. DeepSeek API 实测（"200 假绿"活体）**
- `GET /models` → HTTP 200，白名单**只有 2 个**：`deepseek-flash`(ctx 1048576, out 393216)、`deepseek-v4-pro`。
- `POST /chat/completions` 提交 **`deepseek-v4-flash`**（不在白名单）→ **HTTP 200**，`response.model = "deepseek-flash"`（**静默回落**）。
- 本机 `~/.workbuddy/models.json` 注册的 id 正是 **`deepseek-v4-flash`**（**与白名单不符**），且 **apiKey 明文落盘**。
- 环境有代理：`HTTP_PROXY/HTTPS_PROXY=http://127.0.0.1:55975`；SSL `verify_mode=CERT_REQUIRED`，OpenSSL 3.5.5。

**E. 零依赖 SSE 可行性实测（D-11 的关键证据）**
- `urllib.request` + 代理 + 系统证书 → **HTTP 200，0.4–0.8s**。
- SSE 格式：`Content-Type: text/event-stream; charset=utf-8`；每帧一行 `data: {json}`；末帧 `data: [DONE]`；**共 11 帧**。
- **usage 默认就在最后一帧**（DeepSeek 不依赖 `stream_options.include_usage`，实测 A/B 两组都含 usage）。
- 结论：**零依赖 SSE 能跑**，但上述"能跑"**依赖 env proxy + 系统证书**——换机/换平台需处理三态。

**F. 工时校准（我的估计依据）**
- 依据 = 现有代码形状 + 实测接口行为 + "每条新命令都要带 fixture（D-16 硬 Gate）"的乘数。
- `cli.py`（subprocess 转发 + 三约定适配 + 编码/退出码透传 + 转发自测）：**~1 轮**。
- LLM 调用层（SSE + 重试/退避 + 代理/超时/容错 + usage 回写 + `/models` 双向核对 + 离线 fixture）：**~1.5 轮**（含边界用例）。
- `route_error()` + 最小回归集：**~0.5 轮**（函数0.1，标注脏活0.4）。
- 自测网扩项（5 命令 × 3 用例）：**~0.5-1 轮**。
- → **P2 合计约 4-6 轮**（vs 原文档"2-3 轮"）。**P2b（enforcement/compress/design）有强串行依赖，是爆炸点。**

---

## 一句话总结

**我最想推翻的是 D-13「调用前 enforcement 走 (a) 真熔断」**——它要"真实 usage 回写 + 校准窗口 + 调用必经引擎"三个前提同时成立，而实测这三条**一条都不成立**（cost_log 只有预估成本字符串、rule 83 已有"分母错"先例、子 Agent 绕过引擎直调），照做只会产出一个**比不做更危险的假熔断**。
