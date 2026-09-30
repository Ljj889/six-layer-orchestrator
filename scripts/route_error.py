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
    python scripts/route_error.py --eval <corpus.jsonl>   # 跑语料（首行 _meta.kind 必填）
    python scripts/route_error.py --status        # 打印表版本 + regression_eval + pending 项

**回归评测口径（收尾研讨共识 Q3）**：
    - 语料首行必须写 `{"_meta": true, "kind": "synthetic"|"real"}`，**缺 kind 即 FAIL**；
    - **合成语料（kind=synthetic）无论全绿与否，一律 exit 3 = PENDING** —— 跑绿只证明"harness 可用"，
      **不构成「回归评测通过」**（防合成语料被当真实评测读成假绿）；
    - `regression_eval` 状态由**代码常量** `REGRESSION_EVAL_STATUS` 决定，**不由输出文本决定**；
    - 真实语料（kind=real）全绿才 exit 0，届时才可把常量改成"passed"。

退出码：0=已给出路由 / 1=参数或输入非法 / 2=无输入或语料不合法 / 3=回归评测未成立（PENDING）
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

TABLE_PATH = Path(__file__).resolve().parent / "route_error_table.json"
SYNTHETIC_CORPUS = Path(__file__).resolve().parent / "route_error_corpus_synthetic.jsonl"

# ── 收尾研讨共识 Q3：回归评测的 PENDING 由**代码常量**决定，不由输出文本决定 ──
# （理由：状态板的弱校验曾"报绿但 append 静默失效"—— 文本会被跳过，常量不会。）
REGRESSION_EVAL_STATUS = "pending"
REGRESSION_EVAL_REASON = ("需真实 FAIL 语料；伴学样本=1 → 合成语料跑绿不得算通过"
                          "（kind=synthetic 一律返回 PENDING / exit 3）")
PENDING = [
    f"回归评测（{REGRESSION_EVAL_REASON}）",
    "审查 FAIL 真伪甄别（R-05：已从本条剥离；收尾研讨裁为『下一版第一项』，"
    "前置=判据须先试写成可机械判定的形式）",
]
PENDING_RC = 3


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


def load_corpus(path: Path) -> tuple:
    """读语料（JSONL）。首行可带 `{"_meta": true, "kind": "synthetic"|"real", ...}`。
    返回 (kind, cases)。**kind 缺失 → FAIL**（不许默认成 real，也不许默认成 synthetic 蒙混）。
    """
    kind = None
    cases = []
    for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception as e:
            raise ValueError(f"语料第 {i + 1} 行非法 JSON：{e}")
        if obj.get("_meta"):
            kind = obj.get("kind")
            continue
        if not isinstance(obj, dict) or "text" not in obj or "expect" not in obj:
            raise ValueError(f"语料第 {i + 1} 行缺 text/expect 字段")
        cases.append(obj)
    if kind not in ("synthetic", "real"):
        raise ValueError("语料首行必须带 {\"_meta\": true, \"kind\": \"synthetic\"|\"real\"} —— "
                         "kind 缺失即 FAIL（防合成语料被当成真实评测）")
    return kind, cases


def eval_corpus(path: Path, table: dict) -> dict:
    """跑语料。**合成语料即使全绿也不构成"回归评测通过"**（共识 Q3 / D-14）。"""
    kind, cases = load_corpus(path)
    rows = []
    for c in cases:
        got = route_error(c["text"], table)["target"]
        rows.append({"id": c.get("id", "?"), "text": c["text"],
                     "expect": c["expect"], "got": got, "ok": got == c["expect"]})
    n_ok = sum(1 for r in rows if r["ok"])
    all_ok = n_ok == len(rows)
    # 退出码语义（双信号一致）：合成 → 无论全绿与否一律 3=PENDING；真实 → 全绿 0 / 有错 1
    rc = PENDING_RC if kind == "synthetic" else (0 if all_ok else 1)
    return {"corpus": str(path), "kind": kind, "n": len(rows), "n_ok": n_ok,
            "all_ok": all_ok, "rows": rows, "rc": rc,
            "regression_eval_status": REGRESSION_EVAL_STATUS,
            "verdict": ("PENDING（合成语料，不构成回归评测通过）" if kind == "synthetic"
                        else ("PASS（真实语料）" if all_ok else "FAIL（真实语料）"))}


def render_eval(res: dict) -> str:
    lines = [f"[route_error] corpus_kind={res['kind']} n={res['n']} ok={res['n_ok']} "
             f"→ {res['verdict']}"]
    for r in res["rows"]:
        mark = "✓" if r["ok"] else "✗"
        lines.append(f"  {mark} {r['id']} expect={r['expect']} got={r['got']}  « {r['text']}»")
    lines.append(f"[route_error] regression_eval={res['regression_eval_status']} "
                 f"（由代码常量决定，不由输出文本决定）· exit={res['rc']}")
    if res["kind"] == "synthetic":
        lines.append("[route_error] ★ 合成语料跑绿 = **仅证明 harness 可用**，"
                     "**不构成「回归评测通过」**（exit 3 = PENDING）")
    lines.append("[route_error] 它不保证什么：不做 FAIL 真伪甄别（R-05 已剥离）")
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
    ap.add_argument("--eval", default="", help="跑语料（JSONL，首行 _meta.kind）")
    ap.add_argument("-h", "--help", action="store_true")
    args = ap.parse_args()
    if args.help:
        print(__doc__)
        return 0
    table = load_table(Path(args.table) if args.table else None)
    if args.status:
        print(f"[route_error] table_version={table['version']} updated={table.get('updated')} "
              f"keywords={sum(len(v) for v in table['keywords'].values())}")
        print(f"[route_error] regression_eval={REGRESSION_EVAL_STATUS}")
        for p in PENDING:
            print(f"[route_error] PENDING: {p}")
        return 0
    if args.eval:
        p = Path(args.eval)
        if not p.exists():
            print(f"[route_error] 语料不存在: {p}", file=sys.stderr)
            return 2
        try:
            res = eval_corpus(p, table)
        except ValueError as e:
            print(f"[route_error] 语料不合法：{e}", file=sys.stderr)
            return 2
        print(json.dumps(res, ensure_ascii=False, indent=2) if args.json else render_eval(res))
        return res["rc"]
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
