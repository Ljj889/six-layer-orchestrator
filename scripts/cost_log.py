"""cost_log.py — 成本账本定长行管理（rule 38/53 · 框架对齐 v3.16.0；引擎自 v3.9.13 起）

来源：编排系统项目 cost_tracker.py 按框架语义适配（2026-09-01）。
与 rule 38/53 对齐：每次派发追加一行定长记录（可 grep）：
    [时间]|[派发对象]|[档位 lite/default/reasoning]|[预估成本]|[结果 成功/失败/时长]|[异常类型: 超时/空/非法JSON/截断/无]
缺第 6 列异常类型或为空值 = 记录不合规（rule 53）。

用法：
    python cost_log.py <项目目录> add <对象> <档位> <预估成本> <结果> [异常类型]
    python cost_log.py <项目目录> summary          汇总（含不合规检查）
    python cost_log.py <项目目录> tail              查看最近 N 行（默认 10）

退出码：0=成功 / 1=参数或校验失败 / 2=目录不存在
"""
import sys
from datetime import datetime
from pathlib import Path

ALLOWED_TIERS = {"lite", "default", "reasoning"}
ALLOWED_EXC = {"超时", "空", "非法JSON", "截断", "无"}


def log_path(root: Path) -> Path:
    return root / "cost_log.md"


def append_record(root: Path, line: str):
    p = log_path(root)
    with p.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def cmd_add(root: Path, target: str, tier: str, cost: str, result: str, exc: str = "无"):
    if tier not in ALLOWED_TIERS:
        print(f"[cost_log] 非法档位 {tier}，可选：{sorted(ALLOWED_TIERS)}", file=sys.stderr)
        sys.exit(1)
    if exc not in ALLOWED_EXC:
        print(f"[cost_log] 非法异常类型 {exc}，可选：{sorted(ALLOWED_EXC)}", file=sys.stderr)
        sys.exit(1)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts}|{target}|{tier}|{cost}|{result}|{exc}"
    append_record(root, line)
    print(f"[cost_log] 已记账：{line}")


def cmd_summary(root: Path):
    p = log_path(root)
    if not p.exists():
        print("[cost_log] 无成本记录（cost_log.md 不存在）")
        return
    lines = [l.strip() for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    print(f"[cost_log] 共 {len(lines)} 条记录")
    bad = [l for l in lines if len(l.split("|")) < 6 or l.split("|")[-1] in ("", " ")]
    if bad:
        print(f"  ⚠ {len(bad)} 条不合规（缺异常类型列或为空，rule 53）：")
        for b in bad[:10]:
            print(f"    {b}")
    # 按档位与结果简单聚合
    from collections import Counter
    tiers = Counter(l.split("|")[2] for l in lines if len(l.split("|")) >= 3)
    print(f"  档位分布：{dict(tiers)}")


def cmd_tail(root: Path, n: int = 10):
    p = log_path(root)
    if not p.exists():
        print("[cost_log] 无成本记录")
        return
    lines = [l.strip() for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    for l in lines[-n:]:
        print(l)


def _force_utf8_stdio():
    """stdio 加固（v3.16.0）：Windows 控制台默认 GBK，报告里的 ⚠ 会 UnicodeEncodeError
    直接崩掉输出（2026-09-12 实跑实测）。errors=replace 兜底——报告永不为编码问题静默失败。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def main():
    _force_utf8_stdio()
    args = sys.argv[1:]
    if len(args) < 2:
        print(__doc__)
        sys.exit(1)
    root = Path(args[0])
    if not root.is_dir():
        print(f"[cost_log] 目录不存在: {args[0]}", file=sys.stderr)
        sys.exit(2)
    cmd = args[1]
    rest = args[2:]
    if cmd == "add":
        if len(rest) < 4:
            print("[cost_log] add 需要: <对象> <档位> <预估成本> <结果> [异常类型]", file=sys.stderr)
            sys.exit(1)
        cmd_add(root, rest[0], rest[1], rest[2], rest[3], rest[4] if len(rest) > 4 else "无")
    elif cmd == "summary":
        cmd_summary(root)
    elif cmd == "tail":
        cmd_tail(root, int(rest[0]) if rest else 10)
    else:
        print(f"[cost_log] 未知命令 {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
