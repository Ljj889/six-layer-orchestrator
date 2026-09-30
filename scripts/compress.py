#!/usr/bin/env python3
"""compress.py — 上下文压缩 LC1 / LC2（rule 83 · L1b）

**机械层，不花 LLM**（`llm_calls=0` 是硬断言）。三级级联里只有 **LC3 结构化摘要**才花 LLM，
属 L2；本脚本只做 **LC1 子 Agent 回报压缩** 与 **LC2 已消费输入淘汰**。

    LC1  子 Agent 回报压缩：回报**只留「结论 + 证据指针」**。本脚本只做**字段抽取**，
         不改写、不转述原话（rule 83 硬纪律 ③）；全量报告仍应落盘（本脚本**不删磁盘**）。
    LC2  已消费输入淘汰：`consumed_by` 非空的输入块 → 退出上下文，**替换为指针**
         （标记 ≠ 删除；磁盘上仍可查）。

三条硬纪律（rule 83）：
    ① 摘要**不替代** progress.json（结构化事实源；冲突时以 progress.json 为准）
    ② **指针优先** —— 凡涉及文件/代码必须带 `路径 + 行号@commit`；**缺 commit 锚 → 标 `pointer_weak`**
    ③ **不得转述子 Agent 原话**（LC1 只抽字段）

复述测试（压缩后**必跑**，rule 83 硬步骤）：仅凭产物能否复述
    **phase / ruled_out / open_items / next** 四项？不能 → 说明该落盘的没落盘 → **FAIL，回退重压**。

输入 bundle（JSON）字段：
    phase, modules, ruled_out, top_suspect, open_items, next,
    consumed_inputs:  [{"id","path","commit","consumed_by","text"}],
    subagent_reports: [{"agent","verdict","artifacts":[],"open_questions":[],"narrative"}]

用法：
    python scripts/compress.py <bundle.json> [--out <out.json>] [--json]

退出码：0=压缩成功且复述测试通过 / 1=复述测试失败 / 2=输入非法
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

RESTATE_FIELDS = ("phase", "ruled_out", "open_items", "next")
SIX_FIELDS = ("phase", "modules", "ruled_out", "top_suspect", "open_items", "next")
_COMMIT_RE = re.compile(r"@[0-9a-fA-F]{7,40}\b")


def _pointer_weak(pointer: str) -> bool:
    """指针是否"弱"：缺 `@commit` 锚的行号会漂移误导（rule 83 硬纪律 ②）。"""
    return not bool(_COMMIT_RE.search(pointer or ""))


def _utf8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def lc1_reports(reports: list) -> tuple:
    """LC1：只抽「结论 + 证据指针」，丢弃叙述性正文（不转述、不改写）。"""
    kept, pointers = [], []
    for r in reports:
        if not isinstance(r, dict):
            continue
        entry = {
            "agent": r.get("agent"),
            "verdict": r.get("verdict"),
            "artifacts": list(r.get("artifacts") or []),
            "open_questions": list(r.get("open_questions") or []),
            "chars_dropped": len(str(r.get("narrative") or "")),
        }
        kept.append(entry)
        for a in entry["artifacts"]:
            if str(a).strip():
                pointers.append({"path": str(a), "weak": _pointer_weak(str(a)),
                                 "from": r.get("agent")})
    return kept, pointers


def lc2_consumed(inputs: list) -> tuple:
    """LC2：已消费输入 → 退出上下文，替换为指针。标记 ≠ 删除。"""
    dropped, kept = 0, []
    pointers = []
    for it in inputs:
        if not isinstance(it, dict):
            continue
        if str(it.get("consumed_by") or "").strip():
            dropped += 1
            ptr = f"{it.get('path') or it.get('id')}" + (
                f"@{it.get('commit')}" if it.get("commit") else "")
            pointers.append({"path": ptr, "weak": _pointer_weak(ptr),
                             "consumed_by": it.get("consumed_by")})
        else:
            kept.append(it)
    return dropped, kept, pointers


def compress(bundle: dict) -> dict:
    six = {k: bundle.get(k) for k in SIX_FIELDS}
    reports_in = bundle.get("subagent_reports") or []
    inputs_in = bundle.get("consumed_inputs") or []

    lc1_kept, lc1_ptr = lc1_reports(reports_in)
    dropped, lc2_kept, lc2_ptr = lc2_consumed(inputs_in)

    pointers = lc1_ptr + lc2_ptr
    weak = [p for p in pointers if p.get("weak")]

    before = len(json.dumps(bundle, ensure_ascii=False))
    compressed = {
        "phase": six["phase"],
        "modules": six["modules"],
        "ruled_out": six["ruled_out"],
        "top_suspect": six["top_suspect"],
        "open_items": six["open_items"],
        "next": six["next"],
        "subagent_reports": lc1_kept,
        "pointers": pointers,
        "kept_unconsumed_inputs": lc2_kept,
        "lc3_input": {k: six[k] for k in SIX_FIELDS},   # LC3（LLM）的输入骨架，本层不填
    }
    after = len(json.dumps(compressed, ensure_ascii=False))

    restate = {k: bool(six.get(k)) for k in RESTATE_FIELDS}
    narr_dropped = sum(e.get("chars_dropped", 0) for e in lc1_kept)
    return {
        "compressed": compressed,
        "stats": {
            "lc1_reports_before": len(reports_in),
            "lc1_reports_after": len(lc1_kept),
            "lc2_inputs_dropped": dropped,
            "lc2_inputs_kept": len(lc2_kept),
            "narrative_chars_dropped": narr_dropped,
            "chars_before": before,
            "chars_after": after,
            "ratio": round(after / before, 3) if before else 0.0,
            "ratio_caveat": "ratio 含指针/lc3_input 等元数据；**小 bundle 可能 >1（膨胀）**，"
                            "只有大 bundle 才看得出真实压缩率 —— 真实收益看 narrative_chars_dropped",
        },
        "restate_test": dict(restate, ok=all(restate.values())),
        "llm_calls": 0,
        "weak_pointers": weak,
        "not_guaranteed": [
            "摘要不替代 progress.json（结构化事实源；冲突以 progress.json 为准）",
            "weak 指针（缺 @commit）行号会漂移误导，需补锚",
            "本层不删磁盘：LC2 是『不再进上下文』，不是删除",
            "LC3 结构化摘要（花 LLM）不在本层",
        ],
    }


def main() -> int:
    _utf8()
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("bundle", nargs="?", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("-h", "--help", action="store_true")
    args = ap.parse_args()
    if args.help:
        print(__doc__)
        return 0
    if not args.bundle:
        print("[compress] 需要 bundle.json", file=sys.stderr)
        return 2
    p = Path(args.bundle)
    if not p.exists():
        print(f"[compress] 文件不存在: {p}", file=sys.stderr)
        return 2
    try:
        bundle = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[compress] 解析失败: {e}", file=sys.stderr)
        return 2
    if not isinstance(bundle, dict):
        print("[compress] bundle 必须是 JSON 对象", file=sys.stderr)
        return 2

    res = compress(bundle)
    if args.out:
        Path(args.out).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        s, rt = res["stats"], res["restate_test"]
        print(f"[compress] LC1 回报 {s['lc1_reports_before']}→{s['lc1_reports_after']} · "
              f"LC2 淘汰 {s['lc2_inputs_dropped']} 条 · "
              f"叙述正文丢弃 {s['narrative_chars_dropped']} 字符 · "
              f"字符 {s['chars_before']}→{s['chars_after']}（ratio={s['ratio']}；"
              "小 bundle 可能 >1，真实收益看 narrative_chars_dropped）")
        print(f"[compress] llm_calls={res['llm_calls']}（LC1/LC2 机械层，不花 LLM）")
        for k in RESTATE_FIELDS:
            print(f"[compress]   复述 {k}: {'✓' if rt[k] else '✗'}")
        if res["weak_pointers"]:
            print(f"[compress] ⚠ weak 指针 {len(res['weak_pointers'])} 条（缺 @commit 锚，"
                  "行号会漂移误导 —— rule 83 硬纪律②）")
        print(f"[compress] 复述测试: {'PASS' if rt['ok'] else 'FAIL'}"
              "（phase/ruled_out/open_items/next 四项必须可复述）")
    return 0 if res["restate_test"]["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
