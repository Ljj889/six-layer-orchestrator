"""cost_log.py — 成本账本定长行管理（rule 38/53 · 框架对齐 v3.17.0 · 引擎自 v3.9.13 起）

来源：编排系统项目 cost_tracker.py 按框架语义适配（2026-09-01）。
与 rule 38/53 对齐：每次派发追加一行定长记录（可 grep）：
    [时间]|[派发对象]|[档位 lite/default/reasoning]|[预估成本]|[结果 成功/失败/时长]|[异常类型: 超时/空/非法JSON/截断/无]
    [可选第7列 错位类型 T1/T2/T3/T4/无]|[可选第8列 任务卡行数]|[可选第9列 档位误判 高/低/无]
缺第 6 列异常类型或为空值 = 记录不合规（rule 53）。后 3 列为 v3.17.0 可选扩展（三车共用：记忆取证 T1-T4 / 注入预算 / 档位误判，向后兼容旧 6 列行）。

用法：
    python cost_log.py <项目目录> add <对象> <档位> <预估成本> <结果> [异常类型] [错位类型] [任务卡行数] [档位误判]
    python cost_log.py <项目目录> summary    汇总（含不合规检查）
    python cost_log.py <项目目录> audit      基线首跑（只输出分布+超时交叉表+实锤检测，不改判）
    python cost_log.py <项目目录> tail       查看最近 N 行（默认 10）

实锤判定式（rule 64 引擎化，随本文件写死，见 cmd_audit）：
    audit 升档实锤 = 同档位行 异常类型=超时 连续 >=2 行
    档位过高疑似 = reasoning 档 异常类型全为"无"（成功率 100%）且 reasoning 行占比 >40%
    打标实锤    = 第7列错位类型 非空且 != "无"
    样本不足    = 总记录 <3 条（只输出分布，不做判定）
退出码：0=成功 / 1=参数或校验失败 / 2=目录不存在
"""
import sys
from datetime import datetime
from pathlib import Path

ALLOWED_TIERS = {"lite", "default", "reasoning"}
ALLOWED_EXC = {"超时", "空", "非法JSON", "截断", "无"}
# v3.17.0 可选列枚举（三车共用：记忆取证 / 注入预算 / 档位误判）
ALLOWED_MISALIGN = {"T1", "T2", "T3", "T4", "无"}   # 错位类型（记忆取证打标）
ALLOWED_MISJUDGE = {"高", "低", "无"}               # 档位误判标记


def log_path(root: Path) -> Path:
    return root / "cost_log.md"


def append_record(root: Path, line: str):
    p = log_path(root)
    with p.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def cmd_add(root: Path, target: str, tier: str, cost: str, result: str,
            exc: str = "无", misalign: str = "", card_lines: str = "", misjudge: str = ""):
    if tier not in ALLOWED_TIERS:
        print(f"[cost_log] 非法档位 {tier}，可选：{sorted(ALLOWED_TIERS)}", file=sys.stderr)
        sys.exit(1)
    if exc not in ALLOWED_EXC:
        print(f"[cost_log] 非法异常类型 {exc}，可选：{sorted(ALLOWED_EXC)}", file=sys.stderr)
        sys.exit(1)
    if misalign and misalign not in ALLOWED_MISALIGN:
        print(f"[cost_log] 非法错位类型 {misalign}，可选：{sorted(ALLOWED_MISALIGN)}", file=sys.stderr)
        sys.exit(1)
    if misjudge and misjudge not in ALLOWED_MISJUDGE:
        print(f"[cost_log] 非法档位误判标记 {misjudge}，可选：{sorted(ALLOWED_MISJUDGE)}", file=sys.stderr)
        sys.exit(1)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts}|{target}|{tier}|{cost}|{result}|{exc}"
    # v3.17.0 可选列：仅当任一非空时追加，向后兼容旧 6 列行
    if misalign or card_lines or misjudge:
        line += f"|{misalign or '无'}|{card_lines}|{misjudge or '无'}"
    append_record(root, line)
    print(f"[cost_log] 已记账：{line}")


def _rows(root: Path):
    p = log_path(root)
    if not p.exists():
        return []
    return [l.strip() for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def cmd_summary(root: Path):
    lines = _rows(root)
    if not lines:
        print("[cost_log] 无成本记录（cost_log.md 不存在或为空）")
        return
    print(f"[cost_log] 共 {len(lines)} 条记录")
    bad = [l for l in lines if len(l.split("|")) < 6 or l.split("|")[5] in ("", " ")]
    if bad:
        print(f"  ⚠ {len(bad)} 条不合规（缺异常类型列或为空，rule 53）：")
        for b in bad[:10]:
            print(f"    {b}")
    from collections import Counter
    tiers = Counter(l.split("|")[2] for l in lines if len(l.split("|")) >= 3)
    print(f"  档位分布：{dict(tiers)}")


def cmd_audit(root: Path):
    """基线首跑（v3.17.0 · rule 47 audit）：只输出现状分布 + 超时-档位交叉表 + 实锤检测，不改判。
    实锤判定式写死于此（rule 64）：改判逻辑归 rule 47 判定表，本命令只取证报告。"""
    lines = _rows(root)
    if not lines:
        print("[cost_log] 无成本记录（cost_log.md 不存在或为空）")
        return
    from collections import Counter
    total = len(lines)
    tiers = Counter(l.split("|")[2] for l in lines if len(l.split("|")) >= 3)
    print(f"[audit] 共 {total} 条记录")
    print(f"[audit] 档位分布：{dict(tiers)}")

    # 超时-档位交叉表
    timeout_by_tier = Counter()
    for l in lines:
        parts = l.split("|")
        if len(parts) >= 6 and parts[5] == "超时":
            timeout_by_tier[parts[2]] += 1
    if timeout_by_tier:
        print(f"[audit] 超时-档位交叉表：{dict(timeout_by_tier)}")
    else:
        print("[audit] 无超时记录")

    # 样本不足（Wave<3 条记录不硬判）
    if total < 3:
        print("[audit] 样本不足（<3 条记录），不做档位/实锤判定，仅输出分布")
        return

    # 实锤 1：audit 升档实锤 = 同档位 异常类型=超时 连续 >=2 行
    cont = {}
    max_cont = {}
    for l in lines:
        parts = l.split("|")
        if len(parts) < 6:
            continue
        tier, exc = parts[2], parts[5]
        cont[tier] = (cont.get(tier, 0) + 1) if exc == "超时" else 0
        max_cont[tier] = max(max_cont.get(tier, 0), cont[tier])
    for tier, cnt in max_cont.items():
        if cnt >= 2:
            print(f"[audit][实锤·升档] {tier} 档 连续 {cnt} 次超时 → 疑似档位过低（基线首跑仅报告，改判归 rule 47 判定表）")

    # 实锤 2：档位过高疑似 = reasoning 异常类型全"无" 且占比 >40%
    reasoning_rows = [l.split("|") for l in lines if len(l.split("|")) >= 6 and l.split("|")[2] == "reasoning"]
    if reasoning_rows:
        reasoning_clean = all(r[5] == "无" for r in reasoning_rows)
        reasoning_ratio = len(reasoning_rows) / total
        if reasoning_clean and reasoning_ratio > 0.4:
            print(f"[audit][疑似过高] reasoning 成功率 100% 且占比 {reasoning_ratio:.0%} > 40% → 疑似档位过高（仅报告）")

    # 实锤 3：打标实锤 = 第7列错位类型 非空且 != "无"
    misalign = Counter()
    for l in lines:
        parts = l.split("|")
        if len(parts) >= 7 and parts[6] and parts[6] != "无":
            misalign[parts[6]] += 1
    if misalign:
        print(f"[audit][实锤·记忆错位] 打标分布：{dict(misalign)}（T1-T4 非空即实锤）")
    else:
        print("[audit] 错位类型打标：无实锤（第7列空或全为'无'）")


def cmd_tail(root: Path, n: int = 10):
    lines = _rows(root)
    if not lines:
        print("[cost_log] 无成本记录")
        return
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
            print("[cost_log] add 需要: <对象> <档位> <预估成本> <结果> [异常类型] [错位类型] [任务卡行数] [档位误判]", file=sys.stderr)
            sys.exit(1)
        cmd_add(root, rest[0], rest[1], rest[2], rest[3],
                rest[4] if len(rest) > 4 else "无",
                rest[5] if len(rest) > 5 else "",
                rest[6] if len(rest) > 6 else "",
                rest[7] if len(rest) > 7 else "")
    elif cmd == "summary":
        cmd_summary(root)
    elif cmd == "audit":
        cmd_audit(root)
    elif cmd == "tail":
        cmd_tail(root, int(rest[0]) if rest else 10)
    else:
        print(f"[cost_log] 未知命令 {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
