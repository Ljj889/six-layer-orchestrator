#!/usr/bin/env python3
"""design_gate.py — 设计锁定 Gate（rule 65 · L1b）※ **本件挂 pending**

★ 硬门（开发文档 §4.2 L1b）：**schema 未定稿 → 本件挂 pending**。

设计锁定 Gate（`cli.py design --finalize`）需要一个**已定稿的确认清单 schema**才能机械判定
"设计是否真的锁定"（逐项确认了哪些、谁确认的、确认时间、未确认项怎么处置）。

当前状态：**该 schema 未定稿** → 本件**不实现**，显式返回 pending（**不伪造能力**）。

★ 它不保证什么（必须随件交付）：
   即使将来 `design` 命令能跑，**也 ≠ "设计锁定完整"** ——
   rule 65 的流程含"边讨论边上网调研佐证"，命令行覆盖不到那一层。

用法：
    python scripts/design_gate.py [--status]

退出码：3 = pending（**未实现**，刻意与"通过=0"区分）
"""
from __future__ import annotations

import sys

PENDING_RC = 3

REASON = (
    "[design_gate] PENDING —— 设计锁定 Gate 未实现：\n"
    "  硬门（开发文档 §4.2 L1b）：schema 未定稿 → 本件挂 pending。\n"
    "  已交付的解除条件件：references/design_gate_schema_draft.md（**草案，未生效**）。\n"
    "  解除 pending 需家俊给四项：① 确认清单项列表 ② 谁有权确认 ③ 未确认项处置 ④ 证据载体。\n"
    "  ★ 为什么开发方不自拟 schema：engine_config 的 schema 有外部判据（写错会被 API 当场拒绝），\n"
    "    design_gate 的 schema **没有** —— 漏写一项不会有任何信号，它会安静地给未完成设计的项目发绿。\n"
    "  ★ 不保证什么：即使将来能跑，『design 命令能跑』≠『设计锁定完整』\n"
    "    （rule 65 流程含『边讨论边上网调研佐证』，命令行覆盖不到）。\n"
    "  退出码 3 = pending，刻意与『通过=0』区分，防被 Gate 当成绿。"
)


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    print(REASON)
    return PENDING_RC


if __name__ == "__main__":
    sys.exit(main())
