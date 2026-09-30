# 错误路由器设计（引擎层）

> 版本：v2.0 | 2026-09-30（v3.21.0 引擎落地 · D-14）；v1.0 = 2026-08-11（v3.9 编排 A 落地）
> 状态：**已引擎化** —— `scripts/route_error.py` + 关键词表外置 `scripts/route_error_table.json`
> 对应：SKILL.md rule 33（失败分类+路由）；`cli.py route-error`
> **v2.0 变更（D-14）**：① 关键词表**外置为数据文件**（带 `version` 字段）→ **改规则只改表，不发版**；
> ② 补合成样本**语法级单测**（3 条验收口 + 契约优先 + 外置表反证）；
> ③ **回归评测挂 pending**（需真实 FAIL 语料；伴学样本 = 1）；
> ④ **"审查 FAIL 真伪甄别"从本条剥离**（R-05：误报甄别与路由正交，登记为待立规则）。

## 问题

当前错误路由靠调度器 prompt 里的 LLM 判断——LLM 可能误判错误类型，导致路由到错误角色（如把合约级问题路由给架构师，见 T1 修正）。

## 设计：route_error() 纯规则函数

```python
def route_error(review_report: str) -> str:
    """输入审查报告 → 输出路由决策。纯规则匹配，不调 LLM。

    返回: "programmer_N" | "architect" | "scheduler" | "human"
    """
    # 代码级关键词 → 路由对应程序员（只重跑该模块）
    CODE_KEYWORDS = [
        "type hint", "docstring", "变量名", "函数签名",
        "@interface", "缩进", "import", "语法", "类型标注",
    ]
    # 架构级关键词 → 路由架构师（重新调研、重新拆）
    ARCH_KEYWORDS = [
        "模块拆分", "依赖环", "接口冲突", "粒度", "遗漏模块",
        "边界不清晰", "DAG", "循环依赖",
    ]
    # 合约级关键词 → 路由调度器（调度器+人修订合约 → 架构师重新拆）
    CONTRACT_KEYWORDS = [
        "合约", "contract", "规范冲突", "条款", "跨语言格式",
    ]

    text = review_report.lower()
    hits = {
        "code": sum(1 for k in CODE_KEYWORDS if k.lower() in text),
        "arch": sum(1 for k in ARCH_KEYWORDS if k.lower() in text),
        "contract": sum(1 for k in CONTRACT_KEYWORDS if k.lower() in text),
    }
    # 取命中数最高者；平票且含合约 → 合约优先（T1 修正：合约级必须路由调度器）
    best = max(hits, key=lambda k: hits[k])
    if hits[best] == 0:
        return "human"          # 无法判断 → 标记人工裁决
    if hits["contract"] >= hits["code"] and hits["contract"] > 0:
        return "scheduler"      # 合约级 → 调度器（人修订合约）
    if best == "code":
        return "programmer_N"   # 具体 N 由调度器结合模块 id 决定
    if best == "arch":
        return "architect"
    return "human"
```

## 规则优先级（重要）

1. **合约级关键词命中即路由调度器**（哪怕同时含代码级关键词）——因为合约是调度器+人定的，架构师没权限改（T1 修正）。
2. 代码级 vs 架构级冲突时：按命中数决定；**无法判断 → 标记人工裁决**，禁止 LLM 猜。
3. 本函数只做"错误类型 → 目标角色"的映射；"具体重跑哪个模块"仍由调度器结合模块 id 决策。

## 落地说明

- **已引擎化（v3.21.0 · L1b）**：`python scripts/route_error.py "<报告文本>"`（或 `cli.py route-error`）
  —— 纯规则函数，**不调 LLM**。关键词表在 `scripts/route_error_table.json`（`version=v1.0`，30 个关键词）。
- **改规则 → 只改表**：新增/调整关键词、改 target 映射，都只动 JSON，**代码不发版**。
  表改动后应重跑 `engine_selftest --only TestL1bTools`（三条验收口 + 契约优先 + 外置表反证）。
- **验收（已固化为单测）**：输入含"合约条款过严" → `scheduler`；含"type hint 缺失" → `programmer_N`；
  无法判断 → `human`；同时含合约与代码关键词 → 仍 `scheduler`（T1 修正）。
- **挂 pending 项**（`route_error.py --status` 可打印）：
  ① 回归评测（需真实 FAIL 语料）；② 审查 FAIL 真伪甄别（R-05，待立新规则）。
- **它不保证什么**：本条只做"错误类型 → 目标角色"的映射；**不判 FAIL 本身真伪**、
  **不做回归评测**。具体重跑哪个模块仍由调度器结合模块 id 决策。
