# 扫描员 C · 规则校验 / Gate / 自测网 / 状态板 / 上下文压缩（引擎层研讨 2026-09-30）

> **分工**：六层编排框架「引擎层本体」开源扫描 · C 线（D-16 自测网 / schema 校验 / D-13 token 预算 / D-02 状态板 / rule 83 压缩 / 假绿检测）
> **纪律**：本件只出证据与三张表，**不替 HT 拍板**。查不到的一律写 ❓，禁止编造。
> **实测环境**：本机 Windows 11 · Python `3.14.3`（`C:\Users\one\.workbuddy\binaries\python\versions\3.14.3\python.exe`）· pip 26.0
> **实测方法**（全部真跑，脚本留在 `scan/`）：
> ① `_pypi_probe.py` / `_pypi_probe2.py` —— 直连 `https://pypi.org/pypi/<pkg>/json` 取 `info.license` / `info.license_expression` / `info.requires_dist`（剔 extra）/ 最新上传时间 / 目标平台 wheel 体积
> ② `pip install --dry-run --ignore-installed --report` —— 拿**真实解析后的依赖闭包**（`_rep_*.json` → `_summ_report.py` 汇总），比人工数依赖硬
> ③ `_npm_probe.py` —— 直连 `registry.npmjs.org` 取 npm 包 license / 依赖数 / publish 时间
> ④ 源文件实测：`scripts/six_layer_check.py` 的 `run_self_test()` 逐条用例计数、`grep assert`

---

## 0. 先给三条"硬事实"（本报告其余结论都建立在此）

**事实 1 · 本项目的"zéro 依赖"参照盘**：`pip` 实测，本机 Windows + py3.14 下——

| 候选 | 包数 | 是否全纯 Python | 是否含编译二进制 | 纯净体积（wheel 和） |
|---|---|---|---|---|
| `pytest` | **6** | ✅ 是 | ❌ 无 | ≈ **1.74 MB** |
| `jsonschema` | **5** | ❌ 否 | ✅ **rpds-py（Rust）218 KB** | ≈ 0.41 MB |
| `pydantic` | **5** | ❌ 否 | ✅ **pydantic-core（Rust）1 994.7 KB** | ≈ **2.47 MB** |
| `fastjsonschema` | **1** | ✅ 是 | ❌ 无 | 0.03 MB |
| `json-repair` | **1** | ✅ 是 | ❌ 无 | 0.05 MB |

**事实 2 · 现有自测网规模实测**：`six_layer_check.py::run_self_test()` 内 `add(...)` 调用 = **25 条**（任务书说 25，讨论文档 D-16 写 24 —— **任务书为准，讨论文档口径需订正**）。形态是 `add(name, ok, detail, skip)` 扁平表 + `tempfile.mkdtemp()` 沙箱 + `PYTHONIOENCODING=gbk` 子进程复现。

**事实 3 · 现有脚本**没有裸 `assert`（`grep -E '^\s*assert\s'` 仅命中函数名 `check_product_assert`）—— 即"`python -O` 把 Gate 静默关掉"这条经典坑，**当前不存在**，但新 Gate 必须先钉死（见 R4）。

---

# 一、D-16 自测网：pytest vs stdlib unittest

### [C-01] pytest
- **是什么**：Python 事实标准测试框架（断言重写 + fixture + 插件生态 + 参数化）。
- **为什么可用**：① 有 `ExitCode` 枚举做"假绿闸"——**0=全过 / 1=有用例失败 / 5=NO_TESTS_COLLECTED（一个都没收集到）/ 6=MAX_WARNINGS_ERROR（pytest 9.1+ 新增）**，官方文档明说 code 5 属于"路径打错 / `-k` 匹配空"时**非零退出但"什么都没失败"**的陷阱。D-16 要的硬 Gate 恰好需要"零用例 ≠ 通过"这条语义，pytest 白送。② `--collect-only` 可做"用例数只增不减"的回归闸（fixture 数从 25 掉到 24 即红）。
- **接入成本**：**6 个依赖**（实测解析闭包：`pytest` + `Pygments` 1 220.8 KB + `colorama` 24.7 KB + `iniconfig` 7.3 KB + `packaging` 126.9 KB + `pluggy` 20.1 KB）；**全部纯 Python，无任何编译二进制**；总体积 ≈ 1.74 MB；`requires_python >=3.10`。⚠️ 注意 pytest 本体 377.5 KB 里 **`Pygments`（1.2 MB）占了大头**，且它只用于 traceback 着色。
- **License**：`info.license` 为空，`info.license_expression = 'MIT'`（实测 PyPI JSON）；`pytest-cov` 另带 `License :: OSI Approved :: MIT License` classifier 佐证。→ **MIT**。
- **维护活跃度**：最新上传 **2026-06-19**（v9.1.1，PyPI JSON `urls` 最新时间戳）。
- **风险**：① 违反 D-11「零依赖优先」硬约束——**装第三方依赖须过尽调**，本条就是尽调材料；② pytest 9 是大版本，插件生态（mutmut/pytest-randomly 等）与之存在版本咬合；③ 用 `PYTHONIOENCODING=gbk` 跑 pytest 输出会有额外不确定性（现有自测专门防 GBK 崩溃，两套机制叠加）；④ **不要用它替代现有 `self-test` 命令**，否则引擎多一个"必须装东西才能跑"的分支——与 D-09「脚本不可用时降级」打架。
- **是否适合本项目**：**需实测**（结论取决于 HT 对"零依赖"的硬度定义：若允许"dev-only 可选依赖"，它是纯 Python 低风险；若是硬约束，则 C-02 胜）
- **URL**：https://pypi.org/pypi/pytest/json · https://docs.pytest.org/en/stable/reference/exit-codes.html —— 来源分级：**官方文档 + 官方仓库（PyPI JSON 为官方分发元数据）**

### [C-02] stdlib `unittest` + `subTest`（零依赖方案）
- **是什么**：Python 标准库自带的测试框架；`TestCase.subTest(**params)` 是官方给出的**参数化 / 表驱动**机制。
- **为什么可用**：**与现有 fixture 形态是 1:1 平移，不需要改造**——
  - 现有 `add(name, ok, detail, skip)` → 一条 `with self.subTest(name=...)`；
  - 官方文档明确：**subTest 内失败后执行继续跑完剩余子用例**（不用 subTest 则"第一次失败就停"，且难以定位）→ 正是自测网要的"一次跑完、逐条报红"；
  - `python -m unittest discover`（= `python -m unittest`）自带用例发现；
  - `assertRaises` 可作上下文管理器（`with self.assertRaises(X) as cm:` 取 `cm.exception`）→ 对应现有"checkpoint 缺失产物 rc=1""cost_log 非法档位 rc=1"这些反向用例；
  - `assertListEqual` / `assertDictEqual` 等类型特定方法自带 diff 输出 → 对应现有 `rcs == [0, 0, 0, 1]` 这类断言。
- **接入成本**：**0 依赖**（stdlib）· 0 安装体积 · 纯 Python · 无二进制。
- **License**：PSF-2.0（Python 自身许可，随解释器分发）。
- **维护活跃度**：随 CPython 主线演进（`subTest` 3.4+、`assertRaises` 上下文管理器 3.1+、`unittest discover` 3.2+，官方 3.13 文档在册）。
- **风险**：① 没有 pytest 的 `ExitCode` 语义——**"零用例"时 `unittest` 返回 0（成功）**，这是一个必须自己补的假绿口子（对策：先 `--collect`/自数 `test_*` 方法数，或直接在 runner 里断言"用例数 ≥ N"）；② 没有断言重写，失败信息要自己写 `msg=`；③ 与现有"扁平表 + 沙箱"风格相比，要额外建 `tests/` 目录结构（或塞进同一个 `self-test` 命令里，两者并不冲突）。
- **是否适合本项目**：**适合**（对"零依赖 + 现有 25 条 fixture 平移"两个需求，它是最短路径）
- **URL**：https://docs.python.org/3/library/unittest.html（本机抓取成功版本为 3.13 文档）—— 来源分级：**官方文档**

### [C-03] coverage.py（分支覆盖率）
- **是什么**：Python 覆盖率度量（行 / 分支），可 `--fail-under` 做 CI 闸。
- **为什么可用**：对"假绿"有一层朴素价值——**行长被跑到 ≠ 断言真的验了**，但"某个 except 分支从没被跑到"是能抓的；配合分支覆盖可暴露"测试只走了 happy path"。
- **接入成本**：**0 个运行期依赖**（实测 `requires_dist` 为空）——但**不是纯 Python**：本机命中的 wheel 是 `coverage-7.16.2-cp310-cp310-win_amd64.whl`（221.1 KB，含 C 扩展；另有纯 Python 回退路径但默认装二进制）。
- **License**：Apache-2.0（实测 `info.license = 'Apache-2.0'`）。
- **维护活跃度**：最新上传 **2026-09-27**（v7.16.2，3 天前）。
- **风险**：① 覆盖率作为"测试有效性"代理是**弱的**（100% 行覆盖 + 零断言 = 全绿）；② 二进制 wheel 与"纯 Python 可移植"目标轻微冲突；③ 需要它去 instrument 被测脚本，会引入"被测对象被改写"的复杂度。
- **是否适合本项目**：**不适合**（它的代理指标太弱，抓不到本项目最痛的"报通过但其实没验到"；真正对症的是 C-24 变异测试）
- **URL**：https://pypi.org/pypi/coverage/json · https://coverage.readthedocs.io —— 来源分级：**官方仓库（PyPI JSON）**

### [C-04] pytest-randomly（用例乱序）
- **是什么**：每次运行随机打乱用例顺序 / 随机 seed 的 pytest 插件。
- **为什么可用**：它专治一类**假绿**——"用例之间互相污染 / 只在前一个用例先跑时才通过"（本项目的 fixture 全在 `tempfile` 沙箱，但子进程环境变量、`__pycache__`、"陈旧产物"时间基线这类隐式状态正是隐患）。
- **接入成本**：**1 个依赖**（就是 `pytest` 本身）· 8.7 KB · 纯 Python · 无二进制。
- **License**：`info.license_expression = 'MIT'`（实测；`info.license` 空）。
- **维护活跃度**：最新上传 **2026-09-01**（v5.0.0）。
- **风险**：**它把 C-01 的 6 包依赖变成既成事实**——选了它就等于选了 pytest。且乱序会引入"偶发红"，对单人自用项目可能变成噪声。
- **是否适合本项目**：**需实测**（价值真实但**强依赖是否采纳 pytest**；若走 C-02，等价做法是手写"按 25 条 fixture 随机洗牌跑两遍"约 10 行）
- **URL**：https://pypi.org/pypi/pytest-randomly/json —— 来源分级：**官方仓库（PyPI JSON）**

---

# 二、schema 校验：jsonschema vs pydantic vs 纯 Python 替代

### [C-05] jsonschema ⚠️
- **是什么**：JSON Schema 规范的 Python 实现（唯一被广泛使用的参照实现）。
- **为什么可用**：如果真要"用标准 schema 描述 `progress.json` / `cost_log` 格式"，它是规范级的正解；`jsonschema.validate()` 对非法输入**抛 `ValidationError`**，符合 D-12① "不静默回退"的方向。
- **接入成本**：⚠️ **不是"纯 Python 零 C 依赖"**（见 R1）——实测解析闭包 **5 个包**：`jsonschema` + `attrs` + `jsonschema-specifications` + `referencing` + **`rpds-py`**；其中 `rpds-py-2026.6.3-cp311-cp311-win_amd64.whl` **218 KB 是 Rust 编译产物**。总体积 ≈ 0.41 MB（jsonschema 88.5 + jsonschema-specifications 18.0 + referencing 26.1 + attrs 66.0 + rpds-py 218.0 KB）。
- **License**：`info.license_expression = 'MIT'`（实测，PyPI JSON）；子包族同为 MIT。
- **维护活跃度**：最新上传 **2026-01-07**（v4.26.0）。
- **风险**：① **Rust 二进制**（虽然 MIT、体积小，但"零依赖可移植"这句话已经不成立）；② 传递依赖链 5 层，任何一层发新版都可能触发 `pip` 解析变更；③ 它解决的是"通用 JSON Schema"问题，而本项目的 JSON 是**自家定义的 3–5 个文件**，属于"用大炮打蚊子"。
- **是否适合本项目**：**不适合**（题面假设"零 C 依赖"被实测推翻；且需求规模不匹配）
- **URL**：https://pypi.org/pypi/jsonschema/json · https://python-jsonschema.readthedocs.io —— 来源分级：**官方仓库（PyPI JSON）+ 官方文档**

### [C-06] pydantic ⚠️⚠️
- **是什么**：类型驱动数据校验 + 序列化（v2 核心用 Rust 重写）。
- **为什么可用**：生态最好、报错最友好；`json-repair` 甚至支持直接把 pydantic 模型当 schema 用（见 C-08）。
- **接入成本**：⚠️ **5 个包**，其中 **`pydantic-core` 是 Rust 二进制**：`pydantic 2.13.5` 的 `requires_dist` 精确锁 **`pydantic-core==2.46.5`**，该版本本机平台轮子实测 `pydantic_core-2.46.5-cp310-cp310-win_amd64.whl` = **1 994.7 KB**（对照：最新 2.49.0 为 2 085.8 KB，二者不是同一版本，引用时勿混用）。总体积 ≈ **2.47 MB**（pydantic 461.5 + pydantic-core 1 994.7 + annotated-types 13.1 + typing-extensions 44.5 + typing-inspection 14.4 KB）—— **是 pytest 6 包总和（≈1.74 MB）的 1.4 倍，且带二进制**。
- **License**：`info.license_expression = 'MIT'`（实测，pydantic 与 pydantic-core 同为 MIT）。
- **维护活跃度**：pydantic 最新上传 **2026-08-28**（v2.13.5）；pydantic-core **2026-09-09**（v2.49.0）——都很活跃。
- **风险**：① **Rust 二进制 + 精确版本锁**，同时踩"零依赖可移植"与"依赖长寿"两条；② 每个目标平台都要有对应 `pydantic-core` 轮子，否则本地编译（需 Rust 工具链）——这是"给他人用"（D-20）时的真实摩擦；③ 类型驱动校验要求把"业务规则"写成 Python 类型注解 → 与 D-18「`SKILL.md` 保留为规则真相源、不把规则语义下沉进代码」有张力。
- **是否适合本项目**：**不适合**（体积 + 二进制 + 版本锁三重冲突）
- **URL**：https://pypi.org/pypi/pydantic/json · https://pypi.org/pypi/pydantic-core/json —— 来源分级：**官方仓库（PyPI JSON）**

### [C-07] fastjsonschema ✅（纯 Python 替代）
- **是什么**：把 JSON Schema **编译成 Python 校验函数**的库（运行时校验，无第三方依赖）。
- **为什么可用**：① 实测**只有它自己 1 个包、纯 Python wheel、零运行期依赖**；② 校验失败**抛异常**（不静默）；③ License 是 BSD-3-Clause（比 MIT 更明确带分类器）；④ 体积 26.8 KB。
- **接入成本**：**1 个包 · 26.8 KB · 纯 Python · 无二进制 · 0 依赖**（实测 `pip --dry-run` 解析出 1 个包；`requires_dist` 为空）。
- **License**：`info.license = 'BSD-3-Clause'` + `License :: OSI Approved :: BSD License`（实测 PyPI JSON）。
- **维护活跃度**：最新上传 **2026-08-15**（v2.22.2）。
- **风险**：① 规范覆盖度不如 `jsonschema` 官方实现（冷门关键字可能缺失）——**需按本项目实际用到的关键字实测**；② 它靠 `exec` 生成代码，在极端受限的沙箱里可能被拦（本机未实测）；③ 仍然是"引了一个依赖"，只是**唯一一个可能是干净的**。
- **是否适合本项目**：**需实测**（若 HT 判定"必须上标准 JSON Schema 库"，它是唯一不破坏零 C 依赖前提的选择；但见 C-09 的更强反问——本项目也许根本不该引 schema 库）
- **URL**：https://pypi.org/pypi/fastjsonschema/json · https://github.com/horejsek/python-fastjsonschema —— 来源分级：**官方仓库（PyPI JSON）**

### [C-08] json-repair 🚩（**关键反问项**）
- **是什么**：容错 JSON 解析/修复器（LLM 输出常见：单引号、缺冒号、裸键、尾逗号）。
- **为什么可用**：**对 LLM 结构化输出这个场景它确实好用**——`repair_json(...)` / `loads(...)` / `load(...)` 可直接替换 `json.loads()`，支持 `return_objects` / `skip_json_loads` / `ensure_ascii` / `schema` / `schema_repair_mode` / `stream_stable`。
- **接入成本**：**1 个包 · 50.1 KB · 纯 Python · 无二进制 · 0 依赖**（实测解析出 1 个包）。
- **License**：`info.license_expression = 'MIT'`（实测 `info.license` 为空）。
- **维护活跃度**：最新上传 **2026-09-22**（v0.63.5，8 天前）——很活跃。
- **风险**：🚩 **它与 D-12① "解析失败绝不静默回退" 正面冲突**（见 R2 逐字证据）：
  1. README 明示默认流程是「**先试标准库 `json.loads()`，失败则回退到修复解析器**」——**这个回退是透明的**；
  2. README **没有任何 API 告诉你"到底修过没有"**，**全文未提 logging / warning**；
  3. 超级损坏时它「**返回空字符串**」——这正是本项目最痛的"**静默失效**"形态；
  4. 唯一防线是 `strict=True`（遇到重复键 / 缺冒号 / 空键值等结构性歧义才抛 `ValueError`），但那等于"关掉修复"，修复库的价值也就没了；
  5. README 自己警告：把**合法** JSON 强行喂进修复解析器，**它可能"修"它并改变结果结构或取值**（`skip_json_loads=True` 的说明）。
- **是否适合本项目**：**不适合**（作为"解析器"用会制造 D-12① 要防的那种静默回退；若真要它，只能作为"**二次诊断**"且必须先由调用方 `json.loads()` 分叉并显式记录 `repaired=true` —— 那时它已经不是"回退"，而是"受控的修复 + 强制留痕"）
- **URL**：https://pypi.org/pypi/json-repair/json · https://github.com/mangiucugna/json_repair（README 实测抓取）—— 来源分级：**官方仓库 + 官方文档（README）**

### [C-09] voluptuous / Cerberus（"轻 schema"替代）
- **是什么**：**Python 内嵌式** schema 声明与校验库（schema 就是普通 Python 对象/字典，不是 JSON Schema 规范）。
- **为什么可用**：实测两者都**近乎零依赖、纯 Python**：`voluptuous 0.16.0`（`license_expression=BSD-3-Clause`，`requires_dist` 为空，31.2 KB）/ `Cerberus 1.3.8`（ISC，条件依赖只在 py<3.8，29.9 KB）。对"校验自家 3–5 个 JSON 文件的字段/类型/必填"这种**小规模、固定 schema** 的需求，它们比 JSON Schema 全家桶贴合。
- **接入成本**：**1 个包**（各自）· ~30 KB · 纯 Python · 无二进制。
- **License**：voluptuous = **BSD-3-Clause**；Cerberus = **ISC**（实测 `info.license` 为 ISC 全文）。
- **维护活跃度**：voluptuous **2025-12-18**（v0.16.0）；Cerberus **2025-11-06**（v1.3.8）——同为"低频但未停维"。
- **风险**：① 都不是标准，换人/换平台时"可读性"依赖文档；② **对本项目的真实规模（几个自家 JSON）而言，仍然可能是过度设计**——见下方"反常识"：先证明"手写 20 行不够"再引库。
- **是否适合本项目**：**需实测**（先做"手写 vs 引库"的规模判断：如果 schema 只有 `progress.json` / `cost_log.md` 表 / `PROJECT_STATUS.md` 三处且字段固定，手写 `if not isinstance(...): raise` 更符合零依赖与可读性）
- **URL**：https://pypi.org/pypi/voluptuous/json · https://pypi.org/pypi/Cerberus/json —— 来源分级：**官方仓库（PyPI JSON）**

### [C-10] jsonschema-rs / msgspec（**反例：又一个 Rust**）
- **是什么**：`jsonschema-rs` 是 JSON Schema 的 **Rust 实现**的 Python 绑定；`msgspec` 是 Rust 写的序列化/校验库。
- **为什么可用**：快（但本项目对"校验 3 个 JSON 文件"根本没有性能需求）。
- **接入成本**：`jsonschema-rs` 实测 wheel `jsonschema_rs-0.58.2-cp310-abi3-win_amd64.whl` = **5 778.0 KB（5.6 MB）**，`requires_dist` 为空但**纯二进制**；`msgspec 0.22.0` = 186.3 KB 二进制 wheel。
- **License**：`jsonschema-rs` = MIT（`info.license` 实测）；`msgspec` = BSD-3-Clause（`license_expression` 实测）。
- **维护活跃度**：`jsonschema-rs` **2026-09-28**；`msgspec` **2026-09-29**（都极活跃）。
- **风险**：**"零依赖"被误读的典型陷阱**——"`requires_dist` 为空"不等于"零依赖"，因为它把整个 Rust 生态**静态链接进了那个 5.6 MB 的 `.pyd`**。→ 尽调时必须同时看 **`requires_dist` 和 wheel 文件名/体积**（本报告的方法论收获）。
- **是否适合本项目**：**不适合**
- **URL**：https://pypi.org/pypi/jsonschema-rs/json · https://pypi.org/pypi/msgspec/json —— 来源分级：**官方仓库（PyPI JSON）**

---

# 三、D-13 token 预算 enforcement：有没有值得引的"预算/配额 + 熔断"库

### [C-11] pyrate-limiter
- **是什么**：可插拔算法 + 可插拔后端的限流库（`Rate(limit, interval)`）。
- **为什么可用**：**诚实地说：它建模的是"速率"，不是"累计预算"**。README 原文：bucket「代表固定容量，随请求到达而**填充**、随时间**排空（drains）**」；`burst` 控制的是突发容量。也就是**计数会随时间衰减/滑出窗口**。而 D-13 要的是"**读取本地 JSON 里累计的用量 → 与阈值比较 → 超则熔断**"——这是**单调累积、不衰减**的语义。
- **接入成本**：核心 **1 个包 · 55.8 KB · 纯 Python · 0 依赖**（Redis/Postgres/filelock 都是 optional extras）。
- **License**：`info.license_expression = 'MIT'`（实测）。
- **维护活跃度**：最新上传 **2026-08-30**（v4.5.0）。
- **风险**：**语义错位**——用它的 "Rate(1000, MONTH)" 表达月度预算时，滑动/漏桶窗口会让历史用量**提前过期**，等于"预算越用越多"；要精确表达"预算起点至今的累计和"得自己写存储，那就回到手写。此外它要引入 `Clock`/`Bucket`/`BucketFactory`/`Limiter` 四层概念，对一个 20 行的需求是纯负担。
- **是否适合本项目**：**不适合**（建模对象不对）
- **URL**：https://pypi.org/pypi/pyrate-limiter/json · https://github.com/vutran1710/PyrateLimiter（README 实测抓取）—— 来源分级：**官方仓库 + 官方文档**

### [C-12] limits
- **是什么**：`flask-limiter` 背后的限流库，多存储后端（memory/redis/memcached/mongodb）。
- **为什么可用**：同 C-11——**同样是时间窗速率**，且设计目标是"分布式多后端"。
- **接入成本**：**4 个包**（`limits` 59.5 KB + `deprecated` + `packaging` + `typing-extensions`）· 纯 Python。
- **License**：MIT（`license_expression` + MIT classifier，实测）。
- **维护活跃度**：最新上传 **2026-02-05**（v5.8.0）。
- **风险**：**依赖链比手写实现还长**（4 包 vs 0 包），并附带 `deprecated` 这种元依赖；且存储后端概念（storage URI）对"读一个本地 JSON"是纯多余。
- **是否适合本项目**：**不适合**
- **URL**：https://pypi.org/pypi/limits/json —— 来源分级：**官方仓库（PyPI JSON）**

### [C-13] circuitbreaker
- **是什么**：函数级熔断装饰器（失败计数达阈值 → 打开断路器 → 冷却后半开）。
- **为什么可用**：**语义接近但触发源不同**——它按"**调用失败**"计数熔断；D-13 要按"**累计 token 花销**"熔断。token 超预算是"**成功的调用**累计太多"，不是"失败太多"。
- **接入成本**：**1 个包 · 7.6 KB · 纯 Python · 0 依赖**（实测）——是这一族里最干净的。
- **License**：`info.license = 'BSD-3-Clause'` + BSD classifier（实测）。
- **维护活跃度**：最新上传 **2025-03-31**（v2.1.3，约 1.5 年前）。
- **风险**：① 触发语义错位（failures ≠ spend）；② 门槛条件写成装饰器，会**把"预算检查"埋在调用点之外**，D-12 要的是"调用前显式查、显式拦"，装饰器遮蔽了这一点；③ 维护节奏已经放缓。
- **是否适合本项目**：**不适合**（可借鉴"半开状态"的状态机思想，但不必引库）
- **URL**：https://pypi.org/pypi/circuitbreaker/json —— 来源分级：**官方仓库（PyPI JSON）**

### [C-14] tenacity
- **是什么**：通用重试/退避库。
- **为什么可用**：**与本议题正交**（它是"重试"，不是"预算"），但引擎的 LLM 调用层迟早要重试/退避，且它实测 **0 运行期依赖、纯 Python、28.2 KB**，Apache-2.0。
- **接入成本**：**1 个包 · 28.2 KB · 纯 Python · 0 依赖**（实测 `requires_dist` 为空）。
- **License**：`info.license = 'Apache 2.0'` + `License :: OSI Approved :: Apache Software License`（实测）。
- **维护活跃度**：最新上传 **2026-02-07**（v9.1.4）。
- **风险**：不在 D-13 射程内；归 A 线（LLM 调用层）评估更合适。
- **是否适合本项目**：**需实测**（转交扫描员 A 判断）
- **URL**：https://pypi.org/pypi/tenacity/json —— 来源分级：**官方仓库（PyPI JSON）**

### [C-15] litellm（**反例：成熟"预算"库真实成本**）
- **是什么**：多 provider 统一 LLM 网关，**内含 budget / max_budget / 用量追踪**——即"现成的预算库"确实存在。
- **为什么可用**：如果本项目想要"现成的预算 + 熔断 + 多 provider + 成本表"，它就是答案。
- **接入成本**：⚠️ **17 个包闭包**（`litellm` + `aiohttp` + `boto3` + `click` + `fastuuid` + `httpx[http2]` + `importlib-metadata` + `jinja2` + `jsonschema`(<5,>=4) + `openai` + `pydantic` + `pydantic-settings` + `python-dotenv` + `tiktoken` + `tokenizers` …）；**wheel 本体 27 478.2 KB ≈ 27.5 MB**；`requires_python <3.15,>=3.10`。**它把 pydantic-core(Rust)、tiktoken(regex C 扩展)、tokenizers(Rust)、boto3 全部拉进来**。
- **License**：`info.license_expression = 'MIT'`（实测）。
- **维护活跃度**：最新上传 **2026-09-29**（v1.103.1，1 天前）。
- **风险**：**这是"引库 vs 手写"的量化答案**——为了一个"读本地 JSON 比较阈值"的功能，付 27.5 MB + 17 包 + 3 个二进制依赖。且它的预算模型是"服务端/DB 记账"，与"本地 JSON 累计列"（现有 `cost_log.py`）不是一套账。
- **是否适合本项目**：**不适合**（作为 D-13 的替代方案；作为"多 provider 网关"可另议）
- **URL**：https://pypi.org/pypi/litellm/json —— 来源分级：**官方仓库（PyPI JSON）**

### 小结（D-13 的直接回答）
> 题面问"手写 20 行是否完胜引库"——**证据支持"是"**：
> `cost_log.py` 已经在记账（**读**本地累计量），D-13 只多三步：`读 JSON → 与预算比较 → 超则 raise/退出码非 0`。stdlib `json.load` + 一个 `if` 即可，**0 依赖、可被测**。
> 三个候选库（C-11/C-12/C-13）分别在**语义（速率≠预算）、依赖链（4>0）、触发源（失败≠花销）**上错位；唯一"语义正确"的 C-15 要 27.5 MB。
> ⚠️ 但**手写必须自带一条自测用例**（D-16 硬 Gate）——否则它就是第 8 个"可能出"假绿"的脚本"。

---

# 四、状态板 / 事件流（D-02）

### [C-16] Keep a Changelog（规范，非工具）
- **是什么**：变更日志的**人写规范**（当前版本 **1.1.0**）。
- **为什么可用**：**它的三条原则直接可搬到 `PROJECT_STATUS.md` 的事件流分区**：
  - 六大变更类型固定：`Added` / `Changed` / `Deprecated` / `Removed` / `Fixed` / `Security` → 可作**事件流条目的类型前缀**（把自由文本变成可 grep 的结构）；
  - 「**Changelogs are for humans, not machines**」+「**There should be an entry for every single version**」+「**The latest version comes first**」+「**The release date of each version is displayed**」；
  - 「Keep an **`Unreleased`** section at the top」→ 与状态板"当前状态 30 秒版"是同一个设计（顶部是"现在"）。
  - 反面对照：「Don't let your friends dump git logs into changelogs」→ 正是 D-02 里"用户动作只活在对话里"要避免的。
- **接入成本**：**0 依赖 0 安装**（就是一份 Markdown 规范文本）。
- **License**：规范文本（仓库 `olivierlacan/keep-a-changelog`，MIT，未逐字实测 ❓）。
- **维护活跃度**：规范版本 **1.1.0 定稿于 2019-02-15**（站内 CHANGELOG 实测在册，最新站务版本 1.1.2 / 2024-09-27）。规范本身稳定即优点。
- **风险**：① **它管"版本发布变更"（version-scoped），不管"跨窗口协作事件"**——直接照抄会语义漂移（本项目事件流要记的是"用户发了一条指令""换窗了""某产物坏了"）；② 它是**规范不是校验器**，没有官方 validator（❓未查到官方校验器）→ 想"硬约束"仍要自己写闸。
- **是否适合本项目**：**需实测**（借用"固定类型 + Unreleased + 最新在上"三条**形式**，语义要按 D-02 重定义）
- **URL**：https://keepachangelog.com/en/1.1.0/ —— 来源分级：**官方文档（规范站）**

### [C-17] ADR（架构决策记录）· npryce/adr-tools · @meza/adr-tools
- **是什么**：ADR = "一条决策一个文件 + 编号 + 状态 + 取代关系"的轻量实践；`adr-tools` 是配套 CLI。
- **为什么可用**：**它精确对应 D-02 的第二分区（CMD-NN 待开发执行指令区）与 D-07（`Dxx` 决策编号制）**——两大支柱正是：**编号只增**（`adr new` 自动取下一号）、**取代而非改写**（`adr new -s 9` 把旧条目标为 superseded 并双向链）；`adr generate toc` 生成索引（对应"事件流只追加 + 索引"）。
- **接入成本**：
  - **npryce/adr-tools**：**Bash 脚本**（本机 Bash 残废 → 直接不可用）；
  - **npm `@meza/adr-tools`**（TypeScript 重写）：**8 个依赖 + 需要 Node**；
  - **npm `adr-tools`**（第三方，14 依赖，**2020-03-04 最后发版**）。
- **License**：npryce/adr-tools = **GPL**（仓库根有 `GPL.txt` + `LICENSE.txt`，实测）；`@meza/adr-tools` = **GPL-3.0**（npm 实测）；npm `adr-tools` = MIT（npm 实测）。
- **维护活跃度**：
  - npryce/adr-tools：**最后一次提交 2020-03-30**（GitHub 实测，**6.5 年未动**）；
  - `@meza/adr-tools`：**2026-07-17 发版 v2.0.4**（活跃）；
  - npm `adr-tools`：**2020-03-04**（停维）。
- **风险**：① GPL-3.0 对一个"将来可能给他人用"（D-20）的项目是需要法务判断的许可（作 CLI 用一般不传染，但分销/嵌入要谨慎）；② 需要 Node（本机有 Node 22.22.2，但引擎定位是"python + stdlib 就够"）；③ **ADR 的语义是"架构决策"，不是"待开发指令"**——`CMD-NN` 有"就地标状态、不改原文"的额外约束，ADR 只给"superseded"。
- **是否适合本项目**：**需改造后自用**（借**格式与两条纪律**：编号只增 + 取代不改写；不引工具）
- **URL**：https://github.com/npryce/adr-tools · https://adr.github.io/ · http://registry.npmjs.org/@meza%2Fadr-tools —— 来源分级：**官方仓库（GitHub / npm registry 实测）+ 社区对比文（stars 数仅第三方口径，未实测 ❓）**

### [C-18] Log4Brains
- **是什么**：把 ADR 目录**发布成可浏览静态站点**（含时间线、状态徽章、取代关系图、全文搜索）的工具。
- **为什么可用**：如果状态板将来要给人（而非 AI）看，它是"浏览层"。
- **接入成本**：npm 包 **7 个依赖 + Node**；会**新增一个要托管/构建的站点**。
- **License**：**Apache-2.0**（npm registry 实测）。
- **维护活跃度**：最新发版 **2024-12-17**（v1.1.0，约 1.75 年前）。
- **风险**：**它构建的是"另一个真相源"**——D-02 的立论正是"信息散在多处 → 用户被迫当消息总线"，再引入一个只读站点会加剧分散；且本项目硬约束 1 是零依赖。
- **是否适合本项目**：**不适合**
- **URL**：http://registry.npmjs.org/log4brains · https://github.com/thomvaill/log4brains —— 来源分级：**官方仓库（npm registry 实测）**

### [C-19] eventsourcing（append-only 事件流）
- **是什么**：Python 事件溯源框架（event sourcing：只追加的事件日志 + 由事件重放得到状态）。
- **为什么可用**：**它的核心纪律与 D-02 第三分区完全同构**——「事件只追加、不修改、不删除；状态是事件的投影」。实测依赖极干净：**1 个运行期依赖（`typing_extensions`）· 纯 Python wheel 118.3 KB · `requires_python >=3.11`**。
- **接入成本**：**1 个包 · 118.3 KB · 纯 Python · 无二进制**（实测）。
- **License**：❓ `info.license` 与 `license_expression` 均为空/None（实测）—— **PyPI 元数据未声明 license**，需去仓库核对（**未证实**）。
- **维护活跃度**：最新上传 **2026-08-19**（v9.5.5）。
- **风险**：① **它是完整框架（application / repository / mapper / snapshot / 多后端持久化），对"一个只追加的 Markdown 分区"是严重超配**；② License 未在 PyPI 声明 → 尽调不能通过；③ 它要求把状态写成事件 + 投影，与"人可读的 `PROJECT_STATUS.md`"（D-18 可读性）方向相反。
- **是否适合本项目**：**不适合**（借"只追加 + 状态是投影"这一条**思想**即可，不必引框架）
- **URL**：https://pypi.org/pypi/eventsourcing/json —— 来源分级：**官方仓库（PyPI JSON）**

### [C-20] markdownlint-cli2 / mdformat（把 md 模板变成可校验的闸）
- **是什么**：Markdown linter（`markdownlint-cli2`）与 Markdown 格式化器（`mdformat`）。
- **为什么可用**：D-02 的"三分区模板"若只有模板没有**校验**，就会退化成"建议"（判据 1：能不能被硬约束？）。它们能把"模板结构"变成可检查项——不过**真正的结构约束（三个必需标题、`CMD-NN` 编号只增、事件流只追加）仍要自写**，linter 只能管格式（标题层级、列表符号、空行）。
- **接入成本**：`markdownlint-cli2` = npm，**9 个依赖 + Node**（0.23.3）；`mdformat`(PyPI) = **2 个依赖 · 纯 Python**（v1.0.0，`license_expression=MIT`，但**会改写文件**，与"事件流只追加不改原文"冲突）。
- **License**：`markdownlint-cli2` = **MIT**（npm 实测）；`mdformat` = **MIT**（实测）。
- **维护活跃度**：`markdownlint-cli2` **2026-09-20**（v0.23.3，10 天前，非常活跃）；`mdformat` **2025-10-16**（v1.0.0）。
- **风险**：① 都要引依赖/Node；② `mdformat` 的"格式化"= **改写文件**，直接违反 D-02「指令区只追加 + 就地标状态不改原文」；③ 它们**校验不了本项目真正关心的语义**。
- **是否适合本项目**：**不适合**（语义闸得自写；linter 的收益不抵依赖成本）
- **URL**：http://registry.npmjs.org/markdownlint-cli2 · https://pypi.org/pypi/mdformat/json —— 来源分级：**官方仓库（npm registry / PyPI JSON 实测）**

### 关于"三分区 md 模板有没有成熟范式"
> **实测结论：❗ 没有查到**直接对应"**当前状态 30 秒版 / CMD-NN 待办区 / 事件流只追加**"三分区的成熟规范或工具。
> 最接近的两个范式是 **Keep a Changelog**（顶部 Unreleased + 固定类型 + 最新在上）与 **ADR**（编号只增 + 取代不改写）。**D-02 的三分区是这两者的缝合 + 本项目特有语义**（"用户动作必须落盘"，这是 Changelog/ADR 都不管的）。
> → 归入**未证实项**，建议 D-02 的模板按"自研 + 引用上述两条纪律"处理，不要去找现成件。

---

# 五、rule 83 上下文压缩

### [C-21] LLMLingua / LLMLingua-2（微软）
- **是什么**：提示词压缩（**抽取式 token 剪枝**：逐 token 二分类 → 只保留重要 token）。
- **为什么可用**：⚠️ **品类不对**（见 R6）。它的输出**保证是原文的子序列（extractive、不重排、不幻觉）**——而 rule 83 的 LC3 要的是**"框架版六字段摘要"**（`phase`/`modules`/`ruled_out`/`top_suspect`/`open_items`/`next`），那是**抽象重写**，不是"抽掉一些词"。
- **接入成本**：`llmlingua` PyPI 包本体只有 29.8 KB，但 `requires_dist` = **`transformers` + `accelerate` + `torch` + `tiktoken` + `nltk` + `numpy`（6 个重型依赖）**；且**需要下载模型权重**（LLMLingua-2 base = XLM-RoBERTa-large 355M 参数；small = mBERT 110M）。社区实测显存：LLMLingua（LLaMA-2-7B 底座）**12.5 GB 起、长输入 16.5 GB**；LLMLingua-2 base ≈ **2 GB 起**、small ≈ 0.66 GB。
- **License**：`info.license = 'MIT License'`（实测，PyPI JSON）。
- **维护活跃度**：最新上传 **2024-04-09**（v0.2.2）——**约 2.5 年未发版**。
- **风险**：① torch 依赖（GB 级安装体积）与本机"零依赖 + 受限环境"直接冲突；② 需模型权重（联网下载 / 落盘体积）；③ 停维 2.5 年；④ **抽取式 ≠ 结构化摘要**；⑤ 有第三方评测指出原版 LLMLingua **达不到目标压缩率**、长 prompt（>8,000 token）误差 >0.15，只有 LLMLingua-2 稳定。
- **是否适合本项目**：**不适合**
- **URL**：https://pypi.org/pypi/llmlingua/json · https://github.com/microsoft/LLMLingua · https://deepwiki.com/microsoft/LLMLingua/3.3-llmlingua-2 —— 来源分级：**官方仓库（PyPI JSON）+ 第三方分析（模型/显存数据为社区来源）**

### [C-22] sumy
- **是什么**：传统**抽取式文本摘要**库（Luhn/TextRank/LSA/LexRank 等，另有 HTML 正文抽取）。
- **为什么可用**：**纯算法、无需模型权重、可离线**——是"不花 LLM 的摘要"里最像样的一个。
- **接入成本**：**9 个包**（`sumy` 70.5 KB + `breadability` + `docopt-ng` + `lxml-html-clean` + `nltk` + `pycountry` + `requests` + `setuptools`×2）· 纯 Python 但依赖链长且含 `nltk`（首次用某些功能会下载语料）。
- **License**：`info.license = 'Apache License, Version 2.0'` + Apache classifier（实测）。
- **维护活跃度**：最新上传 **2026-08-12**（v0.13.0）。
- **风险**：① 抽取式摘要**做不出"六字段"结构**（它只会挑句子，不会分类归位）；② 中文本项目场景下，`nltk` 的句子切分/停用词对中文支持弱；③ 9 个依赖违背零依赖。
- **是否适合本项目**：**不适合**
- **URL**：https://pypi.org/pypi/sumy/json —— 来源分级：**官方仓库（PyPI JSON）**

### [C-23] tiktoken
- **是什么**：OpenAI 的 BPE 分词器（用于**调用前**估 token 数）。
- **为什么可用**：**只应该用作"粗估"，不应作为预算判据**。理由：
  - rule 83 规格 §2 已经把**校准源钉死在 API 的 `usage.prompt_tokens`**（"每次实际用量回写，定期校准校准窗口"）→ **本地分词器不是必需品**；
  - 对 DeepSeek，多家社区来源给出**互相矛盾**的偏差方向与幅度（见"未证实项"），**不能当阈值依据**。
- **接入成本**：实测 `requires_dist = ['regex', 'requests']` → `regex` 本体是本机 **`regex-2026.9.29-cp310-cp310-win_amd64.whl`（274.1 KB，C 扩展）**，`requests` 再带 4 个子依赖（`charset_normalizer`/`idna`/`urllib3`/`certifi`）→ **闭包约 7 个包，且含 C 扩展**。本体 wheel 922.0 KB。另：tiktoken 的 BPE 词表**默认需要联网下载**（离线环境需预置缓存，本机未实测 ❓）。
- **License**：`info.license` = MIT 全文（实测，含 `Copyright (c) 2022 OpenAI, Shantanu Jain`）。
- **维护活跃度**：最新上传 **2026-08-17**（v0.14.0）。
- **风险**：① C 扩展 + 联网取词表 → 破坏"可移植"；② **分词器与 DeepSeek 不一致**（方向存疑，见下）；③ 会把"预算判断"变成一个**有误差的函数**，而 D-13 是熔断器——**熔断器建在估算上 = 新的假绿**。
- **是否适合本项目**：**需实测**（**只建议做"粗估 + 显式标注 ±误差"**；硬熔断必须用 API 回写的 `usage` 做累计）
- **URL**：https://pypi.org/pypi/tiktoken/json —— 来源分级：**官方仓库（PyPI JSON）**

### 小结（rule 83 的直接回答）
> 题面问"家俊的规格是否已经比这些库更贴合"——**证据支持"是"**：
> LLMLingua（抽取式、要 torch + 权重、停维 2.5 年）、sumy（抽取式、9 依赖）都是**把文本变短**；rule 83 要的是**把状态"交接化"**（六字段 + 指针 + 与 `progress.json` 的真相源关系 + 复述测试）。
> **三级级联的前两级（LC1 子 Agent 回报只留结论+指针 / LC2 已完成输入淘汰）本质是"上下文治理策略"，任何库都替代不了**；只有 LC3 是"摘要"，而 LC3 的字段定义是框架特有的。
> → 可借的只有**指标**（token 粗估、压缩比），不是**实现**。

---

# 六、"假绿 / 静默失效"检测

### [C-24] mutmut（变异测试）🚩 **思想最值得移植**
- **是什么**：变异测试——自动**改写源代码**（`>` 变 `>=`、`True` 变 `False` 等），然后跑测试；**如果测试仍然全绿，说明这处变异"没被测到"**。
- **为什么可用**：**这是唯一直接针对"假绿"的开源方法学**：它不问"测试跑没跑过这行"，而是问"**把代码弄坏，测试抓不抓得到**"。直接对应本项目 D-16（自测网有效性）与 B-1/B-2（写入类产物断言）——
  > **可移植的最小做法**：对 `six_layer_check.py` 的某个检查做**故意扰动**（如把"归档时序 zip 晚于 asar"的比较反向、把 `evidence >= 3` 改成 `>= 4`），**重跑 25 条 fixture，断言必须有若干条变红**。红了 = 该能力真的被网住了；仍全绿 = **自测网对该能力是"空洞 PASS"**（正好呼应现有第 10 条用例"空洞 PASS 识别"的同一思想，只是反了个方向）。
- **接入成本**：**8 个包**（`mutmut` + `click` + `coverage` + `libcst` + **`pytest`** + `setproctitle` + `textual` + `toml`）· 依赖里**硬绑 pytest**；本体 79.6 KB。
- **License**：`info.license_expression = 'BSD-3-Clause'`（实测 `info.license` 为空）。
- **维护活跃度**：最新上传 **2026-09-12**（v3.8.0，18 天前）。
- **风险**：① **强依赖 pytest**（选它 = 连 C-01 的 6 包一起背）；② 变异测试**跑得慢**（N 个变异 × 全量用例）；③ 它会**修改源码**（需要干净的 git 状态 + 回滚），对"只增不删"的工作区是风险操作；④ `libcst` 是 C 扩展（本机未实测其 wheel ❓）。
- **是否适合本项目**：**需实测**（**思想必学、工具先别引**：先手写 3–5 条"故意扰动"的元用例，验证 25 条网是否有洞）
- **URL**：https://pypi.org/pypi/mutmut/json —— 来源分级：**官方仓库（PyPI JSON）**

### [C-25] cosmic-ray（变异测试，另一实现）
- **是什么**：另一个 Python 变异测试框架（`init`/`exec`/`run` 三段式 + SQLite 存结果）。
- **为什么可用**：同上思想；好处是**不绑 pytest**。
- **接入成本**：⚠️ **14 个包**（`cosmic-ray` + `aiohttp` + `anybadge` + `attrs` + `click` + `decorator` + `exit-codes` + `gitpython` + `parso` + `rich` + **`sqlalchemy`** + `stevedore` + `toml` + `yattag`）· 本体 60.8 KB。
- **License**：`info.license` 为自定义全文（"Copyright (c) 2015-2017 Sixty North AS Permission is…"，未给出 SPDX 标识）→ **SPDX 未证实 ❓**。
- **维护活跃度**：最新上传 **2026-08-09**（v8.7.0）。
- **风险**：**14 个依赖里含 SQLAlchemy / aiohttp / gitpython**——比 mutmut 更重；License 无 SPDX 标识，尽调要读全文。
- **是否适合本项目**：**不适合**
- **URL**：https://pypi.org/pypi/cosmic-ray/json —— 来源分级：**官方仓库（PyPI JSON）**

### [C-26] hypothesis（属性测试）
- **是什么**：property-based testing——你声明**不变量**，它自动**生成大量边界输入**（含收缩到最小反例）来找违反。
- **为什么可用**：**思路正对本项目的"验证不足"**：现有 25 条 fixture 是**手挑的样例**，而 hypothesis 的哲学是"**别只挑你想得到的输入**"。可移植到 Gate 自检的点：把"产物路径解析""GBK 编码安全""注释剥离正则"这类**易出边界 bug**的纯函数，用 hypothesis 生成任意字符串/路径去压——**注释剥离吃掉文件尾（v3.19.0 修的那个 bug）恰好就是这种"手挑样例覆盖不到"的边界**。
- **接入成本**：**3 个包**（`hypothesis` wheel 668.9 KB + `sortedcontainers` 28.9 KB + 条件依赖 `exceptiongroup`）· 本体命中 `hypothesis-6.168.3-cp310-abi3-win_amd64.whl`（**含 C 扩展，非纯 Python**）。
- **License**：**`MPL-2.0`**（实测 `license_expression`）—— 注意这是**弱著佐权（文件级 copyleft）**，与 MIT/BSD/Apache 不同，D-20"将来给他人用"时需留意。
- **维护活跃度**：最新上传 **2026-09-28**（v6.168.3，2 天前）。
- **风险**：① **MPL-2.0**；② 二进制 wheel；③ 属性测试对"只能靠 I/O 副作用描述"的逻辑（写盘、子进程）**难以表达**——本项目大量 Gate 是副作用的；④ 会引入"随机失败"，对单人项目可能是负担。
- **是否适合本项目**：**需实测**（**只对少数"纯函数 + 易边界 bug"的检查项试水**，如注释剥离正则；不适用于整套 25 条）
- **URL**：https://pypi.org/pypi/hypothesis/json —— 来源分级：**官方仓库（PyPI JSON）**

### [C-27] Great Expectations（数据断言）❌（**本机装不上**）
- **是什么**：数据管道的"期望/断言"框架（Expectations + 数据文档 + 校验结果）。
- **为什么可用**：**思想层面**它最接近"产物级断言"（B-1）——把"我期望这个产物满足什么"写成可执行的 Expectation 而不是"看一眼"。
- **接入成本**：⚠️⚠️ **23 个包闭包**（`altair`/`cryptography`/`jinja2`/`jsonschema`/`marshmallow`/`mistune`/`numpy`/`pandas`/`pydantic`/`pyparsing`/`python-dateutil`/`requests`/`ruamel.yaml`/`scipy`/`tqdm`/`typing-extensions`/`tzlocal`…）· 本体 wheel **5 582.1 KB ≈ 5.5 MB**。
- **License**：`info.license = 'Apache-2.0'` + Apache classifier（实测）。
- **维护活跃度**：最新上传 **2026-09-25**（v1.23.2）。
- **风险**：🚩 **`requires_python = '<3.14,>=3.10'`（实测）**——**本机正是 Python 3.14.3，直接装不上**。外加 pandas/scipy/numpy 全家桶，与"零依赖 + 受限环境"彻底冲突。
- **是否适合本项目**：**不适合**（本机 Python 版本硬性不兼容 + 依赖规模超限）
- **URL**：https://pypi.org/pypi/great_expectations/json —— 来源分级：**官方仓库（PyPI JSON）**

### [C-28] ShellCheck / PSScriptAnalyzer（**"只做语法解析"的假绿解药**）🚩
- **是什么**：Bash/`sh` 的**静态分析**器（ShellCheck）与 PowerShell 的**静态分析**器（PSScriptAnalyzer）。
- **为什么可用**：**直接命中现有自测网的一个"低门槛假绿"**（见 R5）——现在 `self-test` 用例 7 对 `sync_to_platforms.sh` 只跑 `bash -n`、对 `.ps1` 只跑 `[scriptblock]::Create(...)`。官方对比资料明说：**`bash -n` 只解析语法，对引号、误用命令、可移植性"没什么可说的"**——也就是"脚本能解析"≠"脚本行为正确"。ShellCheck 补的正是这一层（未加引号的变量展开、`[`/`[[` 误用、危险命令等，带 SC-XXXX 规则号），且**有退出码可直接当闸**。
- **接入成本**：**ShellCheck = 独立二进制**（Haskell 编译），Windows 上 `choco install shellcheck` / `winget install --id koalaman.shellcheck` / `scoop install shellcheck`，也可用 Docker 镜像锁版本；**不是 pip 包，不进零依赖预算**。PSScriptAnalyzer = PowerShell 模块（`Install-Module PSScriptAnalyzer` / `Install-PSResource`），支持 Windows PowerShell 5.1+。
- **License**：ShellCheck = **GPL-3.0**（官方 README + LICENSE 实测口径）；PSScriptAnalyzer = ❓（未实测，通常为 MIT）。
- **维护活跃度**：ShellCheck **v0.11.0 / 2025-08-04**（仓库未归档；v0.9.0 Dec 2022 → v0.10.0 Mar 2024 → v0.11.0 Aug 2025，节奏不均）。
- **风险**：① ShellCheck 是**外部二进制**——在 D-09"脚本不可用时降级为手写等价记录 + 标注未验证"的语境下，必须走 SKIP 分支；② **GPL-3.0**，嵌入/分销需谨慎；③ 新版本会引入新警告 → 官方建议**固定版本**；④ **本机 Bash 残废**，实际可跑性未实测（现有用例 7 已对 bash 缺失做 SKIP）。
- **是否适合本项目**：**需实测**（**"把语法检查升级为静态分析"这个方向值得采纳**；是否真引二进制取决于本机 bash/powershell 可用性与 GPL 接受度）
- **URL**：https://github.com/koalaman/shellcheck · https://learn.microsoft.com/powershell/utility-modules/psscriptanalyzer/overview —— 来源分级：**官方仓库 + 官方文档（经社区对比文交叉印证；版本/许可细节为社区来源，未直连官方 API 实测 ❓）**

### [C-29] `python -O` / `PYTHONOPTIMIZE` 对 `assert` 的影响（**stdlib 认知项**）🚩
- **是什么**：Python 官方 CLI 选项 `-O`（及环境变量 `PYTHONOPTIMIZE`）。
- **为什么可用**：**官方文档原文**：`-O` ——「**Remove assert statements and any code conditional on the value of `__debug__`**」，并把 `.pyc` 改名为 `.opt-1`。`PYTHONOPTIMIZE` 非空即等价于 `-O`（整数则相当于多个 `-O`）。
  → **任何"用 `assert` 当 Gate"的脚本，都能被一个环境变量静默变成空操作——这是本项目"假绿"定义的最纯粹样本。**
  → **正面事实（实测）**：现有 7 个脚本**没有裸 `assert`**（`grep -E '^\s*assert\s'` 只命中函数名 `check_product_assert`）→ **当前无此风险**；但 D-16 一旦把"新命令必须带自测用例"升为硬 Gate，就必须同时钉死"**Gate 断言只用 `if ...: raise/exit(code)`，禁用 `assert`**"。
- **接入成本**：**0 依赖 0 安装**（认知 + 一条 lint 规则）。
- **License**：PSF-2.0（Python 文档）。
- **维护活跃度**：现行 CPython 文档（本机抓取到 3.13 版）。`-O` 自 Python 1.x 起存在；3.5 起 `.pyc` 命名按 PEP 488 变化。
- **风险**：只在**别人用 `-O`/`PYTHONOPTIMIZE` 跑你的脚本**时触发——**恰好是"将来给他人用"（D-20）的场景**。
- **是否适合本项目**：**适合**（作为新 Gate 规范的**一条禁令**，零成本）
- **URL**：https://docs.python.org/3/using/cmdline.html#cmdoption-O —— 来源分级：**官方文档**

---

# 七、三张表

## ✅ 表 A · 可直接拿来用（零/近零成本，证据充分）

| # | 项目/方案 | 拿来做什么 | 成本 | License | 实测依据 |
|---|---|---|---|---|---|
| A1 | **stdlib `unittest` + `subTest`** | D-16：把现有 **25 条 fixture 表**平移成测试用例；官方明确 **subTest 失败后继续跑完**；`assertRaises` 做反向用例 | **0 依赖** | PSF-2.0 | 官方文档（`subTest` 3.4+ / `discover` 3.2+） |
| A2 | **stdlib `json`（严格模式，失败即 raise）** | D-12①"解析失败绝不静默回退"的**正解** | **0 依赖** | PSF-2.0 | 与 C-08 json-repair 的对照 |
| A3 | **stdlib `hashlib` + `os.stat().st_size` + 回读** | B-1"写入类产物级断言"（Files.copy 产 0 字节 / 路径少斜杠） | **0 依赖** | PSF-2.0 | 本项目 §B-1 现场证据 |
| A4 | **`if ...: raise / sys.exit(n)` 替代 `assert`** | 防 `-O` / `PYTHONOPTIMIZE` 把 Gate 静默关掉 | **0 依赖** | PSF-2.0 | 官方 `-O` 文档原文（C-29） |
| A5 | **pytest `ExitCode` 语义（0/1/5/6）** | D-16 硬 Gate 必须区分「**全过**」与「**零用例**（code 5）」；code 6 = 告警超限（pytest 9.1+） | **0 依赖（只用其语义）** | MIT | 官方 exit-codes 文档 |
| A6 | **Keep a Changelog 1.1.0**（规范文本） | D-02 事件流分区：**固定六类型 + 顶部 Unreleased + 最新在上** | **0 安装** | 规范站（仓库 MIT ❓） | 官方规范站实测抓取 |
| A7 | **ADR 的两条纪律**（编号只增 / 取代不改写） | D-02 的 `CMD-NN` 待办区 + D-07 `Dxx` | **0 安装（只用思想）** | GPL（工具）/ 思想无许可 | npryce 仓库实测（工具本身 6.5 年未动，**不引工具**） |

## ⏳ 表 B · 需改造后自用

| # | 项目/方案 | 改造点 | 成本 | License | 为什么是"改造"而非"直用" |
|---|---|---|---|---|---|
| B1 | **pytest**（6 包，全纯 Python ≈1.74 MB） | 只作 **dev-only 可选**；主 Gate 仍走 stdlib；靠 `--collect-only` 做"用例数只增"闸 | 6 包 / 0 二进制 | MIT | 与 D-11「零依赖优先」冲突 → 需 HT 判定"dev-only 依赖"是否豁免 |
| B2 | **fastjsonschema**（1 包 26.8 KB 纯 Python） | 需按本项目实际用到的关键字验证覆盖度 | 1 包 / 0 二进制 | BSD-3-Clause | 唯一"上 schema 库但不破坏零 C 依赖"的选项；**但见 B3——也许根本不该引** |
| B3 | **"先手写 20 行校验"** | 先证伪"手写不够"，再考虑引 B2 | 0 依赖 | — | 本项目只有 3–5 个自家 JSON；与 D-13"手写完胜引库"是同一判据 |
| B4 | **mutmut 的变异测试思想** | **只取思想**：手写 3–5 条"故意扰动"元用例，验证 25 条 fixture 网有没有洞 | 0 依赖（手写）/ 引 mutmut 则 8 包 | BSD-3-Clause | 工具强绑 pytest + 会改源码 + `libcst` 为 C 扩展 → 工具先别引 |
| B5 | **hypothesis 的属性测试思想** | 只对**少数纯函数 + 易边界 bug**的检查项试水（如 v3.19.0 修过的注释剥离正则） | 3 包 / 含 C 扩展 wheel | **MPL-2.0（弱著佐权，注意）** | Gate 多为 I/O 副作用，属性测试难表达；且会引入随机失败 |
| B6 | **ShellCheck / PSScriptAnalyzer** | 把用例 7 的"语法解析"升级为"语义静态分析"；但必须保留"二进制不可用 → SKIP 记未验证"分支 | 外部二进制（非 pip） | ShellCheck **GPL-3.0**；PSScriptAnalyzer ❓ | 本机 bash 残废、GPL、需固定版本 |
| B7 | **json-repair** | **只能作"受控修复 + 强制留痕"**：调用方先跑 `json.loads()`，失败才用它，且必须把 `repaired=true` 写进 cost_log 异常类型列 | 1 包 50.1 KB 纯 Python | MIT | 其默认"静默回退 + 无 API 报告是否修过"直接违反 D-12①（R2） |
| B8 | **tiktoken** | 只作**粗估**并显式标注 ±误差；**硬熔断一律用 API 回写的 `usage`** | ~7 包 / 含 C 扩展 / 词表需联网 | MIT | 与 DeepSeek 分词器不一致（方向存疑）；熔断建在估算上 = 新假绿 |
| B9 | **eventsourcing** | **只借"事件只追加、状态是投影"一条思想** | 1 包 118.3 KB（框架本体）= 超配 | ❓ PyPI 未声明 | 完整框架对"一个 Markdown 分区"严重超配；License 未声明 → 尽调不过 |
| B10 | **@meza/adr-tools** | 若真要 ADR 工具，只有它活跃（2026-07） | 8 依赖 + Node | **GPL-3.0** | 需 Node；GPL；与"python + stdlib 就够"冲突 |

## ❌ 表 C · 不采纳

| # | 项目 | 不采纳的硬理由（一句话 + 实测） |
|---|---|---|
| C1 | **pydantic** | `pydantic-core` 是 **Rust 二进制（锁定版 2.46.5 实测 1 994.7 KB）**，且 `requires_dist` 里 **`pydantic-core==` 精确锁版本** → 同时踩"零依赖可移植"与"依赖长寿"两条 |
| C2 | **jsonschema** | **题面假设被实测推翻**：4.26.0 依赖 **`rpds-py`（Rust，218 KB）**，实测闭包 5 包 → 不是"纯 Python 零 C 依赖" |
| C3 | **jsonschema-rs / msgspec** | `requires_dist` 为空但 wheel 是 **5 776 / 186 KB 的纯二进制** → "0 依赖"被静态链接伪装 |
| C4 | **LLMLingua / LLMLingua-2** | 需要 **torch + 模型权重**（2 GB 显存起），**2024-04 停更**，且**抽取式 ≠ rule 83 的结构化摘要** |
| C5 | **sumy** | 9 包（含 nltk/requests/setuptools），抽取式摘要做不出六字段 |
| C6 | **Great Expectations** | **`requires_python = '<3.14'` → 本机 Python 3.14.3 装不上**；23 包 / 5.5 MB |
| C7 | **pyrate-limiter / limits / circuitbreaker** | 建模错位：**速率窗口（会衰减）≠ 累计预算**；`limits` 4 包比手写 0 包还重；`circuitbreaker` 按"失败"熔断而非"花销" |
| C8 | **litellm** | 若只为预算：**27.5 MB wheel + 17 包**（含 pydantic-core / tiktoken / tokenizers 三个二进制）→ 手写 20 行完胜 |
| C9 | **cosmic-ray** | **14 包**（含 sqlalchemy / aiohttp / gitpython），SPDX 未标识 |
| C10 | **coverage.py** | 覆盖率作为"测试有效性"代理太弱（100% 行覆盖 + 零断言 = 全绿），且是二进制 wheel |
| C11 | **npryce/adr-tools / npm adr-tools** | **最后一次提交 2020-03-30 / 发版 2020-03-04**（6.5 年停维）；且是 Bash（本机 Bash 残废）/ GPL |
| C12 | **Log4Brains** | 会**新增第二个真相源 + 要托管的站点**，与 D-02 立论（减少信息分散）反向 |
| C13 | **markdownlint-cli2 / mdformat** | 管不了本项目真正关心的语义（三分区结构 / CMD 编号只增 / 只追加）；`mdformat` 还会**改写文件**违反"不改原文" |
| C14 | **pytest-randomly** | 它等于把 pytest 的 6 包依赖变成既成事实（价值真实，**取决于 C-01 是否采纳**） |

---

# 八、反转性发现（≥2 条已满足，共 7 条）

> **R1 · "jsonschema 是纯 Python、零 C 依赖"——实测为假。**
> 题面把 `jsonschema` 当成"纯 Python，零 C 依赖？"的候选。实测 `pip install --dry-run`：**解析出 5 个包**（`attrs` / `jsonschema` / `jsonschema-specifications` / `referencing` / **`rpds-py`**），其中 `rpds-py-2026.6.3-cp311-cp311-win_amd64.whl` 是 **Rust 编译产物（218 KB）**。→ **"零 C 依赖"这个前提不成立**；唯一保留该前提的 schema 库是 `fastjsonschema`（1 包、纯 Python、BSD-3）。
> 证据：`scan/_summ_report.py` 输出 + `https://pypi.org/pypi/rpds-py/json`。

> **R2 · `json-repair` 恰好会把 D-12① 要防的"静默回退"制造出来。**
> 题面的反问方向是对的，实测坐实：README 明示默认流程是「**先试标准库 `json.loads()`，失败则回退到修复解析器**」，且这个回退**对调用者透明**；**没有任何 API 返回"是否被修复过"**；**全文未提 logging / warning**；超级损坏时**返回空字符串**（最典型的静默失效形态）。唯一防线 `strict=True` 会让它抛 `ValueError`——但那就等于关掉修复。
> 更狠的一条：README 自己警告，把**合法** JSON 强行送进修复解析器，**它可能"修"它并改变结果结构或取值**。
> → **结论：作为解析器它违反 D-12①；只能作为"调用方已判定失败后的受控修复"，且必须强制留痕。**
> 证据：`https://raw.githubusercontent.com/mangiucugna/json_repair/master/README.md`（实测抓取）。

> **R3 · `pydantic` 的 Rust 二进制与"零依赖可移植引擎"直接冲突，且带精确版本锁。**
> 实测：`pydantic 2.13.5` 的 `requires_dist` 含 **`pydantic-core==2.46.5`（`==` 精确锁）**；该版本本机平台轮子 `pydantic_core-2.46.5-cp310-cp310-win_amd64.whl` = **1 994.7 KB**（最新 2.49.0 是 2 085.8 KB，**不是一个版本，勿混用**）。整个闭包 **5 包 ≈ 2.47 MB**（是 pytest 6 包总和 ≈1.74 MB 的 1.4 倍）。
> → 对"将来可能给他人用"（D-20）的项目，这意味着：**每个目标平台都必须有对应 `pydantic-core` 轮子，否则要求使用者装 Rust 工具链**。
> 证据：`scan/_pypi_probe.py` 输出 + `_rep_pydantic.json`。

> **R4 · `assert` 不是 Gate，是一个可被环境变量静默关掉的空操作。**
> Python 官方文档原文：`-O`「**Remove assert statements and any code conditional on the value of `__debug__`**」；`PYTHONOPTIMIZE` 非空即等价。
> → **这是"假绿"最纯粹的样本**：脚本报"通过"，是因为**断言根本不存在**。
> **好消息（实测）**：现有 7 个脚本**没有任何裸 `assert`**（`grep` 只命中函数名 `check_product_assert`）→ 当前无此风险；但 D-16 升为硬 Gate 时必须同时禁 `assert`。
> 证据：`https://docs.python.org/3/using/cmdline.html`（实测抓取）+ `grep -E '^\s*assert\s' scripts/`。

> **R5 · 现有自测网用例 7 是"低门槛假绿"的教科书样本：`bash -n` 只验语法。**
> `run_self_test()` 用例 7 对 `sync_to_platforms.sh` 只跑 `bash -n`、对 `.ps1` 只跑 `[scriptblock]::Create(...)`。而官方对比资料明说：**`bash -n` 只解析语法，对引号、误用命令、可移植性"没什么可说的"**——它给的是"能解析"，不是"行为正确"。
> → **25 条网里就有一条是"形式通过"而非"实质通过"**，恰好印证家俊最痛的"假绿"。
> 证据：`six_layer_check.py:1396-1417` + ShellCheck 官方对比材料。

> **R6 · LLMLingua 与 rule 83 是**两个品类**——不是"更好的实现"，是"做不了这件事"。**
> LLMLingua-2 是**逐 token 二分类的抽取式剪枝**，其设计优点被明确写为"**输出必然是源文本的子序列（extractive），保证忠实、防重排、防幻觉**"。
> → 而 rule 83 的 LC3 产物是 **"框架版六字段摘要"**（`phase`/`modules`/`ruled_out`/`top_suspect`/`open_items`/`next`），是**抽象重写 + 字段归位**——**LLMLingua 的"优点"恰恰是它做不到这件事的原因**。
> 而且它要 torch（LLaMA-2-7B 底座版本 12.5–16.5 GB 显存；LLMLingua-2 base ≈2 GB）且 **2.5 年未发版**。
> 证据：`https://pypi.org/pypi/llmlingua/json`（requires_dist = transformers/accelerate/torch/tiktoken/nltk/numpy）+ 第三方评测与架构阅读。

> **R7 · "0 依赖"是个会骗人的字段——必须同时看 `requires_dist` 和 wheel 体积。**
> `jsonschema-rs 0.58.2` 的 `requires_dist` **为空**，但它的 wheel 是 `jsonschema_rs-0.58.2-cp310-abi3-win_amd64.whl` = **5 778.0 KB**——整个 Rust 生态被**静态链接**进了那个 `.pyd`。
> `msgspec 0.22.0` 同理（0 依赖、186.3 KB 纯二进制）。
> → **尽调方法论修正**：判断"零依赖"必须**三条同时看**：`requires_dist` + wheel 文件名（是否 `py3-none-any`）+ wheel 体积。只看 `requires_dist` 会得到**假绿**。
> 证据：`scan/_pypi_probe2.py` 输出。

---

# 九、未证实项清单（❓ 禁止编造）

| # | 未证实项 | 现状 | 建议的证实动作 |
|---|---|---|---|
| ❓1 | **DeepSeek 是否发布官方 tokenizer 包** | **来源互相矛盾**：一处称"DeepSeek 在其 token 用量文档旁分发 tokenizer"，另一处称"DeepSeek publishes no official tokenizer"（同站不同文） | 直连 DeepSeek 官方 API 文档 + `/models` 核对（**归扫描员 A**） |
| ❓2 | **tiktoken/cl100k_base 对 DeepSeek 的实际偏差方向与幅度** | **三个互相矛盾的口径**：① 同站称"DeepSeek 用与 OpenAI 相同的 tokenizer，cl100k_base 可准确预估"；② 同站另一文称"cl100k_base **低估** 10–15%"；③ 一篇中文实测称中文系数应取 **1.16** 而非 1.6，即经验公式**高估约 20.9%**。**方向都不一致 → 不可作为阈值依据** | 拿本项目真实 prompt 样本，比对本地估算 vs API `usage.prompt_tokens`，实测出本项目的校准系数 |
| ❓3 | **`pytest 9.1.1` 在 Python 3.14.3 上能否真跑** | `pip --dry-run` **解析通过**（`requires_python >=3.10`），但**未真实安装/运行**（未获授权改环境） | 在隔离 venv 里实测一次（装 + 跑一个用例 + 看 code 5/6） |
| ❓4 | **`sync_to_platforms.sh/.ps1` 在本机能否真跑** | 现有 self-test 自带 SKIP 分支（bash 不可用 / 无 powershell），本报告未实测 Windows 上的实际可用性 | 实跑 `bash --version` / `powershell -Command $PSVersionTable` |
| ❓5 | **"三分区 md 状态板"是否存在成熟规范/工具** | **未查到**。最接近的是 Keep a Changelog（顶部 Unreleased + 固定类型）与 ADR（编号只增 + 取代不改写） | 若 HT 需要，再扩检索（当前判定：D-02 属自研缝合，不必外找） |
| ❓6 | **`eventsourcing` 的 License** | PyPI JSON 的 `info.license` 与 `license_expression` **均为空/None** | 去 GitHub 仓库根 `LICENSE` 核对 |
| ❓7 | **`cosmic-ray` 的 SPDX 标识** | `info.license` 是自定义全文（"Copyright (c) 2015-2017 Sixty North AS…"），**无 SPDX 标识** | 读仓库 LICENSE 全文 + 确认是否与某 SPDX 等价 |
| ❓8 | **`PSScriptAnalyzer` 的 License / 版本** | 未直连官方 API 实测（仅社区资料提及常为 MIT） | 查 PowerShell Gallery / GitHub 官方 |
| ❓9 | **`ShellCheck` 的 star 数与版本日期为社区二手来源** | `v0.11.0 / 2025-08-04` 来自社区对比文，**未直连 GitHub API 实测**（WebFetch GitHub API 未尝试） | 直连 `api.github.com/repos/koalaman/shellcheck` |
| ❓10 | **`adr-tools` 的 star 数** | 对比文称 ~4.5k，**未实测** | 直连 GitHub API |
| ❓11 | **Keep a Changelog 仓库的 License** | 未实测（规范站未标注） | 查 `olivierlacan/keep-a-changelog` 仓库 LICENSE |
| ❓12 | **`mutmut` 的 `libcst` 是否为 C 扩展 / wheel 体积** | 未单独实测（`libcst` 通常有 Rust/C 加速） | 补一次 PyPI JSON 探测 |
| ❓13 | **`fastjsonschema` 靠 `exec` 生成校验码，在受限沙箱里是否被拦** | 未实测 | 本机跑一次 `fastjsonschema.compile()` |
| ❓14 | **tiktoken 的 BPE 词表是否必须联网下载（离线可否）** | 未实测 | 断网/清缓存后跑 `tiktoken.get_encoding('cl100k_base')` |
| ❓15 | **DeepSeek 真实可用模型 id 白名单 / `/models` 行为 / SSE 格式 / `usage` 字段位置** | **超出本线职责**，属**扫描员 A** 的特别点名项 | 归 A 线 |
| ❓16 | **CrewAI 当前版本形态** | **超出本线职责**，属**扫描员 A/B** | 归 A/B 线 |

---

# 十、附：实测脚本与原始数据（可复核）

| 文件 | 作用 |
|---|---|
| `scan/_pypi_probe.py` | 第一批 32 个 PyPI 包：license / license_expression / classifiers / requires_dist(剔 extra) / 最新上传时间 / 目标平台 wheel 体积 |
| `scan/_pypi_probe2.py` | 第二批 15 个包（regex / requests / cosmic-ray / eventsourcing / litellm / msgspec / check-jsonschema / jsonschema-rs / strictyaml / Cerberus / voluptuous / schema / attrs / configobj） |
| `scan/_summ_report.py` | 汇总 `pip --dry-run --report` 的**真实依赖闭包**（包数 / 包清单 / 是否含非纯 wheel） |
| `scan/_rep_*.json` | `pip install --dry-run --ignore-installed --report` 的原始报告（pytest / jsonschema / pydantic / fastjsonschema / json-repair） |
| `scan/_npm_probe.py` | npm registry 实测（adr-tools / @meza/adr-tools / log4brains / markdownlint-cli2 / mdformat） |

**复跑命令**（本机托管 Python）：
```bash
PY="C:/Users/one/.workbuddy/binaries/python/versions/3.14.3/python.exe"
"$PY" "D:/Ai/一些ai项目/项目2.0/six-layer-orchestrator/研讨_引擎层_2026-09-30/scan/_pypi_probe.py"
"$PY" "D:/Ai/一些ai项目/项目2.0/six-layer-orchestrator/研讨_引擎层_2026-09-30/scan/_pypi_probe2.py"
"$PY" "D:/Ai/一些ai项目/项目2.0/six-layer-orchestrator/研讨_引擎层_2026-09-30/scan/_summ_report.py"
"$PY" "D:/Ai/一些ai项目/项目2.0/six-layer-orchestrator/研讨_引擎层_2026-09-30/scan/_npm_probe.py"
```

> **注**：本报告全部结论基于 **2026-09-30** 当日实测。PyPI 元数据（版本 / 上传时间 / 依赖声明）随时间变化，**复核时请重跑上述脚本**，不要引用本报告的版本号当作现状。

---

**扫描员 C 声明**：本件只出证据与三张表，**不替 HT 拍板**。三值判定中"需实测"的 12 条，是把裁决权留给 HT 与家俊。
