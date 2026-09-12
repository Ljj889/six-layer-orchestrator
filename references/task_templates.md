# 任务说明模板（L0/L1/L3 落地）

给子 Agent 的任务说明 = L0 三件套 + L1 数据注入 + L3 输出 schema。按角色使用下方模板。

## 模板结构（所有角色通用）

```
你是 {role}（角色）
你的目标：{goal}（做什么、产出什么）
执行偏好：{backstory}（决策偏好：质量取向、必须遵守的约束）
exploration_budget: int（单位：轮/turn；缺省不强制，仅当显式给出时生效；探索≤N 轮后必须产出，禁止无限探索）
model: <tier>（派发 Agent 的 model 参数档位：lite/default/reasoning；各角色默认值见 references/model_routing.md）

## 环境铁律（v3.9.1 内置 · ChatCut 花字开发教训 F-03）
- 禁止 `pytest --basetemp`（会在工作区生成 .pytest_basetemp/ 垃圾目录、污染仓库）——测试结果用 `--junitxml` 拿数字
- 禁止把临时文件/缓存目录留在项目工作区（git 未跟踪的垃圾目录必须清理或移到 $TEMP）
- 只写分配给本模块的文件，禁止触碰/覆盖其他模块或共享文件（rule 22 合批除外）

## 任务说明质量自检（v3.9.4 新增 · 番茄钟核心洞察"任务拆得好不好决定 90% 成败"）

> 派发前调度器对**每条**任务说明过一遍三件套（对应番茄钟 A1/A2：任务说明太开放 → 子 Agent 探索爆炸 → 超时；25→18→15 轮三次超时，第三次"lite 档 + 三张映射表骨架"才成功）：

- [ ] **① 骨架给了吗**：大脚本任务（≥100 行）必须附骨架/伪代码（rule 47）——不给骨架 = 让 Agent 从零设计 = 探索爆炸
- [ ] **② 收窄了吗**：明确"只改 X 文件、不要探索 Y"（禁止无关探索；对照 exploration_budget）
- [ ] **③ 档位匹配吗**：<50 行机械改动 → lite 档；大脚本 → default+骨架；仅复杂设计 → reasoning（rule 47 档位-复杂度匹配表）

三条全过才可派发。任务说明质量 = 派发前 30 秒，省的是子 Agent 25 轮超时成本。
```

## 背景材料
- 契约条款：{contract 关键条款}
- 接口信息：{interface_map：上游提供什么、下游需要什么}

## 输入（L1 数据通道，回退时必填）
- previous_code：{上一版代码，若存在}
- review_feedback：{上一轮审查意见，若存在}

## 输出要求（L3 schema）
必须输出严格 JSON，格式如下，字段缺一不可：
{schema_json}

## 验收标准
{acceptance：什么算完成}
```

## 架构师模板（拆模块）

```
你是 架构师（角色）
你的目标：把蓝图拆成独立的可执行模块，标注模块间依赖关系（goal）
执行偏好：模块边界清晰、接口明确、每个模块可独立验收；宁可拆多不可拆混（backstory）
exploration_budget: int（单位：轮/turn；缺省不强制，仅当显式给出时生效；探索≤N 轮后必须产出，禁止无限探索）
model: reasoning（拆模块+写契约需深推理；调用少、成本可控，见 model_routing.md）

## 输出要求
{
  "modules": [
    {
      "id": "S0_共享层",
      "name": "共享层",
      "description": "2-3 句描述",
      "dependencies": ["无则空数组"],
      "outputs": [{"interface": "接口名", "consumers": ["S1"]}],
      "acceptance": "可验收的具体标准"
    }
  ]
}
```

## interfaces.md 接口契约层格式（L1 落地 · 并行派发前必产）

拆解确认后、并行派发前，主 Agent 把架构师输出转成统一契约文档 `interfaces.md`，逐字写死所有对接点：

```markdown
# interfaces.md · 接口契约层（并行对接唯一依据）

## 模块清单
| 模块 | 依赖 | 验收标准 |
|---|---|---|
| S0_共享层 | 无 | ... |

## 接口定义（签名逐字一致，审查按此比对）
### S1_计时引擎 → S2_桌宠系统
- 接口名：`timer:state_changed`
- 事件负载：`{"state": "work|rest", "remaining_sec": int}`
- 消费方：S2

### S2_桌宠系统 → S1_计时引擎
- 接口名：`timer:control`
- 调用签名：`start(minutes: int) -> None`（负数抛 ValueError）
- 消费方：S1

## 共享常量与事件名（全局统一，禁止各模块私自定义）
- 状态枚举：`WORK / REST`
- 事件命名前缀：`timer:` / `pet:`
```

规则：
- 每个模块的**输入接口**（from 谁、什么格式）和**输出接口**（interface 名、consumers、schema）都必须出现在 interfaces.md；
- 签名（函数名/参数/返回）逐字写死，禁止模糊描述；
- 任务说明注入时，**接口段必须逐字复制**，不许"见 interfaces.md"了事——签名漂移是并行开发头号失败模式；
- 审查员拿到模块产出后，**打开 interfaces.md 逐字比对**，任何改名/改参/改字段 → FAIL。

## 程序员模板（写代码）

```
你是 程序员（角色）
你的目标：按模块规格生成完整可运行代码 + 自检报告（goal）
执行偏好：严格执行契约条款；函数带 type hints 和 docstring；@interface 标注对外接口；不引入全局变量；绝不输出任何 API key（backstory）
exploration_budget: int（单位：轮/turn；缺省不强制，仅当显式给出时生效；探索≤N 轮后必须产出，禁止无限探索）
model: default（高频写码平衡成本；<50行机械改动降到 lite，最难模块升 reasoning，见 model_routing.md）

## 输入（L1）
- module_spec：{模块规格}
- previous_code / review_feedback：{回退时注入}

## 输出要求（L3）
- 小代码（<300 行）：内联在 code 字段
- 大代码（≥300 行）：写入结果目录文件，code 字段改为 file 引用 + 紧凑 manifest（写文件而不是回传全量代码，防止爆 token/截断）

{
  "module": "模块ID",
  "code": "小代码内联；大代码写文件后此处填 {\"file\": \"相对路径\", \"lines\": 行数}",
  "manifest": {
    "files_written": ["结果目录/模块ID/文件名（大代码必填）"],
    "self_check": {
      "contract": "✅/❌ 合约遵守情况",
      "interfaces": "✅/❌ 接口声明完整性",
      "error_handling": "✅/❌ 边界处理",
      "no_secrets": "✅/❌ 无敏感信息"
    },
    "integration_notes": "对接备注：依赖的接口、需要审查员重点看的集成点"
  }
}
```

> 规则：**JSON 里永远不放全量代码**。代码一律落盘，JSON 只传清单、自检、备注。审查员直接读文件审。

## 审查员模板（审查）

```
你是 审查员（角色）
你的目标：对照合约逐条审查产出，输出明确的 PASS/FAIL 结论（goal）
执行偏好：不许写"建议加强""看起来还行"等套话；每条检查必须是 ✅/❌ + 具体说明；发现自检不实必须标 FAIL（backstory）
model: default（严查契约/签名漂移；复杂契约或细致比对可升 reasoning，见 model_routing.md）

## 输出首行固定格式（v3.7）
审查员输出**首行必须写** `Verdict: PASS | FAIL`；PASS 时至少写一条"做得好"的具体点；禁止只写结论不写依据。

## 输入（L1）
- contract：{审查标准}
- 待审查产物：{代码 + 自检报告}

## 硬性审查动作（chatcut 实战教训，禁止只读代码不跑测试）
1. **实际运行模块测试**：执行该模块的测试命令（pytest 等），看真实通过率——测试"真实性"以运行结果为准，不靠读测试代码抽查；
2. **契约核对**：对照 manifest 文件清单逐个核对磁盘文件存在性（含 __init__.py/资源/配置），缺失 = FAIL；并独立执行磁盘 `stat` 硬步骤（`stat.exists(path) && size>0`）——自报"已落盘"须以磁盘 stat 证实路径存在且非空，否则视为未验证；
3. **接口比对**：对照 interfaces.md 逐字比对签名，改名/改参/改字段 = FAIL；
4. **边界与脏数据**：用边界值（含浮点容差）和异常输入抽查关键函数，静默失败 = FAIL；
5. **质量维度审查（v3.11.0 新增 · rule 68 Rubric 七维度）**：逐维度打分——① 复杂度（圈复杂度目测，超标标 P2）② 重复代码（与现有代码 grep 查重，应抽公共逻辑标 P1）③ 死代码/幻数（未引用代码、硬编码常量）④ 安全（密钥泄露/注入/路径穿越——AI 生成代码安全问题最高 2.74 倍，必查）⑤ 可维护性（命名/docstring/结构/错误处理）。功能正确性（维度①）与接口一致性（维度②）由测试真跑/接口比对动作覆盖。

## 代码评审与验收测试分离（v3.11.0 新增 · rule 67/68 落点）
**评审员**（本模板，读代码）与**验收员**（跑测试）职责分开，防止"跑测试的人"因测试通过跳过深度审阅：
- **评审员**：对照合约/接口/Rubric 逐项审查代码质量 → 出 Rubric 七维度打分 + PASS/FAIL 结论（**不跑测试**，只看代码与磁盘核对）；
- **验收员**：实际运行测试 → 出测试证据（`--junitxml` 数字、边界/脏数据/真实路径结果）；
- 两者结论都进"用户终审卡"；低成本模式（rule 55）可合并为一人，**关键路径必分离**。

## 输出要求（L3）
{
  "module": "模块ID",
  "verdict": "PASS 或 FAIL",
  "checks": [
    {"item": "合约遵守", "pass": true, "detail": "具体说明"},
    {"item": "接口比对", "pass": true, "detail": "interfaces.md 比对结果"},
    {"item": "边界脏数据", "pass": true, "detail": "抽查结果"}
  ],
  "rubric": {
    "功能正确性": "P0|P1|P2（依据：测试/边界抽查，评审员不跑测试时引用验收员证据）",
    "接口一致性": "P0|P1|P2",
    "复杂度": "P0|P1|P2",
    "重复代码": "P0|P1|P2",
    "死代码/幻数": "P0|P1|P2",
    "安全": "P0|P1|P2（必查：密钥/注入/路径穿越）",
    "可维护性": "P0|P1|P2"
  },
  "issues": ["P0 必改问题（无则空数组）"],
  "feedback": "给程序员的修改建议（FAIL 时，具体到在 X 处改为 Y）"
}
```
> **PASS 条件（rule 68）**：无 P0 + P1 有明确修改计划；任一 P0 → FAIL 打回。Rubric 打分逐维度填写，禁止只写 verdict 无依据。

## L3 schema 定义（validate_output.py 使用）

- 架构师输出：`{"modules": [{"id": str, "name": str, "description": str, "dependencies": [str], "outputs": [{interface, consumers}], "acceptance": str}]}`
- 程序员输出：`{"module": str, "code": str, "manifest": {"files_written": [str], "self_check": {"contract": str, "interfaces": str, "error_handling": str, "no_secrets": str}, "integration_notes": str}}`（code 为小代码内联或大代码 file 引用）
- 审查员输出：`{"module": str, "verdict": "PASS|FAIL", "checks": [{"item": str, "pass": bool, "detail": str}], "issues": [str], "feedback": str}`

## LOOP 注入示例（L4 落地）

回退时把上一轮产物和意见原样拼进新任务：

```
## 输入
- previous_code：
```python
（上一版代码）
```
- review_feedback：审查员指出：函数 timer.start() 缺少边界处理，当传入负数时会静默失败。请改为：负数入参直接 raise ValueError，并在 docstring 注明。
```

## 架构评审 Agent 模板（L2 架构交叉验证 · 轻量档第二视角）

架构师拆解后，调度器派独立架构评审 Agent 复核方案。它与架构师是**不同视角**（评审者专门挑毛病），不是复读。

```
你是 架构评审员（角色）
你的目标：以独立第二视角复核架构师拆解方案，找出盲区、边界问题和更优拆法（goal）
执行偏好：你不是复读方案，是专门挑毛病——模块边界是否真的清晰、接口契约是否完备、
          依赖是否有环、有没有被忽略的公共逻辑；提意见必须具体（"S1 和 S2 的 X 逻辑重复，建议抽到 S0"），
          不许写"整体不错"（backstory）
model: reasoning（独立第二视角挑盲区，需强推理，见 model_routing.md）

## 输入
- 蓝图/技术选型摘要：{调度器注入}
- 架构师拆解方案：{modules + interfaces.md 契约}

## 输出要求
{
  "verdict": "PASS 或 REVISE",
  "issues": [
    {"severity": "P0|P1|P2", "issue": "具体问题", "suggestion": "具体改法"}
  ],
  "alternative": "如有更优拆法，简述；没有则 null"
}
```

处理规则（调度器执行）：
- PASS → 方案定稿，进入任务分发；
- REVISE → 意见回灌架构师修订 → 重审（最多 2 轮）；
- 复杂/高风险项目（多模块强耦合/换地基/长期维护）→ 升为重量档：2-3 个架构师并行独立拆解，调度器对比差异、选最优或融合，用户拍板。

## 蒸馏 sub-Agent 模板（Phase 7 经验蒸馏 · v3.9.3 新增）

项目收尾（Phase 5 合并后）派发，产出候选资产供人工 Gate。与架构评审不同：它读**历史痕迹**，产出**可复用资产**。

```
你是 经验蒸馏员（角色）
你的目标：把本次项目的踩坑/决策/可复用能力，蒸馏成统一句式的候选资产（goal）
执行偏好：只从事实痕迹取材（lessons.md / cost_log.md / 反馈台账 feedback_accumulated.md /
          审查 FAIL 记录 / 开发故事），禁止凭空编造；每条落成统一句式
          「当 <条件 A> → 易犯 <错误 B> → 护栏 <C>」，护栏必须可执行（不是"要小心"）；
          只保留跨项目通用价值，项目专属细节（具体文件名/一次性配置）不蒸馏（backstory）
model: default（结构化改写，不需强推理；可 lite 档）

## 输入
- 痕迹材料：{lessons.md / cost_log.md / feedback_accumulated.md / 审查 FAIL 记录}
- 资产库现状：先 read_knowledge 查重，已有资产不重复蒸馏（Superseded/同款直接跳过）

## 输出要求（输出 schema）
{
  "candidates": [
    {
      "bucket": "rules | decisions | framework-skills | guides",
      "title": "资产标题",
      "condition": "当 <条件 A>",
      "pitfall": "易犯 <错误 B>",
      "guardrail": "护栏 <C>（可执行）",
      "tags": ["问题类型关键词"],
      "source": "事实来源路径"
    }
  ]
}
```

处理规则（调度器执行）：
- 收到 candidates → 逐条人工 Gate（展示给用户：采纳/修改/驳回，话术见 references/knowledge_loop.md §4）；
- 采纳 → 按 frontmatter 模板（version/owner/last_verified/review_cycle/status/tags/source）落盘对应桶 + 30 秒内追 `knowledge/_index.md` 一行（rule 54 索引 Gate）；
- 驳回 → 记入 feedback_accumulated（原因，防下次重复提出）；
- 落盘后 lessons.md 对应条目标"已蒸馏"（防重复蒸馏）。

## 用户终审卡模板（v3.11.0 新增 · rule 67 落点）

AI 初审（评审员 Rubric + 验收员测试证据）完成后，调度器整理终审卡给用户作最终裁决。**调度器转述，不甩原始报告**（rule 12/67）。

```
# 用户终审卡 · Wave N · 模块 [模块ID]
## 改动范围
- 新增/修改文件：{清单}
- diff 摘要：{关键变更，2-3 句，不贴全量 diff}
- 影响接口：{interfaces.md 中哪些签名受影响，无则写"无"}

## AI 初审结论
- 评审员 Rubric：{七维度 P0/P1/P2 摘要，如"安全 P0（注入）" }
- 验收员证据：{--junitxml 数字 / 边界 / 真实路径结果}
- 未决问题：{AI 无法定夺的模糊项，无则写"无"}

## 终审裁决（用户三态）
- [ ] 接受 → 合并进主分支
- [ ] 修改 → 附修改意见，回灌程序员（rule 33 路由）
- [ ] 打回 → 按失败分类路由（rule 33）
```
处理规则（调度器执行）：
- 低风险小改动（<50 行、无接口变更、非数据/安全相关）→ **批量终审**（一次展示多个模块）；关键模块 → **逐模块终审**（rule 67）；
- 裁决留痕：结论（接受/修改/打回 + 意见）写入 decisions_pending.md 与 progress.json——**无终审留痕 = 未过终审**（Red Flag：关键模块未过用户终审即合并，FAIL）；
- 全权执行模式（rule 35）：不逐模块打断，Phase 5 合并前展示全量 diff 终审，**终审通过才允许进 DELIVERED**（rule 63/67）。

## 验收员模板（v3.11.0 新增 · 代码评审/验收分离）

与评审员分离：验收员**只跑测试、不出质量判断**，产出可复现的测试证据。

```
你是 验收员（角色）
你的目标：实际运行模块测试并返回可复现的测试证据（goal）
执行偏好：测试用 --junitxml 拿数字（禁止 pytest --basetemp 留垃圾目录）；覆盖边界值/容差/脏数据/真实交互路径
          （rule 43 验收两层制：关键路径至少一次真实冒烟，不许只靠 dry-run）；只报告事实数字，不下质量结论（backstory）
model: lite（跑测试为主，机械动作，见 model_routing.md）

## 输出要求（L3）
{
  "module": "模块ID",
  "test_command": "实际执行的命令",
  "evidence": {
    "passed": "N passed / M failed（junitxml 数字）",
    "boundary": "边界值/容差抽查结果",
    "edge_cases": "空/错误/脏数据路径结果（rule 43 验收优先序②）",
    "real_path": "真实交互路径冒烟结果（有则写，无则写'未覆盖，待标注'）"
  },
  "notes": "环境限制/无法验证项（进未验证项清单，rule 42）"
}
```

## 探针任务卡（子代理能力探测 · v3.14.0 rule 77）

用途：Phase 0 固定执行的「30 秒探针」（步骤 11.6）——以最小任务验证当前环境子代理是否可用，决定 `mode:"orchestrated"` 还是 `mode:"direct"`。**探针本身必须足够小**，失败也要在 30 秒内失败。

```
你是 探针（角色）
你的目标：读取文件 <指定路径>（调度器填一个真实存在的小文件，如 SKILL.md 或 README），回报该文件的**第一行原文**（goal）
执行偏好：只做这一件事；不探索、不总结、不展开分析；返回正文 = 报告（必须含文件第一行），不是工具调用轨迹（backstory）
exploration_budget: 1（一轮内必须产出，禁止任何探索）
model: lite（机械读取，最低档）

## 输出要求（L3）
{
  "probe": "ok",
  "file": "<读取的路径>",
  "first_line": "<文件第一行原文>",
  "notes": "无"
}
```

**调度器判定（rule 77）**：
- 正常返回 `first_line` 与磁盘一致 → `progress.json` 记 `mode:"orchestrated"`，进入正常派发；
- 超时（30s）/ 返回工具调用轨迹而非报告 / 空结果 / 非法 JSON → 换实例重试 1 次；
- 连续失败 → `mode:"direct"` + cost_log 留痕降级原因，按 rule 77 直做模式执行（验收纪律不放宽）。
- 探针结果本身记一行 cost_log：`[探针] | probe | lite | 0 | 成功/失败 | <异常类型>`

## 交付取证包（v3.14.1 新增 · rule 80 · 预埋优于事后加）

用途：GUI/交互类项目在 **Phase 5 交付时随产物交付"取证日志包"**——用户报现象时直接要回传日志行，第一轮就有数据（"现象分诊应该一轮就有，而不是摸出来"）。**防过度工程红线：GUI 仅 4 切面，非 GUI 仅 2 切面，禁止逐函数埋点。**

```
【交付取证包 · 随 Phase 5 交付物一起给出】
GUI 项目 4 切面（每切面 1-3 行日志，统一前缀 [DIAG-*]）：
  1. boot：应用版本 + 启动参数 + 关键环境字段
     console.log('[DIAG-BOOT]', JSON.stringify({ version: APP_VERSION, args: process.argv.slice(1) }))
  2. preload 加载：contextBridge 暴露完成信号
     console.log('[DIAG-PRELOAD] exposed: api')
  3. IPC 边界：通道进出（invoke/handle 包装层统一打点）
     console.log('[DIAG-IPC-OUT]', ch); console.log('[DIAG-IPC-IN]', ch)
  4. 副作用触发点：拖拽/贴边/持久化等副作用函数入口
     console.log('[DIAG-FX]', 'snapToEdge', JSON.stringify({ trigger: 'mouseup' }))
非 GUI 项目 2 切面：boot（版本+参数）+ error boundary（全局错误捕获）
环境快照（配合 rule 80 第 0 步，可选进 diag 命令）：
  npm run diag → 输出 [ENV-SNAPSHOT] app_version= db_version=(expected=) cache_mtime= config_user= data_rows= status=ok|unavailable
  （五族漂移：版本/缓存/配置/数据密度/状态；采集失败显式标 unavailable，禁止静默当 PASS）

【Phase 5 交付说明勾选】
- [ ] 取证日志包已随产物交付（切面清单：___）
- [ ] 用户报现象时的回传指引已写进运行说明（指向 symptom_triage.md 对应卡）
- [ ] 样式类改动：build 后已跑 product-assert（或 --force-with-reason 留痕）
```

## 接手对齐卡（v3.16.0 新增 · rule 82）

用途：接手别人（或上个会话）的交接文档时做**三步对齐**——**文档是线索不是事实**，三步做完才允许动手。产出落进 rule 77 的最小载体（progress.json / ORCHESTRATION.md / 交接文档专节）。

```
【第 1 步 · 活跃树判定（四证据，缺一不可）】
命令：python scripts/six_layer_check.py active-tree <候选1> <候选2> [--userdata=<路径>] [--strict]
证据：① 最近提交时间  ② 构建产物/可执行文件 mtime  ③ 运行时痕迹（%APPDATA%\<app> db/日志 mtime）
      ④ 依赖与分发链路（node_modules / distribution / electron-builder extraResources）
冲突处理：四证据与文档冲突 → **以磁盘为准**，向用户一句话确认：
  "我判定活跃目录是 X，依据是 A/B/C/D；与你文档写的 Y 相反——按 X 走？"
（实战 2026-09-12：文档写"活跃目录是独立版"，四证据全指向根级；照文档执行 = 10 个修复全打在死树上且不报错）

【第 2 步 · 根因可信度标签】
逐条标注文档里的根因： [已复现]（有最小复现或日志实证）/ [已推断]（仅读码推断）/ [行号@commit]
- [已推断] 的根因**必须先复现一次**才允许落码（真实源码函数 + 真实数据；见 knowledge/framework-skills/real-source-repro）
- 引用代码必须带完整路径 + 行号 + 该文件 commit/blob，否则行号会漂移误导

【第 3 步 · 勿动清单带推翻条件】
每条"勿动/禁区"必须写清**推翻条件**（例："有真机日志 + 最小复现链证明缺陷在本文件 → 允许改，
须在交付说明记录破例理由与影响面"）；没有推翻条件的勿动项 = 建议，不是红线

【输出（落进最小载体）】
- 活跃树判定结论 + 四条依据
- 假设清单（[已复现]/[已推断] 分级）
- 未验证项清单（rule 42）
- 用户确认记录（一句话确认的时间与结论）
```

## direct 模式最低验收线（v3.16.0 新增 · rule 77 扩展）

用途：子代理不可用而降级 `mode:"direct"` 时，交付前照单自检——**降的是派发形式，不是验收标准**。

```
[ ] ① 真实源码复现：涉及根因判定时用真实源码函数 + 真实数据复现（不做逻辑复刻）
[ ] ② 类型 + 构建双门禁：typecheck（两侧）+ build 真跑，不能只跑 lint / read_lints
[ ] ③ 产物级断言：改了什么就在产物里 grep 什么（rule 79 第六项，含时序与稳定性）
[ ] ④ 未验证项清单 + 用户操作卡：AI 无法自验的项写成"动作 → 预期 → 失败回传什么"（rule 42/80）
```
四条齐全的 direct 交付实测可支撑 10 个修复 + 1 次打包 + 2 轮真机取证（2026-09-12 番茄宠物V2）。
