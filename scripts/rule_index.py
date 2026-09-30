#!/usr/bin/env python3
"""rule_index.py — SKILL.md 规则索引自报（R-13：一切"现状数字"由脚本自报，禁止手抄）

来源：引擎层研讨 R-13 元层风险——同一件事（自测用例数）曾出现 24/25/30/27 四个数字，
讨论文档错、"纠正值"也错。凡进验收口/版本 banner 的"现状数字"必须由本脚本产出。

做四件事（全部可 grep）：
    1. 规则编号现状（有效条数 / 最大号 / 删除留空号）
    2. "Phase -2 流程步骤"与"真正的 rule"分离（1/2/3/4/5/6 是流程步骤，不是 rule）
    3. 引擎参数单一来源节的「子命令 ↔ rule 号」映射表交叉核对（引用的 rule 号是否都存在）
    4. 版本标记分布（banner 剪枝后的首个/末个锚点，供 sync 抽检锚点核对）

用法：
    python scripts/rule_index.py [SKILL.md 路径]        # 人类可读
    python scripts/rule_index.py <path> --json          # 机器可读

退出码：0=通过 / 1=发现不一致（映射表引用不存在的 rule 号 / 删除号被复用）
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

# Phase -2/-1 的流程步骤编号——它们是"步骤"不是"rule"，须从 rule 计数里剔除
# （实测：Phase -2 步骤 1..6、Phase -1 步骤 7 与全局 rule 编号共用同一数字空间）
_PROCESS_STEP_NUMS = {1, 2, 3, 4, 5, 6, 7}
_PROCESS_STEP_SECTION = "### Phase -2"
_MIN_RULE_NO = 10  # 全局 rule 编号从 10 起（1-9 被 Phase 流程步骤占用，实测自报）

DELETED_NUMS = {13, 15, 17, 25, 26, 30}  # 全局删除号，留空不复用


def _read(path: Path) -> str:
    return io.open(path, encoding="utf-8").read()


def _sections(text: str) -> list:
    """把文本切成 [(section_title, body)]；标题行以 '###' 或 '##' 开头"""
    lines = text.splitlines()
    out, cur_title, cur = [], "__preamble__", []
    for ln in lines:
        if re.match(r"^#{2,4}\s", ln):
            out.append((cur_title, "\n".join(cur))
                       )
            cur_title, cur = ln.strip(), []
        else:
            cur.append(ln)
    out.append((cur_title, "\n".join(cur)))
    return out


def collect(text: str) -> dict:
    rule_nums = []
    for title, body in _sections(text):
        for m in re.finditer(r"(?m)^(\d{1,2})\.\s+", body):
            n = int(m.group(1))
            if n < _MIN_RULE_NO:
                continue  # 1-9 = Phase 流程步骤编号，不是 rule（实测自报：rule 从 10 起）
            if n in _PROCESS_STEP_NUMS and title.startswith(_PROCESS_STEP_SECTION):
                continue
            rule_nums.append(n)
    uniq = sorted(set(rule_nums))
    gaps = [x for x in range(1, (max(uniq) + 1) if uniq else 1) if x not in uniq]

    # 版本标记（按出现顺序去重）
    marks = []
    for m in re.finditer(r"v\d+\.\d+\.\d+", text):
        if m.group(0) not in marks:
            marks.append(m.group(0))

    # 映射表：子命令 ↔ rule 号（在「引擎参数单一来源」节里找 `rule NN`）
    mapping_refs = []
    for title, body in _sections(text):
        if "引擎参数单一来源" in title:
            for m in re.finditer(r"rule\s+(\d{1,2})", body):
                mapping_refs.append(int(m.group(1)))
    mapping_missing = [n for n in sorted(set(mapping_refs)) if n not in uniq]

    return {
        "rules_effective": len(uniq),
        "max_rule_no": max(uniq) if uniq else 0,
        "rule_numbers": uniq,
        "number_gaps": gaps,
        "deleted_nums": sorted(DELETED_NUMS),
        "deleted_ok": all(d not in uniq for d in DELETED_NUMS),
        "version_marks": marks,
        "version_first": marks[0] if marks else None,
        "version_last": marks[-1] if marks else None,
        "mapping_refs": sorted(set(mapping_refs)),
        "mapping_missing": mapping_missing,
    }


def render(d: dict) -> str:
    lines = [
        f"[RULE-INDEX] rules_effective={d['rules_effective']} max_rule_no={d['max_rule_no']}",
        f"[RULE-INDEX] number_gaps={','.join(str(x) for x in d['number_gaps']) or '-'}"
        f" deleted_nums_ok={d['deleted_ok']}",
        f"[RULE-INDEX] version_marks={len(d['version_marks'])} first={d['version_first']}"
        f" last={d['version_last']}",
        f"[RULE-INDEX] mapping_refs={len(d['mapping_refs'])}"
        f" missing={','.join(str(x) for x in d['mapping_missing']) or 'none'}",
    ]
    if d["mapping_missing"]:
        lines.append(f"→ FAIL：映射表引用了不存在的 rule 号 {d['mapping_missing']}（防代码漂移）")
    if not d["deleted_ok"]:
        lines.append("→ FAIL：删除号被复用（rule 编号只增，删号留空）")
    return "\n".join(lines)


def _force_utf8_stdio():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def main() -> int:
    _force_utf8_stdio()
    args = [a for a in sys.argv[1:] if a != "--json"]
    as_json = "--json" in sys.argv[1:]
    path = Path(args[0]) if args else Path(__file__).resolve().parent.parent / "SKILL.md"
    if not path.exists():
        print(f"[RULE-INDEX] SKILL.md 不存在: {path}", file=sys.stderr)
        return 2
    d = collect(_read(path))
    d["file"] = str(path)
    print(json.dumps(d, ensure_ascii=False, indent=2) if as_json else render(d))
    bad = bool(d["mapping_missing"]) or (not d["deleted_ok"])
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
