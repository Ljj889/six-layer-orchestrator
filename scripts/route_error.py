#!/usr/bin/env python3
"""route_error.py — 错误路由器（rule 33 引擎化 · D-14 · L1b）

**纯规则函数，不调 LLM。** 关键词表**外置为数据文件** `route_error_table.json`（带版本号）——
**改规则只改表，不发版**（D-14）。

三条优先级（沿用 references/error_routing.md）：
  1. **合约级命中即路由 `scheduler`**（哪怕同时含代码级关键词）—— 合约是调度器+人定的，架构师无权限改（T1 修正）
  2. 代码级 vs 架构级冲突 → 按**命中数**决定
  3. 命中 0 → **`human`**（人工裁决），**禁止猜**

★ 本条**不做**的事（D-14 显式剥离 / R-05 待立规则）：
  - **不判"审查 FAIL 本身真伪"** —— 误报甄别（"FAIL 判定可信吗"）与路由（"错误类型→哪个角色"）**正交**；
    v3.19.0 已实证"检查器自己会说谎"，该问题登记为**待立规则**，不并入本条。
  - **不做回归评测** —— 需真实 FAIL 语料，伴学样本 = 1 → **挂 pending**（见 --status）。

用法：
    python scripts/route_error.py "<审查报告文本>"
    python scripts/route_error.py --file <报告路径> [--json]
    python scripts/route_error.py --status        # 打印表版本 + pending 项

退出码：0=已给出路由决策 / 2=无输入或输入非法
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

TABLE_PATH = Path(__file__).resolve().parent / "route_error_table.json"
PENDING = [
    "回归评测（需真实 FAIL 语料；伴学样本=1）",
    "审查 FAIL 真伪甄别（R-05：已从本条剥离，待立新规则）",
]


def load_table(path: Path = None) -> dict:
    p = path or TABLE_PATH
    t = json.loads(p.read_text(encoding="utf-8"))
    for req in ("version", "targets", "priority", "keywords"):
        if req not in t:
            raise ValueError(f"route_error 表缺字段 {req}：{p}")
    return t


def route_error(report: str, table: dict) -> dict:
    """纯规则：审查报告 → 路由决策。返回 {target, bucket, hits, table_version}"""
    text = (report or "").lower()
    hits = {b: 0 for b in table["keywords"]}
    for bucket, words in table["keywords"].items():
        for w in words:
            if str(w).lower() in text:
                hits[bucket] = hits.get(bucket, 0) + 1

    # 规则 1：合约级优先（命中即 scheduler）
    if hits.get("contract", 0) > 0 and hits["contract"] >= hits.get("code", 0):
        bucket = "contract"
    else:
        scored = {b: hits.get(b, 0) for b in ("code", "arch")}
        best = max(scored, key=lambda k: scored[k])
        bucket = best if scored[best] > 0 else "none"
    target = table["targets"].get(bucket, table["targets"]["none"])
    return {"target": target, "bucket": bucket, "hits": hits,
            "table_version": table["version"]}


def render(res: dict) -> str:
    hits = " ".join(f"{k}={v}" for k, v in sorted(res["hits"].items()))
    lines = [f"[route_error] table_version={res['table_version']} hits[{hits}]",
             f"[route_error] → target={res['target']} (bucket={res['bucket']})"]
    if res["bucket"] == "none":
        lines.append("[route_error] 命中 0 → 人工裁决（禁止猜；本条只做类型→角色映射，"
                     "不判 FAIL 真伪 —— R-05）")
    lines.append("[route_error] 它不保证什么：不做回归评测（挂 pending）；不判 FAIL 真伪（R-05）")
    return "\n".join(lines)


def _utf8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def main() -> int:
    _utf8()
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("text", nargs="?", default="")
    ap.add_argument("--file", default="")
    ap.add_argument("--table", default="")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("-h", "--help", action="store_true")
    args = ap.parse_args()
    if args.help:
        print(__doc__)
        return 0
    table = load_table(Path(args.table) if args.table else None)
    if args.status:
        print(f"[route_error] table_version={table['version']} updated={table.get('updated')} "
              f"keywords={sum(len(v) for v in table['keywords'].values())}")
        for p in PENDING:
            print(f"[route_error] PENDING: {p}")
        return 0
    text = args.text
    if args.file:
        p = Path(args.file)
        if not p.exists():
            print(f"[route_error] 报告文件不存在: {p}", file=sys.stderr)
            return 2
        text = p.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        print("[route_error] 需要报告文本（位置参数或 --file）", file=sys.stderr)
        return 2
    res = route_error(text, table)
    print(json.dumps(res, ensure_ascii=False, indent=2) if args.json else render(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
