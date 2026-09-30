# Changelog

本项目遵循 [Keep a Changelog 1.1.0](https://keepachangelog.com/zh-CN/1.1.0/) 规范，版本号遵循语义化版本。

> **说明（D-08 banner 治理）**：本文件收纳 **`SKILL.md` 头部原「版本 history banner」的全量历史**（剪到最近 3 版之前的所有内容，**一字不丢**）。
> 本文件的出现属**内容搬迁，非删除**，不受"只增不删"约束（rule 5）。
> **现状数字自报**：规则条数等一切"现状数字"由 `python scripts/rule_index.py` 产出，禁止手抄（R-13）。

固定六类型（Keep a Changelog）：`Added`（新增）/ `Changed`（变更）/ `Deprecated`（弃用）/ `Removed`（移除）/ `Fixed`（修复）/ `Security`（安全）。

---

## [Unreleased]

（下一轮规划：P3 平台化——真熔断 / 跨项目母板 / UI / 用户极简入口。**出现真实需求再开**，无需求则长期为空。）

---

## [3.21.0] - 2026-09-30

> **规则层落地**（开发文档《引擎层与框架升级》v1.0 收敛定稿 · §八 执行序 P1a + P1b）。P1a = D-01…D-07 语义 + 模板 + `engine_config` 初版；P1b = D-08 banner 治理 + 本 CHANGELOG + 同批改 sync 脚本 + 升版。

### Added
- **rule 84 · 跨窗口协作件（状态板三分区 + 隐性知识交接件）· `[假设 · B1 单项目试运行]`**（D-02/D-03/D-07）：状态板 `PROJECT_STATUS.md` 三分区（当前状态 30 秒版 / `CMD-NN` 指令区只追加 / 事件流只追加）+ 隐性知识交接件六项固定（第 ⑥ 项"新窗最易犯的错"为**强烈建议**）。**不升框架级标配**（样本数 = 1，违 rule 5），先 B1 单项目试运行。
- **「引擎参数单一来源（engine_config）」节**（D-18）：温度 / 推理档位 / 预算 / 超时 / 模型白名单 / 校准窗口**单点定义** + 每键 schema + 合法域（**非法即 FAIL，不许静默取默认**）+ **子命令 ↔ rule 号映射表** + 启动打印"生效参数 + 来源"。
- **引擎总开关 `SIXLAYER_ENGINE=off`**（R-01 回滚路径）：cli 全部子命令旁路，回落提示词驱动（一行 env，零成本）。
- **references 新增 4 件**：`real-source-repro.md`（接缝替身模板 · D-04 主载体）、`decisions.md`（Dxx 决策编号制 · D-07）、`collab_artifacts.md`（状态板 + 交接件可选模板 · D-02/D-03）、`engine_config.md`（参数单一来源 canonical source · D-18）。
- **scripts 新增 2 件**：`engine_config.json`（参数机读镜像）、`rule_index.py`（规则数/版本标记/映射表自报 · R-13）。
- **L0 探针层**（`_probe/l0_probe.py` + fixture）：`/models` **双向核对**实测——`deepseek-v4-flash`/`deepseek-chat`/`deepseek-reasoner` 全部 **HTTP 200 但 `model` 被静默改回 `deepseek-flash`**（**不是 404**）；`effort.supported_levels` 实测 = `["low","high","max"]`（**无 `none`**）；`reasoning_effort` 档位**确实生效**；`temperature` 无法证明有效。**硬门：无 fixture → 不许动 L2（已满足）**。
- **L1a 离线硬层**：`cli.py`（in-process + `--isolate` 逃生阀 + 三约定分派 + **Gate 语义契约层** + 参数校验 + 版本寻址 + 总开关）· `engine_selftest.py`（**三条必测断言** + **禁裸 assert** + `-O` 一致性 + **离线护栏**）· `state_board.py`（**弱校验**：结构合法 + 事件流行数单调不减）· `write_assert.py`（产物断言**第三类**：最终位置逐项回读 + 0 字节三分语义 + 降级计数器）。
- **L1b 挂轻门层**：`route_error.py`（纯规则 + **关键词表外置**，改规则不发版）· `compress.py`（**LC1/LC2 机械层，`llm_calls=0`** + 复述测试）· `design_gate.py`（**挂 pending**，exit 3）。
- **L2 需真实往返层**：`llm_client.py`（**默认关闭** + **200 假绿四步防线** + 手写 SSE + 自建连接层 + 预算**漏账 fail-closed** + LC3），已跑通真实非流式/流式往返。
- **Red Flags 新增 5 条**：弱校验通过当"事件流完整" / 用 mock 冒充引擎自测 / 失败路径未写盘 / 引擎参数非法却静默取默认 / 写入搬运只看返回值不看最终位置。

### Changed
- **rule 56 ③ 温度 → `reasoning_effort`（D-12③）**：原"不同阶段用不同温度"**实地驳回**——官方原文 `temperature` 在 thinking mode 下「Has no effect」，且 thinking 默认 enabled → 原方案是**静默失效死代码**。改为 `reasoning_effort`（`none/low/high/max`）+ **三条可探测判据**（能力协商 / `reasoning_tokens` 两端对比 / 兼容映射显式登记）。
- **rule 43 家族扩 D-01（拍板语义 → 单测断言）**：并入本家族，**不新开 rule**；加**降级分支**（无自动化手段 → rule 61 + 人工步骤卡）；测试载体用 **stdlib**（`pytest` 仅 dev-only，禁止作前置依赖）。
- **rule 79 家族扩 D-04 / D-05**：产物断言新增**第三类「写入/搬运类」**（按最终位置的字节数 + 位置逐项回读；拿不到字节记"跳过"不许当"验过"；配降级计数器，先跑能力探针再判"逃逸 vs 环境缺失"）；补"**接缝可替身 / 通道不可 mock**"（**引擎自测同样不得 mock 平台通道**，离线只允许录制重放）。
- **rule 80 扩 D-06（失败必写盘）**：**判定式**——失败路径未写盘 = 该修复**视为未验证**（rule 42）；写盘路径必须**脚本可定位**并纳入 Gate 扫描面。
- **banner 剪到最近 3 版**（v3.19.0 / v3.20.0 / v3.21.0），全量版本史迁入本文件（D-08）。
- **规则条数改为自报**：`有效规则 **69** 条`，编号 10–84（1–9 为 Phase 流程步骤编号；删除号 13/15/17/25/26/30 留空）。原 banner 声明的 67 与实测不符（R-13 活体：现状数字禁止手抄）。

### Fixed
- **`checkpoint.load_state()` 浅拷贝 → 深拷贝**：原 `dict(DEFAULT_STATE)` 是浅拷贝，同进程连调两次会**跨项目串味**（实测真 bug）。
- **`checkpoint` / `lifecycle` 全量写 → `os.replace()` 原子化**：`load→改→全量 save` 在多窗口并发下会丢更新。

### Security
- 分发纪律（D-20）不变：输出物无凭据 + 仓库面无凭据；推送前 `grep -riE 'sk-[a-z0-9]{16,}'` 扫**全仓**（含 references/knowledge/三平台副本）；API Key 只从环境变量读；`models.json` 明文存 key 属**已发生的暴露面**（登记在案）。

---

## [3.20.0] - 2026-09-30

### Changed
- **「先查后试」纪律泛化**（家俊 2026-09-30 需求：解决报错 / 遇到任何问题时，先上网搜别人怎么解决的——网上有大量心得与踩坑帖，靠自己试错要浪费很多时间）：rule 64「纠错先检索」触发面从"改 bug"扩为**一切卡壳**（报错 / API·平台行为诡异 D48 / 库用法不明 / 效果不对 四类）；检索三环升格为**试错前的硬步骤**（三环未跑完禁止试错；搜索规格=平台/库+API+症状·中英各搜·优先官方文档>GitHub Issues>社区·结论标来源；无果才试且试要成组，互链 D48 ③）；**三环注入每个子 Agent 任务卡**（task_templates v3.20.0 环境铁律第 4 条 + 程序员 `self_check.lookup_first` 检索留痕——真正在"试"的是子 Agent，只约束调度器 = 治标不治本）；bug_fix_mode v1.6（检索序强化为硬步骤 + 决策卡加第 ⓿ 步）；symptom_triage 同步。

### Fixed
- **`sync_to_platforms.ps1` 的 wb 目标路径**（sh 版 v3.18.0 已修，ps1 漏改 → 本次修正，防 ps1 同步写到已不存在的旧目录）。
- **同批回流 v3.19.0**（上一轮引擎修复 + rule 61 D48 曾只落平台副本、未回流仓库，已随本次入库）。

---

## [3.19.0] - 2026-09-29

### Fixed
- **render-silent-fail 纯 JS / 原生项目误报根因修复**（0 新 rule，纯引擎缺陷修复）：实战（图片查看器 Wave 4）跑 render-silent-fail 连续稳定误报 2 项，逐层取证后定位到**引擎自身两个缺陷**——
  - ① **注释剥离正则吃文件尾**：原写 `re.sub(r"/\*.*?\*/|^\s*//.*$", "", txt, flags=re.S | re.M)`，`re.S` 让第二支 `^\s*//.*$` 的 `.` 也匹配换行，于是**从第一条行注释一路吃到文件末尾**，其后的 `ipcMain.handle` / `ipcRenderer.invoke` 全部检索不到（**既误报"僵尸 handler"，也漏报真问题=假阴**；实证：`main/ipc.js` 第 148 行一条 `//` 之后 24 个 handler 全消失、`preload.js` 只剩前 11 条）。修法：拆成 `_strip_comments()` 两步（块注释 `re.S` / 行注释 `re.M`），两处调用点（IPC 一致性 + 打包进程探针）同步替换。
  - ② **preload d.ts 对非 TS 项目结构性不适用**：新增 `_is_ts_project()`（有 tsconfig 或有 `.ts/.tsx` 源即算 TS 项目），非 TS 项目降级 **SKIP** 而非 FAIL（这类项目本就没"类型门禁"，preload 契约靠"真 preload + 真 IPC"的渲染层效果验证兜底）。

### Changed
- **`_check_ipc_consistency` 附带加固**：增包装器形态识别（`const invoke = (c) => ipcRenderer.invoke(c, ...)` 后再写 `invoke('x')` 的常见写法——只认字面量会把已调用通道误判成僵尸）+ 动态拼接通道（`` `ns:${x}` ``）标记 uncertain → 降级 SKIP 而非 FAIL。
- **自测 +3 用例**（4b 纯 JS→SKIP / 4c 包装器→PASS / 4d 行注释后 handler 仍在），引擎自检 25 PASS / 0 FAIL。

> **教训**：检查项报 FAIL 时先按 rule 79 v3.15.0"改动范围对焦 + 独立取证"验，**别急着改被测项目——可能是检查器自己在说谎**。

---

## [3.18.0] - 2026-09-28

### Added
- **rule 83 上下文压缩规格**（补 rule 40 缺的「压缩本身」，借鉴「伴学 App」契约 §11 三级级联）：LC1 子 Agent 回报压缩 → LC2 已消费输入淘汰 → LC3 结构化摘要（六字段存 `progress.json`）。
- **references/context_compression.md**。

### Changed
- **分母用校准窗口、不用 API 上限**（伴学教训：分母错 → 与真实会话差 **127 倍** → 压缩永不触发、summary 永远空、判据永远红灯，**调 ratio 没用**）。
- 三条硬纪律（摘要不替代 `progress.json` / 指针优先带行号@commit / 不得转述子 Agent 原话）+ 压缩后复述测试 + 失败降级不阻塞。

### Fixed
- `sync_to_platforms.sh` 的 wb 目标路径（`six-layer-orchestrator` → 实际目录名 `六层编排框架`）。
- 平台副本中 rule 76 残留的旧中文仓库路径由本次 sync 覆盖修正（仓库侧本就正确）。

---

## [3.17.0] - 2026-09-27

> **多agent六层联合编排框架完善研讨 · 三轮对撞收敛（0 新 rule，连续第五版）**

### Changed
- rule 47 档位判据去行数化（两维判定表）+ B1 试运行
- rule 53 `cost_log` 三可选列（错位 T1-T4 / 任务卡行数 / 档位误判）
- rule 40 注入三级策略
- rule 55 三模式联动档位
- rule 64 Gate 预算法四条件 + kill 议题机制二分
- rule 66 确认分级（回退成本 × 方向性）
- rule 78 dispatch-check + write-conflict + audit 进 Wave Gate
- rule 82 触发面扩至派发（T4）

### Added
- scripts：`cost_log audit` 子命令（实锤判定式写死）+ `six_layer_check` 的 `dispatch-check` / `write-conflict` 子命令
- references：`model_routing` B1 判定表 + `knowledge_loop` D1 指针规则 + `task_templates` 注入三级

### Changed（命名）
- 中文名定「**多agent六层联合编排框架**」

---

## [3.16.0] - 2026-09-12

> **番茄宠物V2 单日实战蒸馏**

### Added
- **rule 82 接手对齐三硬步骤**：活跃树判定四证据 + 根因可信度标签 + 勿动清单推翻条件
- **R-012 幂等导入可见性**
- framework-skill `real-source-repro`（真实源码函数复现）
- G-001 v1.4（运行时探针 / 无 Git Bash）、G-002 v2（净机模拟 + 审美反馈）、R-007 v3（切换类状态同步变体）

### Changed
- 扩展 rule 5 分级纪律延伸到交接文档与行号锚定
- 扩展 rule 41 真实源码函数复现
- 扩展 rule 61 审美类反馈一句话确认
- 扩展 rule 64 发布前置链单命令化
- 扩展 rule 66 方向卡未响应分支
- 扩展 rule 77 无框架痕迹项目的最小载体 + direct 模式最低验收线（四条）
- 扩展 rule 78 引擎脚本运行时探针
- 扩展 rule 79 第六项 产物断言时序与稳定性
- 扩展 rule 80 验收三要素 + 现象→可判定断言模板 + 输入输出可见日志

### Added（同日引擎对齐）
- scripts：`+runtime_probe.py`；`six_layer_check` 增 `active-tree` / `product-assert` 时序与稳定性 / `render-silent-fail` 噪音治理 / `[PROBE]` 报告头；`sync_to_platforms(.sh/.ps1)` 校验升级（版本抽检 ≥2 处 + 领先检测 + MD5 + 逐目录文件数）
- references：`symptom_triage` v2.1（验收三要素 + 现象→可判定断言模板）/ `bug_fix_mode` v1.5（真实源码复现 + 检索序补项目内参照）/ `task_templates`（+接手对齐卡 + direct 模式最低验收线）

---

## [3.15.0] - 2026-09-11

> **便签反馈回合2蒸馏**（0 条新 rule，全部扩展现有规则）

### Changed
- rule 72 僵尸新变体 · preload 参数焊死
- rule 73 共享交互 hook 信号
- rule 79 脚本 Gate 噪音甄别 + 空洞 PASS
- rule 80 取证手段分层 · 结构性缺失 grep 三问
- G-001 v1.3 Windows 运行环境坑

---

## [3.14.1] - 2026-09-11

> **改错能力研讨会收敛**（0 条新 rule，全部扩展现有规则）

### Changed
- rule 41 归因闭环：现象消失证据 + 单变量 + 取证排序
- rule 64 检索序加项目内参照
- rule 68 副作用审查子检查点
- rule 79 第六项 产物级断言 `product-assert`
- rule 80 环境快照第 0 步 + 漂移五族
- R-011 项目内参照物优先
- 交付取证包模板

---

## [3.14.0] - 2026-09-05

> **实战复盘五反馈引擎化**

### Added
- rule 77 子代理能力探测与直做模式
- rule 78 引擎三件套进 Wave Gate
- rule 79 渲染端静默失效检查 Gate
- rule 80 取证优先与现象排查卡
- rule 81 长排错会话检查点

---

## [3.13.1] - 2026-09-02

### Added
- **rule 76 蒸馏资产唯一真相源 = 独立仓库**（家俊决策 A）：Phase 7 产出必须直接落盘独立仓库；平台 skills 目录只是运行时副本。

---

## [3.13.0] - 2026-09-01

### Changed
- **WorkBuddy + CodeBuddy 两版合并统一编号**（rule 73-75 并入，G-006 框架合规指南，引擎三件套 + `six_layer_check` 脚本）

---

## [3.12.0] - 2026-08

> **galagame 实战**

### Added
- 僵尸能力红线 + monorepo 构建顺序 + web 自动化环境坑 + 设置入口 ADR

---

## [3.11.0] - 2026-08

### Added
- 混合审查 + 质量 Rubric + 并行隔离 + Wave 级复盘 + 计划评审回合制

---

## [3.10.0] - 2026-08

### Added
- 每步方向讨论 Gate

---

## [3.9.10] - 2026-08

### Added
- 对抗式双架构师设计回路 + 调研 crawler

---

## [3.9.9] - 2026-08

### Added
- 过程文档先行 + 解耦第一 + 验收 Gate 不豁免

---

## [3.9.8] - 2026-08

### Added
- 设计锁定原则

---

## [3.9.7] - 2026-08

### Added
- 硬约束优先原则 + 纠错先检索

---

## [3.9.6] - 2026-08

### Added
- 项目生命周期状态机

---

## [3.9.5] - 2026-08

### Added
- 多宠语音实战反馈

---

## [3.9.4] - 2026-08

### Added
- 番茄钟实战反馈修订

---

## [3.9.3] - 2026-08

### Added
- 经验蒸馏 + 文档读取闭环

---

## [3.9.2] - 2026-08

### Added
- 调研经验转化

---

## [3.9.1] - 2026-08

### Added
- ChatCut 反馈修订

---

[Unreleased]: #unreleased
[3.21.0]: #3210---2026-09-30
[3.20.0]: #3200---2026-09-30
[3.19.0]: #3190---2026-09-29
