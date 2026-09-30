# HT-实现者 · Round 3（聚焦裁决 · ≤120 行）

## §1 A3-1 cli 形态：**in-process 为默认（7 个现有确定性脚本）+ subprocess 仅用于网络/流式（L1）** ｜置信度 **高**

- **一句话理由**：in-process 快 13×（**[复测5]** 31ms vs 416ms）且我已用原型证明它保得住 Gate 退出码（**[复测9]** 6/6）；但 **[复测10] 我用实测发现 HT4 的隔离顾虑不是假设而是已存在的真 bug**——`checkpoint.load_state()` 的 `return dict(DEFAULT_STATE)` 是**浅拷贝**，导致同进程内 `tmp2/progress.json` **泄漏了 tmp1 的模块 A1**（`['A1','B2']`）。→ 结论：**in-process 默认，但必须先修这个 leak（属"除 bug"），网络/流式命令走 subprocess**。这不是和事佬，是证据给出的分界。

**最小实现要点（≤5 条，可直接翻代码）**
1. `mod = importlib.import_module(name)`；`old = sys.argv; sys.argv = ["cli"] + argv`，**`try/finally` 恢复 `sys.argv`**（防污染后续调用）。
2. `try: r = mod.main(); return 0 if r is None else int(r)` ／ `except SystemExit as e: return e.code if isinstance(e.code,int) else 0`。——**归一化契约**：[复测4] 成功返 `None`、失败 `SystemExit(1)`、`six_layer_check` 成功 `SystemExit(0)`。
3. 外层再包 `except Exception` → 返回 1 + 打印，**别让一个命令打死 cli.py**。
4. **先修 [复测10] 的 leak**：`checkpoint.load_state()` 里 `dict(DEFAULT_STATE)` → **`copy.deepcopy(DEFAULT_STATE)`**（§七"只加不改（除 bug）"允许；顺带扫其余脚本有无同类浅拷贝默认值）。
5. **网络/流式（L1 D-11）走 subprocess**：超时可控 + 崩溃/卡死不污染主进程——这是 in-process 唯一站不住的场景。

**必测断言（≤3 条）**
- **A1**：失败命令 → cli 退出码 **1**（用 `checkpoint mark m BAD` 与 `cost_log add t BAD ...` 两例）。
- **A2**：**跨项目不串味**——同进程对 `tmp1`/`tmp2` 各 `mark` 一次，各自 `progress.json` **只含自身模块**（即 [复测10] 的反向断言；不修 leak 必红）。
- **A3**：成功命令 → 退出码 **0**，且 `--json` 转发后仍可 `json.loads`（转发不改内容）。

**若被裁 subprocess（点名 HT4）**：我不反对其"隔离"论据本身，但请注意两点硬成本——① **416ms/次**，且 `six_layer_check` 内部**自己已 spawn subprocess**（self-test），嵌套会叠加；② subprocess **掩盖**而非**修复** [复测10] 的 leak——该 bug 独立存在于脚本中，**换了形态也欠债**。故选 in-process + 修 bug。

---

## §2 A3-2 D-02/D-03 最小形态：**选 (iii) 模板 + 规则 + `append-only` 弱校验**（iv 的"挂 pending"由已冻结的 F5/B1 承担）｜置信度 **中高**

- **一句话理由**：iii 是**当下就能建且能测**的最小件（结构合法 + 行数单调不减）；iv 多出的"挂 pending"是**记账动作**而非构建动作，而"升标配/做生成器"已在 F5 冻结为"降 `[假设]` + B1 单项目试运行"——**重复挂 pending 是记账冗余**。HT4 R2 已承认"自动生成事件流必须删"，iii 与之兼容。
- **「它不保证什么」**：弱校验**不保证事件流完整**——它**不检测"漏记"**（脚本无法知道用户做没做动作）；**"校验通过 ≠ 事件流完整"必须写在报告头**，否则它自己变成新假绿源。

---

## §3 A3-3 P2 默认范围：**默认 = L1 全做（9 件）** ｜置信度 **中高**

- **一句话理由**：9 件里 **7 件是"基础设施 / 纯 bug 修复 / 已存在项的扩测"**——**不预设需求假设**（逐件见下），即使家俊低频也正向不白做；仅 **2 件（route_error / design schema）是中性**（低频收益低但成本小），故标为**可选件**而非砍掉。合计工时 **约 3.5–4 轮**（见下），不是 1 轮也不是 7 轮。
- **一行回退**：**若家俊答"频率很低 / 主战场不走框架"→ 回退为 HT3 最窄版**：只做 **cli 串联 + 自测网 + `os.replace` 原子写 + `runtime_probe` bash 探针**（= 纯基础设施 + 纯 bug 修复，**零需求假设**）；`route_error` / `compress` / `design` / 状态板弱校验 / product-assert 扩测 **全部挂起**。

**对 HT3 判据的正面回答（逐件：是否"不预设需求假设"）+ 工时对齐**

| 件 | 不预设? | 一句依据 | 工时 |
|---|---|---|---|
| cli 串联（in-process + 修 leak） | ✅ | 任何一次调用都经它；修 [复测10] 是除 bug | 0.5 轮 |
| 自测网扩项 | ✅ | 防引擎自己说谎；改引擎必跑，与频率无关 | 0.5–1.0 轮 |
| `os.replace` 原子写 | ✅ | **纯 bug 修复**（[复测10] 又添一类全局污染例证） | 0.25 轮 |
| `runtime_probe` bash 探针 | ✅ | **纯 bug 修复**（补 D-09 探针缺口，我 R1 [附录B] 实测） | 0.1 轮 |
| product-assert 时序 | ✅ | **已存在**（`_check_pack_timing`），只扩自测，零新增 | 0.2 轮 |
| compress LC1/LC2 | ✅ | **无 LLM 的确定性规则**，可独立离线验证 | 0.5 轮 |
| 状态板弱校验 | ✅ | 防状态板**自身**腐烂，与用量无关 | 0.25 轮 |
| route_error + 最小回归集 | ⚠️ 中性 | 预设"错误频繁到需自动路由"；但**函数零成本**（R1：几十行纯匹配） | 0.5 轮 |
| design(schema) | ⚠️ 中性 | 预设"会走设计锁定流程"；低频下白做，但**是 D-15 的前置** | 0.5 轮 |
| **合计** | **7✅ + 2⚠️** | | **≈3.5–4 轮** |

> **注**：**L1（D-11 LLM 层 / token_ledger）不在本默认内**——它仍卡在未消解分歧「谁调 LLM」（R2 §A-①）；若 Agent 继续走原生工具，L1 应缩为 one-shot 非流式（0.75 轮）而非完整 SSE（1.5 轮）。

---

## 本轮实测证据（新增）

**[复测10] in-process 跨项目串味——确认的真 bug**
```
import checkpoint; 同进程连续调用 main()
call([tmp1,"mark","A1","delivered"])   # tmp1 无 progress.json 起步
call([tmp2,"mark","B2","verified"])    # 另开 tmp2
→ tmp2/progress.json 竟含 ['A1','B2']   ★A1 从 tmp1 泄漏到 tmp2★
根因: load_state() 里 `return dict(DEFAULT_STATE)` 是【浅拷贝】
      → state['modules'] 与 DEFAULT_STATE['modules'] 同一对象 → 就地 setdefault 污染模块级全局
```
→ **in-process 才暴露**（subprocess 每次新进程，天然隔离）；但 **bug 本身独立存在**，必须先修。

**[复测11] 模块级可变全局清单**：`checkpoint` 有 `STATUS_MAP/DEFAULT_STATE`（DEFAULT_STATE 是**可变**且被就地改）；`cost_log` 4 个 `ALLOWED_*`、`lifecycle` 3 个、`six_layer_check` 6 个均为**只读常量**（无就地改）→ **风险面仅 checkpoint 一处**。

---

## 最后一句

**三个焦点的最终主张**：**A3-1** = in-process 默认 + subprocess 仅用于 L1 网络层，且**必须先修 [复测10] 的 `DEFAULT_STATE` 浅拷贝 leak**（附 A1/A2/A3 三条断言）；**A3-2** = (iii) 弱校验，报告头写明"通过 ≠ 完整"；**A3-3** = 默认 L1 全做（9 件，≈3.5–4 轮），回退线 = 只留基础设施 + 纯 bug 修复四件。

**本轮是否可收敛**：**可收敛**——A3-2/A3-3 已可落开发文档；**A3-1 亦可收敛**，因 [复测10] 把"隔离"从**立场之争**变成了**一条明确的修 bug + 一条明确的 subprocess 边界**（网络层），双方论据都被吸收，无剩余对立。
