#!/usr/bin/env python3
"""read_knowledge 原语 · 引擎层参考实现（框架对齐 v3.16.0；自 v3.9.3 起）

对应 SKILL.md rule 59：从 knowledge/_index.md（canonical entry）按问题类型/tags
检索 active 资产，供注入 spec/plan/constitution 或 just-in-time 使用。

用法:
    python scripts/read_knowledge.py "成本 熔断"                  # 默认 all scope, active, top_k 5
    python scripts/read_knowledge.py "checkpoint" --scope user --top_k 3
    python scripts/read_knowledge.py "安全" --include_stale      # 显式看 stale

实现要点:
    - 索引优先: 只读 _index.md, 不盲搜整个 knowledge/
    - 按 tags/摘要匹配: 不按项目名 (NASA LLIS 覆辙)
    - 状态过滤: 默认只读 active; 过期(last_verified 超 review_cycle)标 stale
    - 精度优先: top_k 截断, 防上下文膨胀 (rule 40 <2,000 行)
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
INDEX_PATH = SKILL_DIR / "knowledge" / "_index.md"


def _parse_review_cycle(cycle: str) -> timedelta:
    """'90d' -> timedelta(days=90); 解析失败返回 None(不判过期)"""
    m = re.match(r"(\d+)([dwm])", cycle.strip().lower())
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2)
    days = n * {"d": 1, "w": 7, "m": 30}[unit]
    return timedelta(days=days)


def read_index() -> list[dict]:
    """解析 _index.md 表格 -> list[Asset dict]"""
    if not INDEX_PATH.exists():
        print(f"[read_knowledge] ❌ 索引不存在: {INDEX_PATH}", file=sys.stderr)
        print("[read_knowledge] 未查索引不得声称'无相关先验经验'（rule 59 / Red Flag）", file=sys.stderr)
        return []
    assets = []
    for line in INDEX_PATH.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 6 or cells[0] in ("路径", "---"):
            continue
        path, atype, status, tags, summary, verified = cells[:6]
        assets.append({
            "path": path, "type": atype, "status": status,
            "tags": tags, "summary": summary, "last_verified": verified,
        })
    return assets


def _is_stale(asset: dict) -> bool:
    cycle = timedelta(days=90)  # 默认 90d; 精确值应读资产 frontmatter
    try:
        last = datetime.strptime(asset["last_verified"], "%Y-%m-%d")
    except (ValueError, TypeError):
        return False
    return datetime.now() - last > cycle


def read_knowledge(query: str, scope: str = "all", status_filter: str = "active",
                   top_k: int = 5, include_stale: bool = False) -> list[dict]:
    """① 读 _index.md → ② tags/摘要匹配 → ③ 过滤 scope+status → ④ 返回 top_k

    scope 语义: all=不过滤 / user=rules|decisions|framework-skills|guides 四桶(框架级共享)
                / project=project 前缀(当前项目) / local=local 前缀(本机专用)
    knowledge/ 资产库本身是框架级(user)共享, 默认 all 保证开工前能读到全部 active 资产。
    """
    assets = read_index()
    if not assets:
        return []
    terms = [t for t in re.split(r"[\s,，/、]+", query.lower()) if t]
    user_buckets = ("rules/", "decisions/", "framework-skills/", "guides/")
    hits = []
    for a in assets:
        if status_filter and a["status"] != status_filter:
            continue
        if scope == "user" and not a["path"].startswith(user_buckets):
            continue
        if scope == "project" and not a["path"].startswith(("project/",) + user_buckets):
            continue
        if scope == "local" and not a["path"].startswith("local/"):
            continue
        hay = (a["tags"] + " " + a["summary"]).lower()
        n_hit = sum(1 for t in terms if t.lower() in hay)
        if n_hit == 0:
            continue
        entry = dict(a)
        entry["stale"] = _is_stale(a)
        entry["n_hit"] = n_hit
        if entry["stale"] and not include_stale:
            entry["stale_note"] = "⚠️ 过期(last_verified 超 review_cycle)，依赖前须复核"
        hits.append(entry)
    # 命中词多者在前（更相关），再截断（精度优先）
    hits.sort(key=lambda x: x["n_hit"], reverse=True)
    return hits[:top_k]


def _force_utf8_stdio():
    """stdio 加固（v3.16.0）：Windows 控制台默认 GBK 下非 ASCII 输出会 UnicodeEncodeError。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def main() -> None:
    _force_utf8_stdio()
    ap = argparse.ArgumentParser(description="read_knowledge 原语参考实现 (rule 59)")
    ap.add_argument("query", nargs="?", default="", help="检索关键词（按 tags/摘要匹配）")
    ap.add_argument("--scope", default="all", choices=["all", "user", "project", "local"])
    ap.add_argument("--top_k", type=int, default=5)
    ap.add_argument("--include_stale", action="store_true")
    args = ap.parse_args()

    hits = read_knowledge(args.query, scope=args.scope, top_k=args.top_k,
                          include_stale=args.include_stale)
    if not hits:
        print(f"[read_knowledge] query='{args.query}' scope={args.scope} → 0 命中")
        print("[read_knowledge] 未读索引=/ 无匹配 = 不得声称'无先验经验'——扩大关键词或查 _index.md")
        return
    print(f"[read_knowledge] query='{args.query}' scope={args.scope} → {len(hits)} 条 active 资产：")
    for h in hits:
        flag = f" {h.get('stale_note', '')}" if h.get("stale") else ""
        print(f"  - {h['path']} [{h['type']}] tags={h['tags']}{flag}")
        print(f"    {h['summary']}")


if __name__ == "__main__":
    main()
