# 扫描报告 B · CLI 框架 / 编排引擎 / 状态机 / 断点恢复

> 扫描员：**前沿技术扫描员 B**｜日期：2026-09-30｜对象：《讨论文档_框架升级与引擎层_2026-09-30.md》D-10 / D-15 / D-16 / D-17 / D-19
> 纪律：**只出证据与表，不替 HT 拍板**。所有 License / 版本 / 日期均为**本机实测**（非记忆）。
> 查不到写 ❓。来源分级：**官方文档 > 官方仓库 > 活跃仓库 > 社区帖**。

---

## 0. 实测方法与工具（可复现）

沙箱 bash 可用（`curl` / `python3` 正常），Python 用 `C:\Users\one\.workbuddy\binaries\python\versions\3.14.3\python.exe`（**非** `py` 启动器，已知坏）。

本目录落盘的三个可复现工具：

| 脚本 | 作用 |
|---|---|
| `_probe_pypi.sh <pkg...>` | 拉 PyPI JSON，抽 `info.license` / `license_expression` / `requires_dist` / `requires_python` / `urls[0].upload_time` / 首末版本 |
| `dep_closure.py <pkg...>` | **计算"默认安装"传递依赖闭包大小**（跳过 `extra ==` 可选依赖，BFS 递归解析）。这是本次最关键的原创证据——PyPI 只给直接依赖，闭包才是真实装包量 |
| `_probe_license.sh <owner/repo...>` | 回 GitHub raw 核 `LICENSE` 首 4 行 + 关键词，并打 GitHub API 取 stars/license.spdx_id/pushed_at/archived。**因 PyPI 的 `info.license` 大量为 `None`（PEP 639 迁移期），仓级核验是必需的** |

**关键实测事实（本次调研的地基）**：`curl` + `urllib` 均可直连 PyPI / GitHub raw / GitHub API，**全部数据为真联网实测**。

---

## 1. 核心问题 1：D-15 `cli.py` 该用什么？

### 1.1 ⭐ 先看"被包对象"的真实形态（决定打包策略）

实测 `scripts/` 全部 7 个脚本的 CLI 入口形态：

| 脚本 | 行数 | CLI 形态 | 子命令 | 退出码行为 |
|---|---|---|---|---|
| `checkpoint.py` | 138 | **手写 sys.argv** | `<dir> status\|expect\|mark\|verify` | 大多**不 sys.exit**（隐式 0） |
| `cost_log.py` | 204 | **手写 sys.argv** | `<dir> add\|summary\|audit\|tail` | 大多**不 sys.exit** |
| `lifecycle.py` | 173 | **手写 sys.argv** | `<dir> get\|transit\|history` | 大多**不 sys.exit** |
| `six_layer_check.py` | 1637 | **手写 verb 分发**（`argv[0] in (...)`）+ `--flag=value` 手撸解析 | `render-silent-fail` / `product-assert` / `active-tree` / `self-test` / `dispatch-check` / `write-conflict` + 默认 `check` | **总是 sys.exit(0/1/2)** |
| `read_knowledge.py` | 140 | **argparse** | 无（位置参数 `query` + `--scope/--top_k/--include_stale`） | ❓ |
| `runtime_probe.py` | 160 | **argparse**（`add_help=False` 手撸 `-h`） | 无（`--require/--json/-h`） | 返回 int |
| `validate_output.py` | 97 | **裸位置参数** | 无（`<file> <schema>`，`len(sys.argv)!=3` 即报错） | ❓ |

**结论 A**：**4/7 是手写 sys.argv，2/7 是 argparse，1/7 是裸位置参数 —— 三种不同的约定共存**。这意味着 `cli.py` 无论用哪个框架，都必须做一层"参数翻译"，**框架本身省不掉这层**。这是"引框架"收益被高估的第一处证据。

### 1.2 ⭐⭐ 决定性实测：7 个脚本**可零改动 import 并复调 `main()`**

实测（Python 3.14.3）：

```
checkpoint             import=OK  main=True  cmd_*=['cmd_expect','cmd_mark','cmd_status','cmd_verify']
cost_log               import=OK  main=True  cmd_*=['cmd_add','cmd_audit','cmd_summary','cmd_tail']
lifecycle              import=OK  main=True  cmd_*=['cmd_get','cmd_history','cmd_transit']
read_knowledge         import=OK  main=True
runtime_probe          import=OK  main=True
validate_output        import=OK  main=True
six_layer_check        import=OK  main=True

7 模块全量 import 耗时: 0.032s
  six_layer_check 单独 import: 0.001s
```

7 个脚本**全部有 `if __name__ == "__main__"` 守卫、顶层零副作用、`main()` 可见**（`six_layer_check.py` 84KB 但 import 仅 1ms，体积来自数据/正则而非计算）。

**串联原型实测**（改 `sys.argv` → 调 `mod.main()` → 捕获 `SystemExit`）：

```
checkpoint status            exit=0  out='[checkpoint] .../tmphsedc6ig  lifecycle=IN...'
lifecycle  get               exit=0  out='[lifecycle] .../tmphsedc6ig  当前状态: INIT'
cost_log   summary           exit=0  out='[cost_log] 无成本记录（cost_log.md 不存在或为空）'
runtime_probe                exit=0  out='{\n  "python": {\n    "ok": true,\n    "version": "3.14.3"...'
six_layer_check self-test    exit=0  out='[six_layer_check] 引擎自检（self-test · rule 64 回归网 · 改引擎后必跑）...'
```

**这意味着：`cli.py` 可以零依赖、零改动（守住 §七「只加不改」）地包住全部 7 个脚本。** 需要的只有一句 `sys.argv = ["x"] + argv`，加 try/except SystemExit。

**结论 B（本报告最强的一条）**：D-15 的"引不引依赖"问题，**答案在实测后坍缩了** —— 因为被包对象是"可 import 的模块"，不是"只能 subprocess 调的外部程序"，`argparse` 的嵌套子命令成本被大幅稀释（每个子命令体只需 10 行转发）。**引 Typer/Click 的边际收益 ≈ 0，边际成本 = 永久背上依赖。**

### 1.3 CLI 框架横向实测表

| 包 | 版本 | 直接依赖(base) | **闭包总数** | License（PyPI/仓） | 最新发版 | requires_python | 纯 Python |
|---|---|---|---|---|---|---|---|
| **argparse**（stdlib） | — | 0 | **0** | PSF | 随 Python | — | ✅ |
| **click** | 8.5.0 | **0** | **1** | BSD-3-Clause | 2026-08-26 | >=3.10 | ✅ |
| typer | 0.27.2 | 4 | **8** | MIT | 2026-08-28 | >=3.10 | ✅ |
| cyclopts | 5.1.0 | 4 | **8** | Apache-2.0 | 2026-09-29 | >=3.11 | ✅ |
| tyro | 1.0.16 | 4 | **5** | MIT | 2026-08-23 | >=3.8 | ✅ |
| cappa | 0.32.2 | 4 | **8** | Apache-2.0 | 2026-07-27 | <4,>=3.8 | ✅ |
| rich-argparse | 1.8.0 | 1 | **5** | MIT | 2026-05-01 | >=3.9 | ✅ |
| poethepoet | 0.48.0 | 3 | **4** | MIT | 2026-07-05 | >=3.10 | ✅ |
| cleo（Poetry 用） | 2.1.0 | 2 | ❓ | MIT | **2023-10-30** | >=3.7,<4.0 | ✅ |
| docopt | 0.6.2 | 0 | 1 | MIT | **2014-06-16** | None | ✅ |

闭包成员明细（实测）：
- `typer` 8 包 = typer + **rich + pygments + markdown-it-py + mdurl** + shellingham + annotated-doc + colorama
- `cyclopts` 8 包 = cyclopts + attrs + docstring-parser + **rich + rich-rst + pygments + markdown-it-py + mdurl**
- `click` **1 包 = click 自己**（`requires_dist` 实测为 `0` 条）

### [B-01] stdlib `argparse`（含 `subparsers`）
- **是什么**：Python 标准库自带的多级子命令解析器（`add_subparsers()` → 每个子命令一个 `set_defaults(func=...)`）。
- **为什么可用**：① 被包对象已可 import（§1.2），子命令体只剩"转发"；② 10 类子命令在 argparse 里就是 10 个 `add_parser` + 10 个 `set_defaults`，**实测无任何技术障碍**；③ 零依赖硬约束（D-11）零冲突；④ `argparse` 对 `--flag=value` / `--flag value` 两种写法都吃，正好匹配 `six_layer_check.py` 现有的手撸解析。
- **接入成本**：**零依赖**；安装体积 0；纯 Python（stdlib）。
- **License**：PSF-2.0（Python Software Foundation License）——随 Python 解释器，**无仓级差异**。
- **维护活跃度**：随 CPython 发版（3.14.3 已在本机可用，实测通过）。
- **风险**：① 子命令嵌套要手写（但它们本就是平的）；② argparse 的"缩写匹配"（`--verb` 可缩写）偶有意外歧义，可用 `allow_abbrev=False` 关掉；③ 对子命令的 help 文案不自动美观（可用 §B-07 缓解）。
- **需要补的一层**（实测发现）：**退出码不可靠**。`checkpoint/cost_log/lifecycle` 的 `main()` **大多不调 `sys.exit()`**（只有 `six_layer_check` 总是 exit）。→ `cli.py` 必须 `try: mod.main(); code=0 / except SystemExit as e: code=e.code or 0` 并显式 `sys.exit(code)`，否则 `cli.py` 会永远返回 0，**Gate 语义直接失效**。这是本次实测捞出来的**真坑**，不是推测。
- **是否适合本项目**：**适合**。
- **URL**：https://docs.python.org/3/library/argparse.html （来源分级：**官方文档**）

### [B-02] `click`（8.5.0）
- **是什么**：最广泛使用的 Python CLI 库，装饰器式声明命令组/子命令。
- **为什么可用**：**实测 `requires_dist` = 0 条，闭包 = 1 包（它自己）** —— 在"有依赖"的选项里，它是唯一"依赖数 = 1"的。若将来真的想引一个 CLI 框架，**Click 是比 Typer 更合理的选择**（见反转发现 R-2）。
- **接入成本**：**1 个依赖**；wheel 体积 ❓（未实测下载体积）；纯 Python。
- **License**：**BSD-3-Clause**（PyPI `license_expression` 实测）。
- **维护活跃度**：8.5.0，**2026-08-26**；首版 2014-04-28；`>=3.10` 无上界 → 3.14 可用。
- **风险**：① Click 内部基于 `optparse` 而非 argparse，**不支持 `--flag=value` 与 `--flag value` 混用之外的自定义解析**，要包 `six_layer_check.py` 的手撸 flag 需额外适配；② 引入 click 后，7 个脚本的 `main()` 仍是"读 `sys.argv`"，**框架优势用不上**（除非重写脚本，违反 §七）；③ 装饰器样板比 argparse 更多。
- **是否适合本项目**：**不适合**（收益被 §1.2 抹平；且与"包住现有 sys.argv 脚本"的目标错配）。
- **URL**：https://click.palletsprojects.com/ （官方文档）｜https://pypi.org/project/click/ （官方仓库）

### [B-03] `Typer`（0.27.2）
- **是什么**：基于 Click 的类型注解式 CLI（FastAPI 作者出品）。
- **为什么可用**：文档最好、心智负担低。**但对本项目无可复用性**。
- **接入成本**：**8 个依赖**（typer + rich + pygments + markdown-it-py + mdurl + shellingham + annotated-doc + colorama）；纯 Python。
- **License**：**MIT**（PyPI `license_expression` 实测；仓库同样 MIT）。
- **维护活跃度**：0.27.2，**2026-08-28**；`>=3.10`。
- **风险**：① 依赖闭包 8 包，其中 **rich 是一条"渲染/终端"依赖链，与"合规闸"的价值毫无关系**；② Typer 的优势（从函数签名生成 CLI）**在本项目用不上**——因为命令体是"转发到已有脚本"，签名是写死的；③ 引 Typer = 引 Click + rich，**违反零依赖硬约束（D-11）且过不了尽调**。
- **是否适合本项目**：**不适合**。
- **URL**：https://typer.tiangolo.com/ （官方文档）

### [B-04] `Cyclopts`（5.1.0）
- **是什么**：从零设计、纯类型注解 + docstring 解析的现代 CLI 库，被社区称"Typer 本该有的样子"（官方文档自己也这么说）。
- **为什么可用**：技术上最优雅（支持 Union/Literal、自动 docstring 帮助、`@app.command` 直接注册）。
- **接入成本**：**8 个依赖**（cyclopts + attrs + docstring-parser + rich + rich-rst + pygments + markdown-it-py + mdurl）；纯 Python；`requires_python >=3.11`。
- **License**：**Apache-2.0**（PyPI `license_expression` + classifier 双证）。
- **维护活跃度**：5.1.0，**2026-09-29（昨天）**；首版 2023-11-03；**非常活跃**。
- **风险**：① 依赖闭包 8 包（同样含 rich 链）；② `>=3.11` 无上界，3.14 推测可用但**未实测** ❓；③ 项目年轻（2 年），API 曾有大版本跳跃（4.25.3 → 5.0.0）；④ 未进入"零依赖"门槛。
- **是否适合本项目**：**不适合**（依赖面与 Typer 同级，且更年轻）。
- **URL**：https://cyclopts.readthedocs.io/ （官方文档）｜对比：https://cyclopts.readthedocs.io/en/v3.0.0/migration/typer.html

### [B-05] `docopt`（0.6.2）
- **是什么**：从 docstring 里的 usage 文本直接生成解析器。
- **为什么可用**：**不适用**。本项目 3 个脚本的 docstring 已有完整 usage 文本，docopt 本可"零额外代码"生成解析——**但见 R-5，它已停维 12 年**。
- **接入成本**：0 依赖；纯 Python。
- **License**：**MIT**（PyPI `info.license` = `'MIT'` + classifier）。
- **维护活跃度**：**最新发版 2014-06-16（12 年前）**；GitHub `docopt/docopt` 最后 push **2025-06-23**（零星提交），stars 8007，**且仓库根目录未找到 LICENSE 文件**（实测）⚠️。
- **风险**：**长期停维 = 与 3.14 兼容性无保障**；且仓库无 LICENSE 文件（PyPI 声明 MIT，仓级不能核验）→ 若将来按 D-20「给他人用」的纪律，**这条本身就是"不自洽"的合规瑕疵**。
- **是否适合本项目**：**不适合**（停维 + License 不可仓级核验）。
- **URL**：https://pypi.org/project/docopt/ ｜https://github.com/docopt/docopt（活跃仓库，但停更）

### [B-06] `tyro` / `cappa` / `rich-argparse` / `poethepoet`（同类备选，均不采纳）
- **是什么**：`tyro`（注解/数据类式 CLI）、`cappa`（注解式 CLI）、`rich-argparse`（给 argparse 换 rich 皮肤）、`poethepoet`（pyproject 里的任务运行器，可当"命令别名"层）。
- **为什么可用**：若只想"优雅一点"——`rich-argparse` 是唯一"给 stdlib argparse 加美化而**不换解析器**"的选项（接入成本最低，闭包 5 包）。
- **接入成本**：tyro 5 包 / cappa 8 包 / rich-argparse 5 包 / poethepoet 4 包；全部纯 Python。
- **License**：tyro MIT｜cappa Apache-2.0｜rich-argparse MIT｜poethepoet MIT（均实测）。
- **维护活跃度**：tyro 2026-08-23｜cappa 2026-07-27｜rich-argparse 2026-05-01｜poethepoet 2026-07-05。
- **风险**：全部把"零依赖"破掉，收益却只有"好看的 --help"。
- **是否适合本项目**：**不适合**（若真要美化 help，`rich-argparse` 是唯一"可商议"的，但仍需过尽调）。
- **URL**：https://github.com/brentyi/tyro ｜https://github.com/DanCardin/cappa ｜https://github.com/hamdanal/rich-argparse ｜https://github.com/nat-n/poethepoet

### [B-07] 备选："git-hooks 式"极简串联（零框架，~120 行）
- **是什么**：不写框架，只写一个 `cli.py`：`COMMANDS = {"wave": {"status": (checkpoint, ["status"]), ...}}` 字典 + `argparse` 只做顶层分发，子命令体是 8 行转发函数。
- **为什么可用**：这是 §1.2 实测成果的直接应用——**7 个脚本已具备"可 import + 有 main()"的接缝，包装它不需要任何框架**。同一模式可参考 `pre-commit`（MIT，自身闭包 12 包）的"薄入口 + 插件声明"思路，但**不需要装它**。
- **接入成本**：**零依赖**（stdlib）；新增文件 ~120 行；**对现有 7 脚本 0 改动**。
- **License**：自研（无外部 License 约束）。
- **维护活跃度**：不适用（自持）。
- **风险**：① 退出码必须显式处理（见 B-01 的坑）；② 「新命令必带自测用例」（D-16）的硬 Gate 要靠人遵守，可加一条 `self-test` 覆盖（现有 `six_layer_check self-test` 已 25 PASS / 0 FAIL，实测通过）。
- **是否适合本项目**：**适合**（推荐度不低于 stdlib argparse，本质是其具体化）。
- **URL**：参考模式 https://pre-commit.com/ （官方文档，仅借鉴"薄入口"思想）

---

## 2. 核心问题 2：有没有值得"整体借鉴架构"的编排引擎？

### 2.0 ⭐ 全局对比表（全部实测闭包）

| 项目 | 版本 | 直接依赖 | **闭包总数** | License | 最新发版 | 需服务端? | 需 Node? |
|---|---|---|---|---|---|---|---|
| **apache-burr** | 0.43.0 | **0** | **1** | **Apache-2.0**（仓级实测） | 2026-08-25 | ❌ | ❌ |
| **pocketflow** | 0.0.3 | 0 | 1 | MIT（仓级实测） | 2025-07-28 | ❌ | ❌ |
| python-statemachine | 3.2.1 | 0 | **1** | MIT | 2026-08-01 | ❌ | ❌ |
| dill | 0.4.1 | 0 | **1** | BSD-3-Clause | 2026-01-19 | ❌ | ❌ |
| cloudpickle | 3.1.2 | 0 | **1** | BSD-3-Clause | 2025-11-03 | ❌ | ❌ |
| voluptuous | 0.16.0 | 0 | **1** | BSD-3-Clause | 2025-12-18 | ❌ | ❌ |
| msgspec | 0.22.0 | 0 | **1** | BSD-3-Clause | 2026-09-29 | ❌ | ❌（**C 扩展，非纯 Python**） |
| transitions | 0.9.3 | 1 | **2** | MIT | 2025-07-02 | ❌ | ❌ |
| llama-index-workflows | 2.25.0 | 3 | **9** | MIT | 2026-09-25 | ❌ | ❌ |
| typer（对照） | 0.27.2 | 4 | 8 | MIT | 2026-08-28 | ❌ | ❌ |
| temporalio | 1.33.0 | 5 | **7** | MIT | 2026-09-15 | **✅ 必须** | ❌ |
| agent-framework（MS） | 1.19.0 | 1 | **11** | MIT | 2026-09-18 | ❌ | ❌ |
| autogen-agentchat | 0.4.x | 1 | **11** | MIT（PyPI） | **2025-09-30** | ❌ | ❌ |
| jsonschema | 4.26.0 | 4 | 6 | MIT | 2026-01-07 | ❌ | ❌ |
| check-jsonschema | 0.38.2 | 6 | **16** | Apache-2.0（classifier） | 2026-09-23 | ❌ | ❌ |
| pymarkdownlnt | 0.9.40 | 5 | 12 | MIT | 2026-09-13 | ❌ | ❌ |
| promptlint-cli | 1.3.0 | 2 | **6** | Apache-2.0 | 2026-04-13 | ❌ | ❌ |
| langgraph-checkpoint | 4.2.0 | 2 | **37** | MIT | 2026-08-07 | ❌ | ❌ |
| langgraph | 1.2.12 | 6 | **40** | MIT | 2026-09-21 | ❌ | ❌ |
| dagster | 1.13.24 | 32 | **55** | Apache-2.0 | 2026-09-21 | ❌ | ❌ |
| prefect | 3.8.7 | 57 | **106** | Apache-2.0 | 2026-09-27 | ❌ | ❌ |
| apache-airflow | — | 2 | **122** | Apache-2.0 | 2026-09-17 | ❌* | ❌ |
| aider-chat | — | **108** | **123** | Apache-2.0（仓级） | 2026-02-12 | ❌ | ❌ |
| crewai | 1.15.23 | 31 | **141** | MIT（仓级） | 2026-09-28 | ❌ | ❌ |
| agno | 3.0.11 | — | ❓（396 条 requires_dist） | Apache-2.0 | 2026-09-23 | ❌ | ❌ |

\* Airflow 默认 SQLite 可单机，但生产形态是服务端；此处只标"依赖面"。

**读表法**：本项目硬约束是"零依赖优先 + 本地 CLI（D-17）+ 单人自用"。**闭包 1 包的项目 = 可以谈；闭包 ≥20 包的项目 = 与硬约束正面冲突**。

### [B-08] ⭐⭐ Apache Burr（incubating）—— 本次最强"可借鉴架构"
- **是什么**：把决策型应用（含多 agent）建模为**显式状态机**：`@action(reads=[...], writes=[...])` 定义动作 + `Transition`/`Condition` 定义边 + **不可变 `State` 快照**贯穿全程；`ApplicationBuilder` 组装；`halt_after=[...]` 让机器在指定动作后停下等人。
- **为什么可用**：**它一个框架同时命中了本项目三件事**——
  1. **状态机**：对应 `lifecycle.py`（INIT→EXECUTING→DELIVERED→(REOPENED|ACCEPTED) 五态+转移表）；
  2. **断点/恢复**：`.with_state_persister()` 可持久化到磁盘/DB，**"resume from where it left off"**，官方定位含 "Persistence & State Management / Resume applications"；
  3. **HITL**：官方定位含 "Human-in-the-Loop：Pause execution and wait for human input at any step"——**正好对应本项目 D-13「超预算停下问人」与各 Gate**。
  另有 **"Replay / Testing"**（回放历史 run、单测单个 action）对应本项目"回归网"。
- **接入成本**：**0 个依赖（实测 `apache-burr` 闭包 = 1，即它自己）**；**纯 Python**（wheel `py3-none-any`）；`requires_python >=3.9`；**整包在 PyPI 有 100 条 `requires_dist`，但全部是 extras**（`apache-burr[start]` / `[postgres]` / `[streamlit]` 之类），**base 安装零依赖**。
- **License**：**Apache-2.0**（仓级实测：GitHub `apache/burr` 的 `LICENSE` 首行 = "Apache License / Version 2.0, January 2004"；GitHub API `license.spdx_id` = `Apache-2.0`）。⚠️ PyPI `info.license` 为 `None`（PEP 639 未声明）→ **必须以仓级为准**。
- **维护活跃度**：PyPI `apache-burr` **0.43.0 @ 2026-08-25**；`burr`（旧名，0.42.0 @ 2026-07-18）；GitHub `apache/burr` **pushed_at 2026-09-29（昨天）**，stars 2563，open issues 104，**未 archived**；已捐给 Apache 基金会（incubating），**治理非单一公司**。
- **风险**：① **官方落地页写 "Python 3.12+"，而 PyPI metadata 写 `requires_python >=3.9` → 两处冲突**，本机 3.14.3 能否实跑**未实测** → ⏳；② 引入它会带来"框架语义"（State 不可变、action reads/writes 声明），**可能与 SKILL.md 的提示词真相源产生双真相源风险**（D-18 冲突）；③ 需要重写现有脚本才能发挥价值 → 违反 §七「只加不改」。
- **⭐ 怎么用才合适（关键）**：**不装包，抄思想**。它的四个设计点可零成本移植进 `cli.py`：
  1. **action 显式声明 `reads` / `writes`** → 用于 `dispatch-check`（任务卡必须声明读哪些文件、写哪些文件，天然和规则 78 的 `write-conflict` 子命令咬合）；
  2. **`halt_after`** → 用于 Wave Gate 的"跑到某一步停下等人"；
  3. **不可变 State 快照**（每步都是新对象）→ 这是"断点恢复"能成立的前提，可反哺 `progress.json` 的写盘契约；
  4. **"state 是普通 dict，可 inspect/persist/replay"** → 正是本项目 `progress.json` 的现有形态，**说明家俊的 JSON 路线与 Apache 顶级项目的选择一致**（见 R-1）。
- **是否适合本项目**：**需实测**（作为依赖：不推荐；作为架构参照：**强烈建议**）。
- **URL**：https://burr.apache.org/ （官方文档）｜https://github.com/apache/burr （官方仓库）｜https://pypi.org/project/apache-burr/

### [B-09] ⭐ PocketFlow（100 行）
- **是什么**：**整个框架 100 行、零依赖、MIT** 的图式 LLM 框架（`Node`/`Flow` + `prep/exec/post` 三钩子）。
- **为什么可用**：它是"**结构可读性**"的极致——README 自带对比表（LangChain 405K 行 /+166MB，CrewAI 18K 行 /+173MB，LangGraph 37K 行 /+51MB，**PocketFlow 100 行 /+56KB**）。仓库里带 **CLI HITL**、**Streamlit FSM**、**Multi-Agent**、**Parallel Flow**、**Heartbeat（常驻轮询监控）** 等教程，其中 **"Agent Skills：Route requests to reusable markdown skills and apply them in an agent flow"** 与本项目"skill + 规则文件"的形态高度同构。
- **接入成本**：**0 依赖**（PyPI `requires_dist` = 0，闭包 = 1）；**纯 Python**；**56KB**；官方明确推荐"**直接复制源码**"而非 pip 安装。
- **License**：**MIT**（仓级实测：`the-pocket/PocketFlow` 的 LICENSE 首行 "MIT License / Copyright (c) 2024 Zachary Huang"；GitHub API `spdx_id` = MIT）。
- **维护活跃度**：GitHub **11,208 stars / 1,199 forks**，**pushed_at 2026-07-26**（约 2 个月前），open issues 75，未 archived。⚠️ **PyPI 包 `pocketflow` 0.0.3 停在 2025-07-28**（作者确认为 Zachary Huang / 同仓库 Homepage），而 GitHub 已 640 commits → **PyPI 镜像滞后，唯一可靠获取途径是复制源码**。
- **风险**：① **无 license 声明于 PyPI metadata**（仓级 MIT 已核）；② 极简 = 无 Gate、无成本记账、无审计，**全要自己写**；③ 社区较小（11K stars vs LangGraph 42K）；④ 官方"零依赖"也是"无第三方保障"。
- **是否适合本项目**：**需实测**（论"抄 100 行的图执行核"值；论"整包依赖"因 PyPI 滞后而不可行）。
- **URL**：https://github.com/The-Pocket/PocketFlow （官方仓库）｜https://pypi.org/project/pocketflow/

### [B-10] LangGraph（1.2.12）
- **是什么**：LangChain 系的**图式状态机 + 检查点/持久化**运行时。官方文档确认：`compile(checkpointer=...)` → 每个 super-step 存一个 checkpoint；`interrupt()` + `Command(resume=...)` 做 HITL；`get_state_history` 做**时间旅行（回退到任一历史点并分叉）**；"durable execution：崩溃后从最后 checkpoint 恢复"。
- **为什么可用**：**概念上 100% 命中**本项目「断点三态 + Gate 暂停 + 回放」。它的"每个 super-step 一个 checkpoint / thread_id 划分"设计，是"断点恢复"这一主题上最成熟的工业实现。
- **接入成本**：**langgraph 闭包 = 40 包**；**`langgraph-checkpoint` 单独用也要 37 包**（因为它硬依赖 `langchain-core` + `langsmith`，实测闭包成员含 requests/httpx/websockets/orjson/zstandard/ormsgpack/pydantic 全套）；纯 Python（`py3-none-any`）；`requires_python >=3.10`。
- **License**：**MIT**（仓级实测：`langchain-ai/langgraph` LICENSE 首行 "MIT License / Copyright (c) 2024 LangChain, Inc."；`info.license_expression` = MIT）。
- **维护活跃度**：**langgraph 1.2.12 @ 2026-09-21**；`langgraph-checkpoint 4.2.0 @ 2026-08-07`；GitHub **42,490 stars**，**pushed_at 2026-09-29**，open issues 836，**非常活跃**。
- **风险**：① **依赖闭包 40 包（或仅 checkpoint 37 包），与"零依赖"硬约束正面对撞**，必然过不了"任何要装第三方依赖的决策须过尽调"；② **框架绑定**：checkpoint 不是独立库，抽不出来用；③ `checkpointer` 需生产级后端才算真 durable（InMemorySaver 进程重启即丢，官方明说）→ **被迫引 Postgres/SQLite**，与 D-17「本地 CLI 无服务端」冲突；④ 需要把代码写成"图 + 节点"，**要把现有 7 个脚本重写**（违反 §七）。
- **是否适合本项目**：**不适合**（概念可学，依赖不可引——见 R-1）。
- **URL**：https://docs.langchain.com/oss/python/langgraph/persistence （官方文档）｜https://langchain-ai.github.io/langgraph/ ｜https://github.com/langchain-ai/langgraph （官方仓库）

### [B-11] CrewAI（1.15.23）——思想来源，实测见 §4
- **是什么**：角色分工式多 agent 框架（`Agent`/`Task`/`Crew`/`Process`）。
- **接入成本**：**闭包 141 包**（含 chromadb / lancedb / onnxruntime / kubernetes / opentelemetry / openai / instructor / mcp 全套）。
- **License / 维护**：见 §4 专项。
- **是否适合本项目**：**不适合**（详见 §4）。
- **URL**：https://github.com/crewAIInc/crewAI

### [B-12] Prefect 3.8.7 / Dagster 1.13.24 / Airflow
- **是什么**：三个生产级数据/任务编排平台。
- **为什么可用**：调度、重试、可观测性成熟——**但全是"数据管道"心智，不是"合规闸"心智**。
- **接入成本**：Prefect **闭包 106 包**（直接依赖 57）；Dagster **闭包 55 包**（直接 32）；Airflow **闭包 122 包**。全部含 SQLAlchemy/Alembic/FastAPI/OpenTelemetry/Jinja2 等 web+DB 栈。
- **License**：Prefect Apache-2.0｜Dagster Apache-2.0｜Airflow Apache-2.0（实测）。
- **维护活跃度**：Prefect 2026-09-27｜Dagster 2026-09-21｜Airflow 2026-09-17（全部活跃）。
- **风险**：**依赖面超出本项目两个数量级**；且需要 `~/.prefect` 服务的守护进程（Prefect 会起本地 API/UI），**与"无服务端"直接冲突**。
- **是否适合本项目**：**不适合**。
- **URL**：https://www.prefect.io/ ｜https://dagster.io/ ｜https://airflow.apache.org/

### [B-13] Temporal（temporalio 1.33.0）
- **是什么**：durable execution 引擎（workflow/activity，确定性重放，崩溃可续跑数年）。
- **为什么可用**：**"断点恢复"这件事的工业天花板**——它把持久化做成了运行时保证（replay 重建状态）。
- **接入成本**：**Python SDK 闭包仅 7 包**（temporalio + nexus-rpc + protobuf + python-dateutil + six + types-protobuf + typing-extensions）——**依赖面出乎意料地小**；但 wheel 是**编译产物**（`cp310-abi3` 多平台），非纯 Python。
- **License**：**MIT**（PyPI `license_expression` + classifier 双证）。
- **维护活跃度**：1.33.0 @ **2026-09-15**；月下载量 3000 万+ ❓（来源为第三方站 skillfed.io，**未独立核实**）。
- **风险**：⭐ **必须跑一个 Temporal Server**（官方 Quickstart 第一步即 `temporal server start-dev`，worker + client + cluster 三件套；Docker 或 CLI 起服务）。**这与 D-17「本地 CLI + 项目工作区、服务端后置」是正面冲突**。另外它要求 workflow 代码**确定性**（不能有随机/IO 副作用），本项目"调用 LLM"本质不确定，**模型不匹配**。
- **是否适合本项目**：**不适合**（需求不匹配 + 需服务端）。
- **URL**：https://docs.temporal.io/develop/python/set-up-your-local-python （官方文档）｜https://pypi.org/project/temporalio/

### [B-14] Dify / n8n（可视化编排）
- **是什么**：可视化（拖拽）编排平台（Dify 偏 LLM 应用，n8n 偏工作流自动化）。
- **为什么可用**：**不适用**——D-17 已明确"UI 不产生价值，闸才产生价值"；且两者都是 **Web 服务 + 前端栈**（n8n 是 Node）。
- **接入成本**：需 Node/Docker + 数据库；非纯 Python；非零依赖。
- **License**：**未实测（❓）**——两者均有"开源版 + 商业版"的双许可结构（n8n 为 fair-code/Sustainable Use License 类），**不适合作为可嵌入组件**，但**本次未取数，故不列结论**。
- **是否适合本项目**：**不适合**（形态冲突：可视化平台 vs 本地 CLI 闸）。
- **URL**：https://dify.ai/ ｜https://n8n.io/ （❓ License 待核）

### [B-15] AG2 / AutoGen / OpenAI Agents SDK / LlamaIndex Workflows / Agno / MS Agent Framework
- **是什么 / 实测**：
  - **microsoft/autogen**：⚠️ **已进入 maintenance mode（2025-10 起），社区托管，不再加新功能**（官方 README + 微软 devblog 双证）。**实测其 GitHub 仓库根 `LICENSE` 内容为 "Attribution 4.0 International"（CC-BY-4.0）** —— 一个**软件仓库挂着 CC 内容许可**，本身即警示（该仓已退化为"指路牌"）。PyPI `autogen-agentchat` 最新发版 **2025-09-30（一年前）**，闭包 11 包。
  - **Microsoft Agent Framework**（继任者，合并 AutoGen + Semantic Kernel）：`agent-framework` **1.19.0 @ 2026-09-18**，闭包 **11 包**，**MIT**（classifier + 仓级 LICENSE 首行 "MIT License"），GitHub **13,872 stars**，pushed 2026-09-29。官方定位含 "Graph-based workflows … with streaming, checkpointing, and human-in-the-loop support"。**风险**：面向 Azure/微软生态（`AzureCliCredential` 等），且 2026-04 才 GA，API 仍新。
  - **AG2**（AutoGen 社区分支）：Apache-2.0，4,969 stars，pushed 2026-09-29，活跃。
  - **openai-agents**：0.22.3 @ **2026-09-17**，闭包 ❓（56 条 requires_dist），**MIT**，GitHub `openai/openai-agents-python` **29,774 stars**，pushed **2026-09-30（今天）**——**极活跃**。但它是"agent 运行循环"而非"状态机 + 闸"。
  - **llama-index-workflows**：2.25.0 @ **2026-09-25**，**闭包仅 9 包**，MIT，GitHub `run-llama/workflows`（仓级 LICENSE = MIT）。**轻量度仅次于 burr**，是"事件驱动 workflow"里依赖面最小的之一。
  - **agno**：3.0.11 @ 2026-09-23，Apache-2.0（PyPI license 字段内嵌完整 Apache 全文），但 **396 条 requires_dist**（❓ 闭包未算完，量级明显 ≥50）。
- **为什么可用（正面）**：若将来 D-17 转向"多机/服务端"，**MS Agent Framework 与 llama-index-workflows 是依赖面最可控的两个**（11 / 9 包）。
- **是否适合本项目**：**不适合**（形态/生态偏离本地 CLI + 零依赖）。
- **URL**：https://github.com/microsoft/agent-framework ｜https://github.com/microsoft/autogen ｜https://github.com/ag2ai/ag2 ｜https://github.com/openai/openai-agents-python ｜https://github.com/run-llama/workflows

---

## 3. 核心问题 3：断点恢复/检查点 —— `langgraph.checkpoint` / `dill` / `cloudpickle` / JSON？

### 3.1 实测数据

| 方案 | 闭包 | License | 最新发版 | 产物形态 |
|---|---|---|---|---|
| `langgraph-checkpoint` | **37 包**（拖 `langchain-core` + `langsmith`） | MIT | 2026-08-07 | 序列化 state 快照（默认 ormsgpack） |
| `dill` | **1 包（零依赖）** | BSD-3-Clause | 2026-01-19 | **pickle 二进制**（人类不可读） |
| `cloudpickle` | **1 包（零依赖）** | BSD-3-Clause | 2025-11-03 | **pickle 二进制**（人类不可读） |
| **现有 `progress.json`** | **0**（stdlib `json`） | PSF | — | **JSON 文本（人类可读、可 git diff、可 grep）** |
| `msgspec`（JSON 加速） | 1 包，但**是 C 扩展** | BSD-3-Clause | 2026-09-29 | JSON/MessagePack |

### [B-16] ⭐ 反转性结论：**现有 `progress.json` 就是正确答案，不值得升级**
- **是什么**：家俊现用 `progress.json` 存 JSON 三态（`modules` / `expected_products` / `lifecycle`），实测由 `checkpoint.py` 与 `lifecycle.py` **共用同一文件**。
- **为什么可用（证据链）**：
  1. **顶级项目选择一致**：Apache Burr 的官方描述即"**your state is a plain dictionary you can inspect, persist, and replay**"、"State 是普通 dict，可 inspect/persist/replay"，并强调**可版本控制、可调试**——**与家俊的 JSON 路线同构**。
  2. **`langgraph-checkpoint` 抽不出来用**：实测其闭包 37 包，硬绑 `langchain-core` + `langsmith` → **想"只用它的断点"是不可能的**。
  3. **`dill` / `cloudpickle` 解决的是"序列化任意 Python 对象（含函数/闭包）"的问题**，而本项目的状态是**纯数据（模块名 / 三态枚举 / 文件路径）**，**不需要 pickle**；引入 pickle 反而制造三个新问题：**(a) 不可读**（违反规则 80「取证优先」与 rule 82「行号锚定」）；**(b) 不可 git diff**；**(c) 反序列化即执行任意代码 = 安全面**（D-20「将来给他人用」时是硬伤）。
  4. **JSON 的缺陷（无 schema 强制、无原子写）与项目当前规模不成比例**：现有脚本已通过 `checkpoint.py verify`（磁盘 stat 核验）补齐了"数据真实存在"这层。
- **接入成本**：升级到 `dill` = 1 依赖（但引入上述 3 个风险）；升级到 `langgraph-checkpoint` = 37 依赖（不可接受）；**保持 JSON = 0**。
- **License**：不适用（自持）。
- **维护活跃度**：不适用。
- **风险**：JSON 方案的**真实缺口**只有两条，且都不需要框架：**(a) 无 JSON Schema 校验**（现有 `validate_output.py` 已是"JSON+Schema"校验原语！）；**(b) 非原子写（写一半崩溃会毁掉状态文件）**→ 可用 stdlib `os.replace()`（同目录临时文件 + rename）解决，**零依赖**。
- **是否适合本项目**：**现状已适合**（若真要加固，走"`validate_output.py` 上 Schema + `os.replace()` 原子写"，而非引框架）。
- **URL**：https://burr.apache.org/ （官方文档，作为"顶级项目同样选 plain dict"的旁证）｜https://docs.python.org/3/library/os.html#os.replace （官方文档）

### [B-17] python-statemachine 3.2.1（若真要状态机库）
- **是什么**：声明式状态机（`State`/`Transition`/`Event`），支持回调、条件、嵌套。
- **为什么可用**：**闭包 = 1 包（零依赖）、纯 Python、MIT、2026-08-01 仍在发版**——是"状态机库"里最干净的一个，对应 `lifecycle.py` 的五态转移表。
- **接入成本**：**1 个依赖**；纯 Python。
- **License**：**MIT**（PyPI `info.license` = `MIT License` + classifier）。
- **维护活跃度**：3.2.1 @ **2026-08-01**，`requires_python >=3.10`。
- **风险**：`lifecycle.py` 的转移表**已经用 30 行硬编码实现且有审计与 Gate 证据门**（docstring 实测："★ Gate 证据门 rule 63/51 引擎化：EXECUTING→DELIVERED 需 `--evidence-file`"）；换成库**是把 30 行换成 1 个依赖 + 重写**，且新库**不知道"证据门"是什么**（要自己写条件函数，代码量不减）。
- **是否适合本项目**：**不适合**（现状已够，收益为负）。
- **URL**：https://pypi.org/project/python-statemachine/ ｜https://github.com/fgmacedo/python-statemachine

### [B-18] transitions 0.9.3
- **是什么**：老牌 Python 状态机库（`Machine`/`add_transition`），支持 HierarchicalMachine。
- **为什么可用**：功能全、文档多。
- **接入成本**：**2 包**（transitions + **six**）；纯 Python。
- **License**：**MIT**（PyPI `info.license`）。
- **维护活跃度**：0.9.3 @ **2025-07-02**（约 15 个月前），**发版节奏偏慢**。
- **风险**：**依赖 `six`**（py2/py3 兼容垫片，2025 年了还在拖 py2 时代的包）；发版间隔长。
- **是否适合本项目**：**不适合**。
- **URL**：https://github.com/pytransitions/transitions

---

## 4. ⭐ 核心问题：CrewAI 实测专项结论

| 实测项 | 结果 | 证据 |
|---|---|---|
| 最新版本 | **1.15.23** | PyPI JSON `info.version` |
| 发版日期 | **2026-09-28**（2 天前） | `urls[0].upload_time` |
| **License（PyPI）** | **`None`**（未声明；`license_expression` 亦为 `None`，无 License classifier） | PyPI JSON |
| **License（仓级）** | **MIT** | GitHub `crewAIInc/crewAI` 的 `LICENSE` @ main：首行 "Copyright (c) 2025 crewAI, Inc." + MIT 授权文；GitHub API `license.spdx_id` = `MIT` |
| **`requires_python`** | **`<3.14,>=3.10`** ⚠️ | PyPI JSON |
| **依赖闭包** | **141 包** | 本机 `dep_closure.py` 实测 |
| 直接依赖 | 31 条（含 `chromadb` / `lancedb` / `onnxruntime` / `kubernetes` / `opentelemetry-sdk` / `instructor` / `mcp` / `openai>=2.30` / `tokenizers`） | PyPI `requires_dist` |
| 仓库活跃度 | **59,197 stars**，pushed **2026-09-29**（昨天），open issues 504，未 archived | GitHub API |
| 首版 | 0.1.0 @ 2023-11-14 | PyPI releases |

### ⚠️ 硬阻断发现（D-15/引擎层必读）
**CrewAI `requires_python = <3.14`，而家俊本机主 Python 是 `3.14.3`（engine 的托管版）**
→ **在 3.14.3 上 `pip install crewai` 会被直接拒绝**。
本机另有 `3.13.12`，**只在 3.13.12 上可装**。
→ 这意味着：**即使家俊想"拿来改造"，也必须先解决"引擎跑在哪个 Python 上"**（而 `runtime_probe.py` 实测本机默认是 3.14.3）。

### 结论：**不适合拿来改造，推荐继续自建**
三条理由（按证据强度排）：

1. **依赖面与硬约束正面对撞**（实测）：**141 包** vs 本项目"零依赖优先"（D-11）+「任何要装第三方依赖的决策须过尽调」。141 包的尽调**不可能过**，且其中 `kubernetes` / `chromadb` / `onnxruntime` / `lancedb` 与"合规闸"零关系。
2. **模型不匹配（更本质）**：CrewAI 的抽象是 **`Agent`(角色) + `Task` + `Crew` + `Process`（sequential/hierarchical）**。本项目六层框架的核心资产是 **Phase/Wave/模块三态 + Gate 硬拦截 + 成本账本（cost_log 定长行）+ 生命周期五态 + 经验蒸馏闭环**——**这五样里没有一样是 CrewAI 的原生概念**。CrewAI **没有 Wave 三态、没有 Gate 硬拦截、没有成本记账、没有蒸馏闭环**。拿它回来包装 = **在别人的模型上重新发明自己的模型**。
3. **本框架已经脱离 CrewAI 演化了 8 个大版本**（`SKILL.md` 版本 banner 实测：v3.9.13 → v3.13.0 → v3.14.x → v3.16.0 → v3.17.0 → v3.18.0 → v3.19.0 → v3.20.0）。`SKILL.md` Overview 自述"把家俊的 CrewAI 六层框架在 WorkBuddy 原生多 Agent 能力上完整落地"——**CrewAI 是"思想起点"，不是"当前实现"**。回退到 CrewAI = **降级**。
4. **Python 版本硬阻断**（见上）。

**唯一值得从 CrewAI 拿走的**：无（其角色分工思想已在 SKILL.md 里被消化为 Layer0-L5 + 三类子 Agent）。

---

## 5. 核心问题 4：任务卡 lint（D-15 的 `dispatch-check`）

**现状实测**：`six_layer_check.py` **已有 `dispatch-check` 子命令**（`argv[0] == "dispatch-check"` → `check_dispatch_card(args[0])`，支持 `--force-with-reason=` 强制跳过并留痕），且 v3.17.0 banner 记录"rule 78 dispatch-check + write-conflict + audit 进 Wave Gate"。
→ **`dispatch-check` 不是"要不要做"，而是"要不要换成现成工具"。**

### [B-19] `promptlint-cli` 1.3.0（ESLint for prompts）
- **是什么**：LLM 提示词的**静态分析器**（本地跑、无 API 调用）。规则：token 成本估算、`prompt-injection` 检测（含 leetspeak/unicode 混淆 evasion）、`structure-sections`（是否含 Task/Context/Output 分节）、`clarity-vague-terms`（"some/stuff/maybe"）、`politeness-bloat`（please/kindly，纯烧 token）、`verbosity-sentence-length`（>40 词句子）、`consistency-terminology`（混用 user/customer）、`completeness-edge-cases`；支持 `--fix` 自动修复、`.promptlintrc` 配置、CI 模式（`--fail-level` / `--quiet`）。
- **为什么可用**：**"任务卡 lint"这个抽象是真实存在且已有开源实现的**——它的 `structure-sections`（缺 Task/Context/Output 分节就 WARN）与本项目"任务卡三件套/六项固定"的检查**语义最接近**；`prompt-injection` 检测可作为**安全层**补充。
- **接入成本**：**6 包**（promptlint-cli + markdown-it-py + mdurl + pygments + rich + pyyaml）；`requires_python >=3.9`；纯 Python。
- **License**：**Apache-2.0**（PyPI `license_expression` 实测；`info.license` 为 `None`）。
- **维护活跃度**：1.3.0 @ **2026-04-13**；**首版 2026-03-10（仅半年）**，5 个发版。⚠️ **项目非常年轻**。
- **风险**：① **语义错配（关键）**：它 lint 的是"**提示词质量/成本**"（分节、措辞、注入），**不是"任务卡的必填字段完整性"**（本项目要的是"六项固定项是否齐""是否声明写哪些文件""是否带检索三环"）。**它能替代的是"措辞层"，替代不了"契约层"**；② 项目半年新，规则集可能变；③ 引入 6 包为一条 WARN 规则，性价比低。
- **是否适合本项目**：**需实测**（建议：**抄它的规则清单**用于扩充 `dispatch-check` 的检查项，**不装包**）。
- **URL**：https://pypi.org/project/promptlint-cli/ ｜https://github.com/AryaanSheth/promptlint （活跃仓库）

### [B-20] LangPatrol（Pre-inference Prompt Validation）
- **是什么**：商业公司的"推理前提示词校验"产品（自称 "Think ESLint for LLM prompts"），有 **open-source core + Node SDK + CLI**。
- **为什么可用**：与本项目 `dispatch-check` / D-13（调用前 enforcement）**定位几乎一模一样**（"catch missing context / schema risks / ambiguity **before** you call the model"）。
- **接入成本**：**CLI 是 `npm install -g langpatrol-cli`** → **需要 Node**（本机有 Node 22.22.2，但**引擎硬约束是 Python-only**）；SDK 是 Node（`npm install langpatrol`）。**非 Python**。
- **License**：**❓ 未实测**（官网自称"Open-source core"，但**未给出 SPDX、未核仓库**；且核心校验有"escalate to our API for an LLM judge"的云服务形态）→ **未能证实**。
- **维护活跃度**：**❓ 未取数**（无 PyPI 包，npm 包未核）。
- **风险**：① **Node 依赖**（与 Python-only 引擎冲突）；② **混合云形态**（部分能力走它家 API）→ 与 D-20「无凭据落盘 / 本地优先」冲突；③ License 不可核。
- **是否适合本项目**：**不适合**（形态 + License + 语言三重错配）。**仅作"这个产品形态已被验证有市场"的信号**。
- **URL**：https://www.langpatrol.com/ （活跃仓库/官网，**非官方标准**）

### [B-21] 结构化校验原语：`jsonschema` / `check-jsonschema` / `voluptuous` / `msgspec`
- **是什么**：JSON Schema 校验链。
- **为什么可用**：**`validate_output.py` 已经实现了"JSON + Schema 校验"原语（实测 97 行，位置参数 `<file> <schema>`）** → 任务卡（YAML/JSON 形态）的字段完整性校验**已有载体**。
- **接入成本**：`jsonschema` **6 包**（attrs/referencing/rpds-py/jsonschema-specifications/typing-extensions）；`check-jsonschema`（CLI）**16 包**（含 requests/ruamel.yaml/click）；`voluptuous` **1 包零依赖**；`msgspec` **1 包但为 C 扩展**（非纯 Python）。
- **License**：jsonschema MIT｜check-jsonschema Apache-2.0｜voluptuous BSD-3-Clause｜msgspec BSD-3-Clause（均实测）。
- **维护活跃度**：jsonschema 4.26.0 @ 2026-01-07｜check-jsonschema 0.38.2 @ 2026-09-23｜voluptuous 0.16.0 @ 2025-12-18｜msgspec 0.22.0 @ 2026-09-29。
- **风险**：① 任务卡当前是 **Markdown**（`task_templates` / `task-brief.md` 形态，实测本次任务书即 Markdown）→ **JSON Schema 校验不上 Markdown**，需要"先解析成结构"这一步（这一步才是真正的工作量，任何库都省不掉）；② `check-jsonschema` 16 包含 requests/yaml，为一个 CLI 引 16 包不划算。
- **是否适合本项目**：**需实测**（若任务卡定型为 YAML/JSON → `validate_output.py` 足够；若保持 Markdown → 必须自写结构提取，无现成件）。
- **URL**：https://python-jsonschema.readthedocs.io/ ｜https://github.com/python-jsonschema/check-jsonschema

---

## 6. 核心问题 5：D-17「本地优先、项目目录即工作区」的同类架构参考

### [B-22] Aider（aider-chat）—— ⚠️ 参考价值已下降
- **是什么**：终端里的 AI 结对程序员，"repo 即工作区"的经典本地优先形态。
- **为什么可用**：**架构上最贴 D-17**（纯本地 CLI、无服务端、状态落项目目录），且有成熟的"git 集成 / repo map / 文件选择"设计可借鉴。
- **接入成本**：**闭包 123 包 / 直接依赖 108 条** ⚠️（本次实测最大意外之一）；纯 Python。
- **License**：**Apache-2.0**（仓级实测 `Aider-AI/aider` 的 `LICENSE.txt` 首行 = Apache License 2.0；GitHub API `spdx_id` = `Apache-2.0`）。⚠️ PyPI `info.license` 为 `None`。
- **维护活跃度**：**PyPI 最新发版 2026-02-12（约 7 个月前）**；GitHub **pushed_at 2026-05-22（约 4 个月前）**，49,286 stars，**open issues 1,902**，未 archived。→ **活跃度明显低于本报告其他项目**。
- **风险**：依赖面 123 包（含 litellm/networkx/boto3/numpy/pillow/openai）；发版与 push 节奏放缓。
- **是否适合本项目**：**不适合**（依赖面 + 活跃度双降）。**"repo 即工作区"这一条已被 D-17 采纳，不需要看它**。
- **URL**：https://github.com/Aider-AI/aider

### [B-23] OpenHands（原 OpenDevin）
- **是什么**：能"写代码 + 跑命令 + 浏览网页"的自主 agent 平台（本地 Docker / 云端）。本地优先形态的标杆之一。
- **为什么可用**：它的"**事件流（event stream）+ 沙箱 runtime + 可回放**"设计，与本项目"派发/审查/回放"有同构点；`runtime_probe.py` 的"环境探测"角色也与之同族。
- **接入成本**：**闭包 ❓**（本次未实测，但形态为 Docker 化平台，必然远大于 1 依赖）；非纯 Python 单体。
- **License**：**MIT**（仓级实测：`LICENSE` 首行 "The MIT License (MIT) / Copyright © 2025 OpenHands contributors"）。⚠️ GitHub API 返回 "Moved Permanently"（仓库已改名/迁移，**新路径未核**）。
- **维护活跃度**：**❓**（因 API 跳转，本次未取到 stars/pushed_at）。
- **风险**：**需要 Docker / 沙箱 runtime**（与服务端化同向），且当前沙箱环境本身禁止某些子进程（本次实测 `runtime_probe` 触发了沙箱对 `wsl.exe` 的黑名单拦截提示）→ **本地 CLI 化落地成本高**。
- **是否适合本项目**：**不适合**（形态过重）。
- **URL**：https://github.com/All-Hands-AI/OpenHands （→ 已 301，新名未核 ❓）

### [B-24] Cline（VS Code 扩展）
- **是什么**：VS Code 内的本地编码 agent 扩展，"项目目录即工作区"的另一种落地。
- **为什么可用**：可作为"用户极简入口"（D-22 的 P3 项）的形态参照。
- **接入成本**：**TypeScript / Node / VS Code 扩展宿主** → **非 Python**。
- **License**：**❓ 未实测**。
- **维护活跃度**：**❓ 未取数**。
- **风险**：语言与宿主环境双重错配（引擎是 Python + CLI）。
- **是否适合本项目**：**不适合**（本次未取数，仅形态参照）。
- **URL**：❓（未核）

### [B-25] ⭐ 真正对 D-17 有用的"本地优先"证据：`pre-commit` 的形态
- **是什么**：**"本地、零服务端、配置即声明、薄入口 + 插件"的 Python 生态标杆**（`.pre-commit-config.yaml` → hook 声明 → 本地执行）。
- **为什么可用**：这正是 D-15 想要的 `cli.py` 形态——**一个薄入口（`cli.py`）+ 一份声明（子命令 ↔ 脚本映射）**。实测 `pre-commit` 自身闭包 12 包（**不需要装它，只需要它的形态**）。
- **接入成本**：借鉴形态 = **0 依赖**。
- **License**：**MIT**（PyPI `info.license` = `'MIT'`）。
- **维护活跃度**：4.6.2 @ **2026-08-10**（首版 2014-06-17，**12 年持续维护**，`>=3.10`）。
- **风险**：无（不引入）。
- **是否适合本项目**：**适合**（**仅作为 `cli.py` 的形态参照**）。
- **URL**：https://pre-commit.com/ （官方文档）

---

## 7. ⭐ 反转性发现（≥2 条，实为 7 条）

### R-1｜**LangGraph 不值得引——但理由不是"重"，而是"它抽不出来"**
直觉是"LangGraph 40 包太重"。**实测更狠**：想只取"断点/检查点"这层，`langgraph-checkpoint` **单独也要 37 包**（硬依赖 `langchain-core` + `langsmith`）。**"借它的检查点"这条路根本不存在**——它不是可拆的库，是一整套生态的入口。
**反向对照**：家俊的 `progress.json`（JSON 三态、0 依赖、人类可读、可 git diff）**与 Apache Burr 官方主打的 "state is a plain dictionary you can inspect, persist, and replay" 是同一个设计选择**。**你现在的方案不是"简陋版"，是"和 Apache 顶级项目撞了同一个答案"。**
→ 升级成本若真要花，应花在"JSON 加 Schema + 原子写（`os.replace`）"，**不是换成 37 包的框架**。

### R-2｜**"想引依赖"的话该引 Click 而不是 Typer——但更该一个都不引**
社区共识是"Typer 比 argparse 好用"。**实测翻案**：`click` 的 `requires_dist` = **0 条（闭包 1 包）**，而 `typer` 闭包 **8 包**、`cyclopts` **8 包**、`cappa` **8 包** —— 后三者**都被 `rich` 系渲染链绑住**。
所以"引框架"的正确答案若是 Click（1 包），**但 §1.2 的实测把问题直接消掉了**：7 个脚本**已可零改动 import + 复调 `main()`**（0.032s），命令体是"转发"，**框架的核心优势（从签名生成 CLI）完全用不上**。
→ **结论：argparse（0 包）不是"将就"，是在这个具体接缝下的最优解。**

### R-3｜**真正的"整体借鉴架构"不是 CrewAI/LangGraph，是 Apache Burr（0 依赖）**
被点名要查的都是重框架，**但命中本项目三个核心概念（状态机 + 持久化恢复 + HITL）且零依赖的，是 Apache Burr**：`@action(reads, writes)` + 不可变 `State` + `halt_after` + `.with_state_persister()`。**Apache-2.0、纯 Python、闭包 1 包、昨天还在 push、已捐给 Apache 基金会**。
→ **它的四件事可以"人肉搬进 cli.py"（declared reads/writes、halt_after、不可变快照、plain dict state），而不用装它。**

### R-4｜**CrewAI（思想来源）在 3.14 上装不上，且已 141 包**
"能不能拿 CrewAI 改造"的答案，被一个**硬事实**打断：`crewai 1.15.23` 的 `requires_python = <3.14`，而本机引擎默认 Python 是 **3.14.3**（`runtime_probe.py` 实测）。**装都装不上**（除非切到 3.13.12）。
叠加 **141 包闭包**，以及**它的模型里没有 Wave 三态 / Gate / 成本账本 / 蒸馏闭环**——**回退 CrewAI 是双重降级**。

### R-5｜**`docopt` 已停维 12 年，且仓库根目录找不到 LICENSE 文件**
PyPI 最新发版 **2014-06-16**（12 年前）。更值得注意：实测回仓核验时，`docopt/docopt` **默认分支未找到任何常见 LICENSE 文件名**（`LICENSE` / `LICENSE.md` / `LICENSE.txt` / `COPYING` 均 404），而 GitHub API 却报 `spdx_id = MIT`。
→ 这条对本项目有**方法论价值**：D-20 要求按"将来可能给他人用"的纪律写——**"PyPI 声明了 License 但仓库核不到"本身就是不自洽**。这正是本报告坚持"**PyPI JSON + GitHub raw 双核**"的原因（本报告已发现 **4 处 PyPI `info.license = None` 但仓级有明确 License**：crewai / apache-burr / pocketflow / aider）。

### R-6｜**AutoGen 已经"死了"，且其仓库挂的是 CC-BY-4.0 内容许可**
被广泛引用的 `microsoft/autogen`：**2025-10 起 maintenance mode、社区托管**（官方 README + 微软 devblog 双证），PyPI `autogen-agentchat` **最新发版 2025-09-30（一年前）**。**实测其仓库根 `LICENSE` 内容为 "Attribution 4.0 International"（CC-BY-4.0）** —— 一个软件框架挂内容许可，是"该仓已退化为指路牌"的信号。
继任者 **Microsoft Agent Framework**（`agent-framework` 1.19.0，**MIT**，13,872 stars，pushed 2026-09-29，**闭包 11 包**）——**如果将来 D-17 转向服务端多机，这是依赖面最可控的候选之一**。

### R-7｜**"任务卡 lint"有现成件（promptlint-cli），但它 lint 错了维度**
实测 `promptlint-cli`（Apache-2.0，闭包 6 包）：它查的是**提示词质量**（分节/模糊措辞/token 成本/**prompt 注入**），**不是任务卡的"必填字段契约完整性"**。
→ **它替代不了 `dispatch-check` 的契约层**（六项固定项 / 写文件声明 / 检索三环留痕），**只值得抄它的规则清单**去扩充 `dispatch-check`；`prompt-injection` 那条可作为**新检查项**（本项目尚未覆盖的安全维度）。
→ 且它**首版仅 2026-03-10**（半年新）——**不宜作为硬 Gate 的依赖**。

---

## 8. ⭐ 三张表

### 表一 · ✅ 可直接拿来用

| 编号 | 项目 | 拿来做什么 | 接入成本 | License | 关键实测证据 |
|---|---|---|---|---|---|
| B-01 | **stdlib `argparse`** | `cli.py` 顶层 + 10 类子命令分发 | **零依赖** | PSF-2.0 | 7 脚本可 import 实测通过；闭包 0 |
| B-07 | **"git-hooks 式"薄入口**（自写 ~120 行） | 用字典声明"子命令 → (模块, argv 模板)" | **零依赖** | 自研 | 串联原型 5 条命令实测全 exit=0 |
| — | **`progress.json`（现状，不新增）** | 断点三态持久化 | **零依赖** | 自持 | Apache Burr 官方同选"plain dict"；langgraph-checkpoint 抽不出来（37 包） |
| B-25 | **`pre-commit` 的形态** | `cli.py` 的"薄入口 + 声明"架构参照 | **0（不装）** | MIT | 闭包 12 包但**不需装**；12 年持续维护 |
| B-08 | **Apache Burr 的 4 个设计点** | 搬进 `cli.py`：`reads/writes` 声明 / `halt_after` / 不可变快照 / plain dict state | **0（抄思想，不装）** | Apache-2.0 | `apache-burr` 闭包 **1**；仓级 LICENSE 首行 Apache-2.0；pushed 2026-09-29 |
| B-09 | **PocketFlow 的 100 行源码** | 读它的 `Node/Flow` 图执行核（56KB，可整体读懂） | **0（复制源码）** | MIT | 仓级 LICENSE "MIT / Copyright (c) 2024 Zachary Huang"；11,208 stars |
| B-19 | **`promptlint-cli` 的规则清单** | 抄去扩充 `dispatch-check`（尤其 `prompt-injection` 这条本项目缺的） | **0（抄清单）** | Apache-2.0 | 闭包 6 包；规则集见 README |
| — | **stdlib `os.replace()`** | `progress.json` 原子写（补 JSON 方案唯一真缺口） | **零依赖** | PSF-2.0 | 官方文档；见 B-16 风险段 |

### 表二 · ⏳ 需改造后自用（或需先实测）

| 编号 | 项目 | 待验证/待改造点 | 成本 |
|---|---|---|---|
| — | **`cli.py` 退出码层** | ⚠️ 实测：`checkpoint`/`cost_log`/`lifecycle` 的 `main()` **大多不 `sys.exit()`** → 包装层必须 `try/except SystemExit` + 默认 0 + 显式 `sys.exit(code)`，否则 Gate 永远返回 0 | 零依赖，~10 行 |
| B-16 | **`progress.json` + `validate_output.py`** | 用现有 `validate_output.py` 给 progress.json 上 Schema；`os.replace()` 原子写 | 零依赖 |
| B-21 | **`validate_output.py` 作任务卡校验载体** | 任务卡现在是 **Markdown** → 必须先自写"Markdown → 结构"提取（**无现成件，任何库都省不掉这步**） | 零依赖 |
| B-08 | **Apache Burr（作为依赖）** | ⏳ 官方页写 "Python 3.12+" vs PyPI `>=3.9` **冲突**；3.14.3 实跑**未验证**；且会与 SKILL.md 形成双真相源 | 1 依赖（base） |
| B-19 | **`promptlint-cli`（作为依赖）** | ⏳ 项目仅半年新；语义只覆盖"措辞层"不覆盖"契约层" | 6 依赖 |
| B-17 | **`python-statemachine`** | ⏳ 若要替换 `lifecycle.py`：它的条件函数里**要重写"证据门"**，代码量不减 | 1 依赖 |
| B-06 | **`rich-argparse`** | ⏳ 唯一"不换解析器只美化 help"的选项 | 5 依赖 |
| B-15 | **`agent-framework` / `llama-index-workflows`** | ⏳ 仅当 D-17 转向服务端多机时才评估（依赖面 11 / 9 包，最可控） | 11 / 9 依赖 |
| B-20 | **LangPatrol** | ⏳ License ❓ / 需 Node / 有云 API 成分 → 三重错配，不建议 | Node |

### 表三 · ❌ 不采纳

| 编号 | 项目 | 一句理由（含实测数据） |
|---|---|---|
| B-03 | **Typer** | 闭包 8 包（rich 链），而命令体只是"转发"，优势用不上 |
| B-04 | **Cyclopts** | 闭包 8 包（同样含 rich 链），且项目仅 2 年 |
| B-02 | **Click** | 闭包虽仅 1 包，但被包对象已是"可 import 的模块"，收益 ≈ 0 |
| B-05 | **docopt** | 停维 12 年（2014-06-16）；仓库根无 LICENSE 文件 |
| B-06 | tyro / cappa / poethepoet | 5 / 8 / 4 包，收益仅"好看的 help" |
| — | **CrewAI** | **141 包** + **`requires_python <3.14`（本机 3.14.3 装不上）** + 模型不含 Wave/Gate/账本/蒸馏 |
| B-10 | **LangGraph / langgraph-checkpoint** | 闭包 40 / **37 包**（checkpoint 抽不出来）；durable 还需 Postgres/SQLite |
| B-12 | **Prefect / Dagster / Airflow** | 闭包 **106 / 55 / 122 包**；Prefect 还起守护进程 |
| B-13 | **Temporal** | **必须跑 Temporal Server**（与 D-17 正面冲突）；且要求 workflow 确定性，与"调 LLM"不匹配 |
| B-14 | **Dify / n8n** | 形态冲突（可视化 Web 平台 vs 本地 CLI 闸）；非 Python；License ❓ |
| B-15 | **AutoGen / Agno** | AutoGen 已 maintenance mode + 仓挂 CC-BY-4.0；Agno 396 条 requires_dist |
| B-11/B-15 | **OpenAI Agents SDK / AG2** | 是"agent 运行循环"不是"状态机 + 闸"；与本地 CLI 形态错配 |
| B-22 | **Aider** | 闭包 **123 包 / 直接依赖 108**；PyPI 发版停在 2026-02-12、push 停在 2026-05-22 |
| B-23 | **OpenHands** | 需 Docker/沙箱 runtime；仓库已 301 迁移（新址未核 ❓） |
| B-24 | **Cline** | TypeScript/VS Code 宿主，语言错配；本次未取数 ❓ |
| B-18 | **transitions** | 2 包（仍拖 `six`）；发版停在 2025-07-02 |
| B-20 | **LangPatrol** | 需 Node + License 不可核 + 云 API 成分 |

---

## 9. 未证实项清单（❓，禁止编造）

| # | 未证实项 | 说明 | 影响 |
|---|---|---|---|
| 1 | **Apache Burr 在 Python 3.14.3 上能否实跑** | 官方落地页写 "Python 3.12+"，PyPI metadata 写 `requires_python >=3.9`，**两处冲突**；本次只做元数据核验，**未实装实跑** | 若 HT 想引 burr，必须先跑一次探针 |
| 2 | **Cyclopts 在 3.14 上是否可用** | `requires_python >=3.11`（无上界），推测可用，**未实测** | 不引则无影响 |
| 3 | **LangGraph 1.1/1.2 的具体新 API**（v2 streaming / `GraphOutput` / v3 content-block） | 来源为第三方 AI wiki（aiwiki.ai），**非官方文档** | 本报告对 LangGraph 的结论（MIT / 40 包 / 官方持久化文档）均基于 PyPI + 官方 docs.langchain.com，不受影响 |
| 4 | **各包 wheel 的实际磁盘安装体积（MB）** | 本次实测的是"**装包数量**"（闭包大小），**未下载度量 MB** | 若 HT 要"体积"数字，需另跑 `pip download` + 度量 |
| 5 | **`pocketflow` PyPI 包与 GitHub 仓库是否同源同码** | PyPI `project_urls` 指向 `the-pocket/PocketFlow`，作者 Zachary Huang 一致；但 **PyPI 停在 0.0.3 / 2025-07-28，而 GitHub 已 640 commits** → **镜像滞后**，同源性**未逐行比对** | 结论已保守处理（建议复制 GitHub 源码） |
| 6 | **n8n / Dify / Cline 的 License 与活跃度** | 本次**未取数** | 三者均已被"形态冲突"排除，不影响结论 |
| 7 | **OpenHands 迁移后的新仓库路径与 stars** | GitHub API 返回 "Moved Permanently"，**新路径未核** | 不影响"形态过重"的结论 |
| 8 | **LangPatrol 的 License / npm 包活跃度** | 官网自称 "Open-source core" 但**未给 SPDX、未核仓库**；npm 侧未取数 | 已按"三重错配"排除 |
| 9 | **Temporal 的月下载量 30.4M** | 来源为第三方站 skillfed.io 的 AI 摘要，**未独立核实** | 不影响"需服务端"的结论 |
| 10 | **`tyro` / `cappa` / `rich-argparse` / `poethepoet` 的 wheel 体积与 3.14 实跑** | 只取到元数据（版本/依赖/License/日期），**未实装** | 均已被"收益不足"排除 |
| 11 | **`msgspec` 的 Windows wheel 在 3.14.3 上是否可用** | 实测 wheel 名为 `cp310-cp310-macosx...`（**C 扩展**），未核 Windows/3.14 轮子 | 不引则无影响 |
| 12 | **`six_layer_check.py` 中 `dispatch-check` 的现有检查项完整清单** | 本次只核到入口与调用点（`check_dispatch_card`），**未逐项读完 1637 行** | ⚠️ **建议 HT 让实现者补一份"现有检查项清单"**，否则 R-7 的"该抄什么"会重复劳动 |

---

## 10. 一句话交给 HT 的证据摘要（不替 HT 拍板）

1. **D-15**：实测 7 个脚本**全部可零改动 import + 复调 `main()`**（0.032s）→ 「包住它们」不需要框架。`argparse` 闭包 **0**；`click` **1**；`typer` **8**；`cyclopts` **8**；`docopt` **停维 12 年**。**唯一必须自己补的一层是"退出码规范"**（3 个脚本不 `sys.exit()`）。
2. **D-15/D-16 的新增命令（design / compress / route-error）**：`design --finalize` / `route-error` **不在本扫描员分工范围内**（路由规则表属扫描员 A 的"错误路由"题）；`compress`（rule 83 三级级联）属**扫描员 C**的分工（"上下文压缩与摘要 · LLMLingua 类"）。**本次 B 未命中"可直接复用的实现"，但这不等于"没有"——请以 A / C 的报告为准，勿据本条下结论。** → 无论如何，三条新命令按 D-16 都**必须自带自测用例**。
3. **D-17**：本地优先形态的最优参照是 **`pre-commit` 的"薄入口 + 声明"** 与 **Apache Burr 的 action/state 模型**；而 `aider`（123 包 / push 停在 2026-05）与 `OpenHands`（Docker）**已不适合做参照**。
4. **D-19（多项目并行）**：**未找到**"本地多项目状态隔离"的开源直接件（本次未命中）——所有编排引擎都是"服务端 + 多租户/多 workspace"，与"先隔离、母板后置"不同构。→ **自建**。
5. **CrewAI**：`requires_python <3.14`（本机 3.14.3 **装不上**）、**141 包**、模型不含本框架四个核心资产 → **不适合拿来改造**。
