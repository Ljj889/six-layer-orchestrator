#!/usr/bin/env python3
"""design_gate.py — 设计锁定 Gate（rule 65 · L1b）※ **本件已 WITHDRAWN（家俊 2026-09-30 裁决）**

★ 状态：**已撤回（withdrawn）** —— 家俊 2026-09-30 裁决「**当前不需要这个 Gate**」。
  处置依据：收尾研讨共识 Q1 + `references/design_gate_schema_draft.md` §四 触发条件表最后一行
  →「家俊明确'不需要这个 Gate' → 本件标 withdrawn，**从 pending 列表移除（不再挂着）**」。

★ 为什么当初是 pending（保留在案，不是错误意见）：
  `engine_config` 的 schema 也是开发方自拟的，但它**有外部判据**——写错会在下一次真实调用时被
  API 当场拒绝；而 `design_gate` 的 schema **没有外部判据**——漏写一项（如"数据迁移策略已确认"），
  **没有任何信号会告诉我们错了**，它会安静地给一个没做完设计的项目**发绿**。
  → schema 的内容只能由人定（rule 65：设计锁定 = 人机共同确认）。

★ 恢复路径（若将来需要）：`references/design_gate_schema_draft.md` 的四项解除条件
  （确认清单项 / 谁有权确认 / 未确认项处置 / 证据载体）全到位 → 升 v1.0 → 实现 `check` 与 `--finalize`。

★ 它不保证什么（即使将来恢复也成立）：
  **「design 命令能跑」≠「设计锁定完整」** —— rule 65 的流程含"边讨论边上网调研佐证"，
  命令行覆盖不到那一层。

用法：
    python scripts/design_gate.py

退出码：3 = 未执行（**withdrawn**，刻意与"通过=0"区分，防被 Gate 当成绿）
"""
from __future__ import annotations

import sys

WITHDRAWN_RC = 3

REASON = (
    "[design_gate] WITHDRAWN —— 本件已撤回（家俊 2026-09-30 裁决：当前不需要这个 Gate）。\n"
    "  处置依据：收尾研讨共识 Q1 + references/design_gate_schema_draft.md §四 触发条件表。\n"
    "  → 已从 pending 列表移除（不再挂着）；将来若需要，按草案件的**四项解除条件**恢复。\n"
    "  ★ 为什么当初不实现：engine_config 的 schema 有外部判据（写错会被 API 当场拒绝），\n"
    "    design_gate 的 schema **没有** —— 漏写一项不会有任何信号，会安静地给未完成设计的项目发绿。\n"
    "  ★ 它不保证什么（即使将来恢复也成立）：『design 命令能跑』≠『设计锁定完整』\n"
    "    （rule 65 流程含『边讨论边上网调研佐证』，命令行覆盖不到）。\n"
    "  退出码 3 = 未执行，刻意与『通过=0』区分，防被 Gate 当成绿。"
)


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    print(REASON)
    return WITHDRAWN_RC


if __name__ == "__main__":
    sys.exit(main())
