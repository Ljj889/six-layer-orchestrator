"""lifecycle.py — 项目生命周期状态机硬拦截（rule 63 · 框架对齐 v3.16.0；自 v3.9.13 起）

五态：INIT → EXECUTING → DELIVERED → (REOPENED | ACCEPTED)
转移表（非法转移一律拒绝 + 审计记录）：
    INIT       → EXECUTING   （Phase 0 完成，开始执行）
    EXECUTING  → DELIVERED   （Phase 5 交付）★ Gate：需 evidence 通过
    DELIVERED  → REOPENED    （用户反馈修改）
    DELIVERED  → ACCEPTED    （用户验收通过）★ Gate：需用户确认记录
    REOPENED   → EXECUTING   （新一轮修改执行）
    REOPENED   → ACCEPTED    （用户验收通过）★ Gate：需用户确认记录
    ACCEPTED   → INIT        （新迭代，重新 Phase -2）

★ Gate 证据门（rule 63/51 引擎化）：
    - EXECUTING → DELIVERED：--evidence 必须为 six_layer_check deliver 模式（或手动确认的
      未验证项清单已存在）；此处用 --evidence-file <未验证项清单路径> 作为硬证据。
    - DELIVERED/REOPENED → ACCEPTED：--evidence 必须为 <用户确认文件>（如验收报告、
      ACCEPTED.md），证明用户明确说"完成/没问题/验收通过"。

说明：脚本能硬约束的是"状态转移合法性 + 证据"，不能拦"调度器改代码"的行为本身——
那靠 Red Flag（rule 63 调度器直改 FAIL）+ 审计记录兜底。

用法：
    python lifecycle.py <项目目录> get                         查看当前状态
    python lifecycle.py <项目目录> transit <目标状态> [--evidence-file <路径>]  执行转移
    python lifecycle.py <项目目录> history                     查看审计历史

退出码：0=成功 / 1=非法转移或证据缺失 / 2=目录不存在
"""
import json
import sys
from datetime import datetime
from pathlib import Path

VALID_STATES = {"INIT", "EXECUTING", "DELIVERED", "REOPENED", "ACCEPTED"}

# 合法转移表
TRANSITIONS = {
    "INIT": {"EXECUTING"},
    "EXECUTING": {"DELIVERED"},
    "DELIVERED": {"REOPENED", "ACCEPTED"},
    "REOPENED": {"EXECUTING", "ACCEPTED"},
    "ACCEPTED": {"INIT"},
}

# 需要证据门的转移：目标状态 -> (证据说明)
GATED = {
    "DELIVERED": "需提供未验证项清单（--evidence-file），证明 rule 42/51 已核对",
    "ACCEPTED": "需提供用户确认记录文件（--evidence-file），证明用户已验收（rule 63 验收权归用户）",
}


def state_path(root: Path) -> Path:
    return root / "progress.json"


def load_state(root: Path) -> dict:
    p = state_path(root)
    if p.exists():
        data = json.loads(p.read_text(encoding="utf-8"))
        data.setdefault("lifecycle", "INIT")
        data.setdefault("lifecycle_history", [])
        return data
    return {"lifecycle": "INIT", "lifecycle_history": []}


def save_state(root: Path, data: dict):
    p = state_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def audit(data: dict, event: str):
    data.setdefault("lifecycle_history", []).append(
        f"{datetime.now().isoformat(timespec='seconds')} {event}"
    )


def cmd_get(root: Path):
    data = load_state(root)
    print(f"[lifecycle] {root}  当前状态: {data['lifecycle']}")
    hist = data.get("lifecycle_history") or []
    if hist:
        print("  审计历史（最近 10 条）：")
        for h in hist[-10:]:
            print(f"    {h}")


def cmd_transit(root: Path, target: str, evidence_file: str = None):
    target = target.upper()
    if target not in VALID_STATES:
        print(f"[lifecycle] 非法状态 {target}，可选：{sorted(VALID_STATES)}", file=sys.stderr)
        sys.exit(1)
    data = load_state(root)
    current = data["lifecycle"]
    if target not in TRANSITIONS.get(current, set()):
        print(f"[lifecycle] ✗ 非法转移 {current} -> {target}（rule 63 状态机），拒绝执行", file=sys.stderr)
        audit(data, f"REJECT {current}->{target} (非法转移)")
        save_state(root, data)
        sys.exit(1)
    # Gate 证据门
    if target in GATED:
        if not evidence_file or not Path(evidence_file).exists():
            print(f"[lifecycle] ✗ 转移 {current}->{target} 证据缺失：{GATED[target]}", file=sys.stderr)
            audit(data, f"REJECT {current}->{target} (证据缺失)")
            save_state(root, data)
            sys.exit(1)
    data["lifecycle"] = target
    audit(data, f"TRANSIT {current}->{target}" + (f" (evidence={Path(evidence_file).name})" if evidence_file else ""))
    save_state(root, data)
    print(f"[lifecycle] ✓ {current} -> {target}")
    if target == "DELIVERED":
        print("  提醒：DELIVERED 状态下调度器禁止直改任何代码（rule 63），修改一律走 Phase 6 路由子 Agent")


def cmd_history(root: Path):
    data = load_state(root)
    hist = data.get("lifecycle_history") or []
    print(f"[lifecycle] 审计历史共 {len(hist)} 条")
    for h in hist:
        print(f"  {h}")


def _force_utf8_stdio():
    """stdio 加固（v3.16.0）：Windows 控制台默认 GBK，报告里的 ✓/✗ 会 UnicodeEncodeError
    直接崩掉输出（2026-09-12 实跑实测：transit 成功路径必崩）。errors=replace 兜底。"""
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
        print(f"[lifecycle] 目录不存在: {args[0]}", file=sys.stderr)
        sys.exit(2)
    cmd = args[1]
    rest = args[2:]
    # 解析 --evidence-file <path>
    evidence = None
    filtered = []
    i = 0
    while i < len(rest):
        if rest[i] == "--evidence-file":
            if i + 1 < len(rest):
                evidence = rest[i + 1]
                i += 2
                continue
            else:
                print("[lifecycle] --evidence-file 缺少值", file=sys.stderr)
                sys.exit(1)
        filtered.append(rest[i])
        i += 1
    if cmd == "get":
        cmd_get(root)
    elif cmd == "transit" and filtered:
        cmd_transit(root, filtered[0], evidence)
    elif cmd == "history":
        cmd_history(root)
    else:
        print(f"[lifecycle] 用法错误：{cmd} {rest}", file=sys.stderr)
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
