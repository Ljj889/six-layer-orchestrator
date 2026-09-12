# 学习回路原语：经验蒸馏（写）+ 文档读取（读）

> 版本：v3.9.3 · 对应 SKILL.md rule 58/59/60 与 Phase 7
> 一句话：**写（Phase 7 蒸馏成资产）→ 存（knowledge/ 四桶 + _index.md）→ 读（read_knowledge 原语召回）→ 用（注入 spec/plan/constitution + progress.json 留证）**，框架才真正"越用越聪明"。
> 设计源头：`调研专用/六层框架_经验蒸馏与文档读取回路_设计_2026-08-12.md`（NASA LLIS 教训：只写不读 = 坟墓）。

---

## 1. 写侧：Phase 7 经验蒸馏（rule 58）

### 1.1 两级触发

| 级别 | 时机 | 动作 | 成本 |
|---|---|---|---|
| **阶段级 mini** | 每个 Phase / Gate / 波次完成后 | 更新 `lessons.md`；在 cost_log/progress.json 记一行 `候选: <资产路径>|<类型>|<一句话>` | 便宜，必跑 |
| **项目级 full** | Phase 5 合并交付后、进入下一轮前（Phase 6 反馈处理完） | 跑完整六步：**Gather → Rewrite → Classify → Gate → Land → Feed** | 每次项目收尾必跑 |

### 1.2 六步流程（full 级）

```
① Gather（收集）   —— 蒸馏 sub-Agent 收集：lessons.md / cost_log / 反馈台账(feedback_accumulated) / 审查 FAIL 记录 / 开发故事
② Rewrite（改写）  —— 每条落成统一句式：「当 <条件 A> → 易犯 <错误 B> → 护栏 <C>」；含可执行护栏，不写感慨
③ Classify（分类） —— 分四桶：rules(红线) / decisions(ADR) / framework-skills(可调用 Skill) / guides(可选说明)
④ Gate（人工把关） —— 调度器把候选清单 + 每条一句话摘要展示给用户，用户确认：采纳 / 修改 / 驳回（见 §4 话术）
⑤ Land（落盘）    —— 按 frontmatter 模板写资产文件 + 复用 rule 54 索引 Gate 追加 `_index.md` 一行
⑥ Feed（回喂）    —— 更新 _index.md（canonical）→ 标记被吸收的 lessons 条目为"已蒸馏"（防重复蒸馏）
```

### 1.3 资产四桶（user 级跨项目共享，位于 `knowledge/`）

| 桶 | 内容 | 资产形态 |
|---|---|---|
| `knowledge/rules/` | 红线（必须遵守，违反=FAIL） | rule 资产，注入 constitution 常驻 |
| `knowledge/decisions/` | 架构/技术决策记录（ADR） | ADR-xxx.md，plan 引用为 rationale |
| `knowledge/framework-skills/` | 可复用能力（框架自身可调用的 Skill） | 按名可调用 |
| `knowledge/guides/` | 可选说明/操作手册 | 仅按需读 |

> 与 `知识经验/`（项目内四分类）的关系：`knowledge/` 是**框架级**共享库（跨项目），`知识经验/vN/` 是**项目内**沉淀（Phase 0.5）。两者并存：项目内先落 `知识经验/`，蒸馏出**跨项目通用价值**的再进 `knowledge/`。

### 1.4 防腐烂 frontmatter 模板（每篇资产必带）

```yaml
---
title: 资产标题
version: 1
owner: <谁沉淀的：家俊 / 调度器 / 某 sub-Agent>
last_verified: 2026-08-12     # 最近一次被真实使用/复核的日期
review_cycle: 90d             # 复核周期，超期读时标 stale
status: active                # active | deprecated
tags: [成本控制, 循环护栏, runtime]   # ★ 召回检索的主键，按问题类型/tags 不按项目名
source: 调研全档案索引 §五 / 开发故事 02 / ChatCut F-01   # 溯源
supersedes: null              # 被本资产取代的旧资产路径
superseded_by: null           # 本资产被谁取代（被取代只读不覆盖）
---
```

**防腐烂规则**：
- `deprecated` 不自动注入；`last_verified` 超 `review_cycle` → 读时标 `stale`，依赖前要求复核
- `Superseded by` 旧版只读不覆盖（不历史重写）
- 已嵌入框架规则（SKILL.md rule）的资产 → 从库移除（**空库 = 吸收彻底**，不是没沉淀）
- 每个新项目启动 = 天然复核点（Phase 0.5 顺带 review 召回列表）

---

## 2. 读侧：read_knowledge 文档读取原语（rule 59）

### 2.1 签名与步骤

```
read_knowledge(query: str, scope: "user"|"project"|"local" = "project",
               status_filter: str = "active", top_k: int = 5) -> list[Asset]
  步骤：① 读 knowledge/_index.md（canonical entry，禁止盲搜）
        ② 按问题类型 / tags 匹配（不按项目名——NASA 覆辙）
        ③ 过滤 scope + status（默认 active）
        ④ 返回资产（frontmatter + 正文摘要），供注入或 just-in-time 使用
```

- **索引优先**：永远先从 `_index.md` 出发。未查 `_index.md` 不得声称"无相关先验经验"（Red Flag）。
- **按 tags 检索**：用本次项目特征（问题域/技术栈/阶段）匹配资产 frontmatter 的 `tags`；初期 frontmatter tags + 全文 grep，后续可升级 embedding。
- **scope 三档**：`user`（框架级共享）/ `project`（当前项目）/ `local`（本机专用）——仿 LangGraph store。

### 2.2 触发点（何时读）

| 时机 | 动作 | 消费目标 |
|---|---|---|
| **Phase -2 调研前** | read_knowledge 召回相关 ADR/Rules | 调研方向清单种子（避免重复调研已知坑） |
| **Phase -1 规格** | 命中 Rules 注入 constitution（红线常驻）；命中 ADR 注入 plan（rationale 引用） | 不可协商原则 |
| **Phase 0.5 知识初始化** | read_knowledge 产出"本次项目相关经验召回清单"（**Gate：未读禁止标已初始化 ✅**） | 初始化判据 |
| **L-执行中（just-in-time）** | 子 Agent 遇未知情形按需 read_knowledge | 即时约束/解法（= 项目级 Reflexion 的"读取"侧） |
| **Phase 7 写之前** | read_knowledge 查重 / 查 Superseded | 去重，避免重复造资产 |

### 2.3 消费方式（读到后怎么用）

| 命中资产 | 消费动作 |
|---|---|
| Rule | 作为硬约束写进 constitution（红线常驻），标注来源路径 |
| ADR | plan/决策里引用为 rationale（标注来源路径，可追溯） |
| Skill | 该相位变为可按名调用的能力 |
| 记录复用 | `progress.json` 记"本次召回清单"（资产路径+命中 tags+注入位置）→ **L2 学习证据**（教训真改变了流程） |

### 2.4 护栏（防错 / 防膨胀）

1. **先读索引**——未查 `_index.md` 不得声称"无先验经验"
2. **只读 active**——deprecated 不自动注入；过期（last_verified 超 review_cycle）标 stale，依赖前复核
3. **引用溯源**——注入 spec/plan 标注资产路径，不静默吸收
4. **精度优先**——只注入与当前项目 tags 匹配的资产（precision > recall），防上下文膨胀（呼应 rule 40 <2,000 行）
5. **不过度依赖**——召回资产是"建议/约束"，不替代本次调研与规格判断

---

## 3. 闭环与 L2 证据（rule 60）

```
Phase 7 写 → knowledge/ 资产库存 + _index.md → 下一项目 Phase -2/0.5 read_knowledge 读
→ 注入 spec/plan/constitution → 执行使用 → progress.json 记录"召回了哪些"（L2 学习证据）
→ 项目收尾 Phase 7 再写（新经验入库）→ 循环
```

**L2 学习证据**：`progress.json` 每次初始化记：
```json
"knowledge_recalled": [
  {"asset": "knowledge/rules/execution_boundary.md", "tags": ["执行边界"], "injected_to": "constitution#2"},
  {"asset": "knowledge/decisions/ADR-001_shared_state.md", "tags": ["共享状态"], "injected_to": "plan#架构"}
]
```
用途：证明闭环真发生（教训真改变了流程），也是防腐烂审计依据。

---

## 4. 人工 Gate 话术（Phase 7 第 ④ 步，调度器向用户展示）

```
【Phase 7 经验蒸馏 · 人工 Gate】
本次项目共收集到 N 条候选经验，蒸馏后 M 条进入人工 Gate：

1. [rules] 执行边界默认拒绝 ——「当子 Agent 需要外部访问时 → 易犯默认放行 → 护栏：无网出口/文件限临时目录/硬超时」
   采纳 / 修改 / 驳回？
2. [decisions] ADR-002 缓存友好提示组装 —— 依据：ProjectDiscovery 7%→84% cache hit
   采纳 / 修改 / 驳回？
...

确认方式：直接回"采纳全部" / "1 驳回 2 修改为 xxx" / 逐条回复。
驳回的资产不落盘，但记入 feedback_accumulated（原因，防下次重复提出）。
```

---

## 5. 引擎层实现（编排 B 预埋）

- **读模块**：`read_knowledge` = 读 `_index.md` → 过滤 scope/status → 返回匹配资产；初期文件实现（frontmatter grep，见 `scripts/read_knowledge.py` 参考实现），后续 embedding 升级。
- **写模块**：Phase 7 蒸馏 sub-Agent 产出候选 → 人工 Gate → 落盘 + 更新 `_index.md`。
- **注入点**：Phase -2/-1/0.5 初始化时引擎层自动调用 read_knowledge 注入上下文（仿 Anthropic "开工前查记忆"）。
- **审计**：progress.json 记录召回清单（L2 学习证据）。

---

## 6. 跨会话记忆指针规则（D1 决策项 · v3.17.0 条件拍板）

> 背景：D1（memory 隔离选型）挂起 3+ 版本。三轮对撞后条件拍板：**指针规则 + 铁律先行 + 启用条件化**，不新建存储。

### 6.1 指针规则（纯文档约定，0 新存储）

- **MEMORY.md 只存蒸馏结论 + 指针**：每条"当前事实"一行声明 + 指向 `.workbuddy/memory/YYYY-MM-DD.md` 明细的指针。明细（完整过程）落日志，结论（跨会话要记住的）落 MEMORY.md 并带指针。
- **不新建存储**：MEMORY.md 与日志路径均为平台既有文件，本规则是纯文档约定，不触 C1 平台边界。

### 6.2 跨窗口铁律（先行，不待条件）

**先读指针层再动手**——跨会话/跨窗口接手时，先读 MEMORY.md 的指针层（蒸馏结论 + 指针），再按需读明细日志。这是零成本约定，先于 T3 实锤启用（低频高伤缺口的最小对策待遇，见 rule 66 确认分级）。

### 6.3 启用条件 + 回退条款

- **启用条件**：T3 跨会话错位 ≥2 例实锤（cost_log 第 7 列错位类型 = T3 累计 ≥2 行）→ 指针规则从"铁律"升级为"强制"（进 Red Flags 检查项）。
- **回退条款**：若实测平台已序列化写入（多窗口并发写不冲突）→ 指针规则优势减半，改"单一 memory + 会话标签"方案。回退条款入正文（不藏脚注）。
- **kill 语义**：议题关闭（取证窗口内 0 实锤）**不连带撤销**本"铁律先行"的一行级最小对策——关闭的是"是否升级为强制"的取证议程，不是"先读指针层"这条零成本约定（低频高伤缺口：关闭议题 ≠ 关闭机制）。
