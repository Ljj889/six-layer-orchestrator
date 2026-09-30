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
    "  需要先定稿的 schema：设计确认清单（逐项 id / 谁确认 / 确认时间 / 未确认项处置）。\n"
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
