#!/usr/bin/env python3
"""state_board.py — 跨窗口状态板（rule 84 · D-02 弱校验 + D-22 事件写入）

对应开发文档：
    D-02  状态板三分区 + **弱校验 (iii)**：结构合法 + 事件流区**行数单调不减**
    D-22  `cli.py status append "事件"` 进 L1b（本脚本即其落地）
    rule 84 跨窗口协作件（[假设 · B1 单项目试运行]）

★ 弱校验（本脚本能保证什么 / 不保证什么）：
    判：① **结构合法** —— 三分区标题存在 + 各表格列数一致
        ② **事件流区行数单调不减** —— 基线用**独立 append-only 日志**（`<板名>.count.log`），
           **禁止写回 progress.json**（progress.json 是断点三态的载体，不是留痕基线）
    **不判**：内容真伪、"用户动作是否都被记入"（漏记一律不报）
    → **弱校验通过 ≠ 事件流完整**。报告头固定打印 `[WEAK-CHECK]`。

用法：
    python scripts/state_board.py <项目目录> init [--board PROJECT_STATUS.md]
    python scripts/state_board.py <项目目录> check
    python scripts/state_board.py <项目目录> append "<事件>" ["<落盘证据>"]

退出码：0=通过 / 1=弱校验失败（结构非法或行数倒退）/ 2=目录或板文件不存在
"""
from __future__ import annotations

import argparse
import io
import re
import sys
from datetime import datetime
from pathlib import Path

DEFAULT_BOARD = "PROJECT_STATUS.md"
SECTIONS = {
    "state": "当前状态",
    "cmd": "待开发执行",
    "events": "事件流",
}
WEAK_HEADER = "[WEAK-CHECK] 只判结构合法 + 行数单调不减（弱校验通过 ≠ 事件流完整）"

TEMPLATE = """# {name} · 状态板（跨窗口单一事实源）

> **铁律**：**跨窗口动作必须落盘到这里** —— 只在对话里说 = 不存在。
> **本项目根** = {root}

---

## 一、当前状态（30 秒版本）

| 项 | 值 |
|---|---|
| **阶段** | INIT |
| **唯一开发依据** | <文件名> |
| **现在等谁** | <人 / 窗口> |
| **下一步** | <一个动作> |

---

## 二、待开发执行（指令区 · 只追加 + 只标状态，不删不改）

| 编号 | 指令 | 发布 | 状态 |
|---|---|---|---|

---

## 三、事件流（**只追加，不删除**；新事件加在表格末尾）

| 时间 | 谁 | 做了什么 | 落盘证据 |
|---|---|---|---|
"""


def _utf8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def board_path(root: Path, name: str) -> Path:
    return root / name


def count_log_path(root: Path, name: str) -> Path:
    """独立 append-only 基线日志（**不是** progress.json，D-02 明令禁写回它）"""
    return root / (name + ".count.log")


def _split_sections(text: str) -> dict:
    """按 '## ' 标题切分；返回 {标题: 正文}"""
    out, cur, buf = {}, "__pre__", []
    for line in text.splitlines():
        if line.startswith("## "):
            out[cur] = "\n".join(buf)
            cur, buf = line[3:].strip(), []
        else:
            buf.append(line)
    out[cur] = "\n".join(buf)
    return out


def _section_body(sections: dict, key_word: str):
    for title, body in sections.items():
        if key_word in title:
            return title, body
    return None, None


def _table_rows(body: str) -> list:
    """取正文里的表格数据行（排除表头与分隔行）"""
    rows = []
    for line in body.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        if re.match(r"^\|[\s\-:|]+\|$", s):      # 分隔行 |---|---|
            continue
        rows.append(s)
    return rows


def structural_check(text: str) -> tuple:
    """结构合法：三分区标题存在 + 每张表列数一致。返回 (ok, problems)"""
    problems = []
    sections = _split_sections(text)
    for key, word in SECTIONS.items():
        title, body = _section_body(sections, word)
        if title is None:
            problems.append(f"缺分区标题：含「{word}」的 ## 标题")
            continue
        rows = _table_rows(body)
        if not rows:
            problems.append(f"分区「{title}」没有表格行")
            continue
        widths = {r.count("|") for r in rows}
        if len(widths) > 1:
            problems.append(f"分区「{title}」表格列数不一致（| 计数 = {sorted(widths)}）")
    return (not problems), problems


def event_row_count(text: str) -> int:
    sections = _split_sections(text)
    _, body = _section_body(sections, SECTIONS["events"])
    if body is None:
        return -1
    return len(_table_rows(body))


def read_baseline(root: Path, name: str):
    p = count_log_path(root, name)
    if not p.exists():
        return None
    last = None
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.strip().split()
        if len(parts) >= 2 and parts[-1].lstrip("-").isdigit():
            last = int(parts[-1])
    return last


def write_baseline(root: Path, name: str, count: int):
    p = count_log_path(root, name)
    with io.open(p, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat(timespec='seconds')} {count}\n")


def cmd_init(root: Path, name: str) -> int:
    p = board_path(root, name)
    if p.exists():
        print(f"[state_board] 已存在，不覆盖：{p}")
        return 0
    p.write_text(TEMPLATE.format(name=root.name, root=root), encoding="utf-8")
    print(f"[state_board] 已建状态板：{p}")
    print(f"[state_board] {WEAK_HEADER}")
    return 0


def cmd_check(root: Path, name: str) -> int:
    p = board_path(root, name)
    if not p.exists():
        print(f"[state_board] 状态板不存在：{p}", file=sys.stderr)
        return 2
    text = p.read_text(encoding="utf-8", errors="replace")
    print(WEAK_HEADER)
    ok_struct, problems = structural_check(text)
    cur = event_row_count(text)
    base = read_baseline(root, name)

    print(f"  结构合法: {'✓' if ok_struct else '✗'}"
          + ("" if ok_struct else "  " + "; ".join(problems)))
    if base is None:
        print(f"  事件流行数: {cur}（无基线 → 本次建立基线，不做单调性判定）")
        mono = True
    else:
        mono = cur >= base
        print(f"  事件流行数: {cur}（基线 {base}）→ {'✓ 单调不减' if mono else '✗ 行数倒退'}")
    write_baseline(root, name, cur)          # 只追加基线日志（不碰 progress.json）

    ok = ok_struct and mono
    print(f"[state_board] 弱校验 {'通过' if ok else '失败'}"
          f" —— 提醒：**弱校验通过 ≠ 事件流完整**（漏记一律不报，也不校验内容真伪）")
    return 0 if ok else 1


def cmd_append(root: Path, name: str, event: str, evidence: str) -> int:
    """只追加一行到事件流表末尾（**绝不修改既有行**）。"""
    p = board_path(root, name)
    if not p.exists():
        print(f"[state_board] 状态板不存在：{p}（先 init）", file=sys.stderr)
        return 2
    text = p.read_text(encoding="utf-8", errors="replace")
    if not text.endswith("\n"):
        text += "\n"
    ts = datetime.now().strftime("%m-%d %H:%M")
    row = f"| {ts} | cli | {event} | {evidence or '-'} |\n"
    p.write_text(text + row, encoding="utf-8")     # 纯追加：原内容一个字节不动
    print(f"[state_board] 已追加事件行：{row.strip()}")
    return 0


def main() -> int:
    _utf8()
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--board", default=DEFAULT_BOARD)
    ap.add_argument("-h", "--help", action="store_true")
    args, rest = ap.parse_known_args()
    if args.help or len(rest) < 2:
        print(__doc__)
        return 0 if args.help else 1
    root = Path(rest[0])
    if not root.is_dir():
        print(f"[state_board] 目录不存在: {root}", file=sys.stderr)
        return 2
    cmd, extra = rest[1], rest[2:]
    if cmd == "init":
        return cmd_init(root, args.board)
    if cmd == "check":
        return cmd_check(root, args.board)
    if cmd == "append":
        if not extra:
            print("[state_board] append 需要事件文本", file=sys.stderr)
            return 1
        return cmd_append(root, args.board, extra[0], extra[1] if len(extra) > 1 else "")
    print(f"[state_board] 未知命令 {cmd}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
