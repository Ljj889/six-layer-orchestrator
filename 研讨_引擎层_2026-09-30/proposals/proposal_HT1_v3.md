# HT-设计者 · Round 3 聚焦裁决

## §1 A3-1 cli 形态：**in-process 默认 + subprocess 逃生阀（两形态共存）** ｜置信度 高

- 一句话理由：HT2 的 `[复测1]`（7/7 有 `__main__` 守卫、顶层零副作用）、`[复测4]`（`main()` 契约＝成功返回 None→0 / 失败 `SystemExit(n)`→n）、`[复测9]`（原型 **6/6 保住 Gate 退出码**）、`[复测5]`（31ms vs 416ms，**13×**）证明 **in-process 在"退出码保真"上与 subprocess 等价**——两条路径读到的是**同一批 `sys.exit()`**。我 Round 2 主张 subprocess 的唯一论据（"exit 码 ≠ Gate 语义"）**不构成对 subprocess 的支持**：那个缺口**两种形态同样存在**，该由独立的一层「子命令语义契约」补，而不是靠换调用形态补。故我**主动让位**，取共存折中。
- 不反对 HT4：subprocess 的**隔离收益真实但极小**（单人自用 + 同源仓库 + 同一 Python；唯一实感差异是 `six_layer_check` 内部本来就自己 spawn subprocess，与 cli 层无关）。保留逃生阀即可覆盖它。
- **最小实现要点（5 条）**：
  1. `_run(mod, argv)`：存/还原 `sys.argv`（`["<name>"]+argv`）→ `redirect_stdout/redirect_stderr` 到缓冲 → 调 `mod.main()`；**`except SystemExit as e:` → `code = e.code if isinstance(e.code,int) else (0 if e.code is None else 1)`；`except Exception:` → 打 traceback、`code = 1`**（后者是 in-process **唯一会与 subprocess 漂移**的点，必须显式兜）。
  2. 三种调用约定收进 cli 的**不可变分派表**（verb-first / dir-first / argparse），由 cli 拼 argv，**不改 7 脚本**。
  3. `--project` 归一化 → 翻译成各脚本期望位置（dir-first 放 `argv[0]`、verb-first 放 verb 之后）。
  4. **子命令语义契约层（与形态无关、必做）**：`{subcommand: {module, fail_predicate}}`，专门覆盖"失败不走退出码"的脚本（如 `read_knowledge` 0 命中 → 默认 **WARN 非 FAIL**，须**显式声明**，不许默认当绿）。
  5. `--subprocess` 逃生阀：捕获目标模块 `ImportError` 即自动降级为 `python <script> …`（`encoding="utf-8"`、returncode 透传）。
- **必测断言（3 条）**：
  1. **退出码保真**：7 模块各造 1 个已知失败（`checkpoint` 非法态 / `lifecycle` 非法转移 / `cost_log` 缺列 / 其余等价）断言 cli ≠ 0；各造 1 个已知成功断言 = 0；再各造 1 个"未捕获异常"断言 = 1。（＝`[复测9]` 6/6 + **补齐第 7 个** + 覆盖异常路径）
  2. **零副作用可执行版**：`import` 7 模块前后 `sys.argv / os.getcwd() / sys.path / signal 注册表` 不变。
  3. **逃生阀等价**：同一失败用例，in-process 与 `--subprocess` 返回码一致（防两条路径语义漂移）。

## §2 A3-2 D-02/03 最小形态：**(iv) 弱校验 + 挂 pending** ｜置信度 中高

- 一句话理由：(iii) 是我 R2 的主张，且**与 F5 已冻结的"不升标配 + `[假设]` + B1 单项目试运行"完全兼容**——做"**结构合法 + 行数单调不减**"的弱校验器（离线可测、**不需要并发基线**），把"升标配 / 生成器 / 强校验（基线+锁）"**明确挂 pending 到家俊 B1 数据之后**；接受 HT4 已承认的"**自动生成事件流必须删**"（脚本无法知道用户做没做动作）。
- **「它不保证什么」（必填）**：**弱校验通过 ≠ 事件流完整**——它只保证"结构没坏、行数没减少"，**不保证用户漏记的动作会被发现**（"是否漏记"需基线 + 锁，留 P3；此留白须写进规则，防它自己成为新假绿源）。

## §3 A3-3 P2 默认范围：**默认 = L1 全做（9 件），其中 `design` 与 `route_error` 的"回归评测"两件挂 pending** ｜置信度 中高

- 一句话理由：L1 里 **7 件经逐件检查"不预设需求假设"**（要么"修已有资产的暗病"、要么"落已成文的规则"、要么"需求缺席时成本 = 0"）；剩下 **2 件确实预设了前置**（`design` 需 schema、`route_error` 评测需真实 FAIL 语料），**诚实挂 pending，不为保范围硬撑**。
- **一行回退**：若家俊答"**频率很低 / 主战场不走框架**" → 回退为 **HT3 最小集（cli 串联 + 自测网返修）**，其余 7 件挂 pending；其中 **自测网返修必留**——它修的是**已在跑的** 25 条 fixture（[S4] 用例 7 是假绿），**与使用频率无关**。
- **对 HT3 判据的正面回答（逐件）**：

| L1 件 | 是否"不预设需求假设" |
|---|---|
| cli 串联 | ✅ 元工具：把**已在用**的 7 脚本收进一个入口，减"记不住路径"摩擦 |
| 自测网（含返修） | ✅ 修**既有**资产（25 条 fixture 已在跑，含 1 条假绿），非新需求 |
| `route_error` **函数本体** | ✅ 纯规则 + 表外置，离线可测、成本低 |
| `route_error` **回归评测** | ⚠️ **预设**：需真实 FAIL 语料（伴学样本 = 1）→ **挂 pending** |
| `compress` LC1/LC2 | ✅ 机械层不花 LLM，落地**已冻结**的 rule 83 |
| `design(schema)` | ⚠️ **预设**：schema 尚不存在（HT2 R2 已指出）→ **挂 pending 至 schema 定稿** |
| `product-assert` 时序 | ✅ 扩**既有**命令；无产物项目不触发（缺席成本 0） |
| 状态板弱校验 | ⚠️ 轻微预设（假设板子被用）→ 但**文件不存在即 SKIP**（复用 render-silent-fail "存在才查"约定），**缺席成本 0** → 操作上不预设 |
| `os.replace` 原子写 | ✅ 修**既有**并发写丢更新的 bug |
| `runtime_probe` bash 探针 | ✅ 补齐**既有**探针（现只有 node/python/py_launcher） |

---

**最后一句**：三个焦点我各自的最终主张 = ① **in-process 默认 + subprocess 逃生阀**（让位给 HT2 的实测，缺口由独立"子命令语义契约"层补）；② **(iv) 弱校验 + 挂 pending**（"不保证事件流完整"必须写进规则）；③ **默认 L1 全做，`design` 与 `route_error` 评测挂 pending**，回退 = HT3 最小集且**自测网返修必留**。**本轮已可收敛（是）**——三处剩余差异均已在证据上闭合，唯二的 pending 是**前置条件未满足**（schema 定稿 / FAIL 语料积累），是执行前置而非观点分歧，无须再开一轮。
