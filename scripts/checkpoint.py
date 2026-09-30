"""checkpoint.py — 断点三态管理（rule 39 · 框架对齐 v3.16.0；引擎自 v3.9.13 起）

来源：编排系统项目 checkpoint_manager.py 按框架语义适配（2026-09-01）。
与 rule 39 对齐：状态三态（已交付/已验证/未验证）+ 派发前"预期产物清单"（pending）。
产物写 progress.json（与 lifecycle.py 共用，字段：modules / expected_products / lifecycle）。

用法：
    python checkpoint.py <项目目录> status                        查看三态与预期产物
    python checkpoint.py <项目目录> expect <wave名> <模块id> <文件...>  派发前写预期产物清单
    python checkpoint.py <项目目录> mark <模块id> <delivered|verified|unverified>  标记三态
    python checkpoint.py <项目目录> verify <模块id> <文件...>     磁盘核验（stat 存在且非空）

退出码：0=成功 / 1=参数或校验失败 / 2=目录不存在
"""
import copy
import json
import os
import sys
from pathlib import Path

STATUS_MAP = {"delivered": "已交付", "verified": "已验证", "unverified": "未验证"}
DEFAULT_STATE = {
    "modules": {},
    "expected_products": [],
    "lifecycle": "INIT",
}


def load_state(root: Path) -> dict:
    """读 progress.json。★ 必须深拷贝（v3.21.0 修）：
    原实现 `return dict(DEFAULT_STATE)` 是**浅拷贝**——外层 dict 是新的，但内层
    `modules` / `expected_products` 仍是 DEFAULT_STATE 里**同一个可变对象**；
    同进程连续处理两个项目时，A 项目写入的模块会"串"到 B 项目的初始状态里。
    同理 `data.setdefault(k, v)` 也会把 DEFAULT_STATE 的内层对象直接挂进 data。
    """
    path = root / "progress.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        for k, v in DEFAULT_STATE.items():
            if k not in data:
                data[k] = copy.deepcopy(v)
        return data
    return copy.deepcopy(DEFAULT_STATE)


def save_state(root: Path, data: dict):
    """★ 原子写（v3.21.0 修）：原 `write_text` 直写目标文件，
    `load→改→全量 save` 在多窗口并发下会互相覆盖（丢更新）；
    且进程被中断会留下半截 JSON。改用 同目录临时文件 + os.replace 原子替换。"""
    path = root / "progress.json"
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def cmd_status(root: Path):
    state = load_state(root)
    lines = [f"[checkpoint] {root}  lifecycle={state['lifecycle']}"]
    modules = state.get("modules") or {}
    if not modules:
        lines.append("  无模块记录（尚未 mark 任何模块）")
    for mid, m in modules.items():
        lines.append(f"  {m.get('status', '未验证'):4s} {mid}")
    expected = state.get("expected_products") or []
    if expected:
        lines.append("  预期产物清单：")
        for e in expected:
            files = ",".join(e.get("files", []))
            lines.append(f"    [{e.get('status', 'pending')}] {e.get('wave', '?')} {e.get('module', '?')} -> {files}")
    print("\n".join(lines))


def cmd_expect(root: Path, wave: str, module_id: str, files: list):
    state = load_state(root)
    entry = {"wave": wave, "module": module_id, "files": files, "status": "pending"}
    state.setdefault("expected_products", []).append(entry)
    save_state(root, state)
    print(f"[checkpoint] 已记录预期产物：Wave {wave} {module_id} -> {len(files)} 个文件（pending）")


def cmd_mark(root: Path, module_id: str, status_key: str):
    if status_key not in STATUS_MAP:
        print(f"[checkpoint] 非法状态 {status_key}，可选：{list(STATUS_MAP)}", file=sys.stderr)
        sys.exit(1)
    state = load_state(root)
    state.setdefault("modules", {})[module_id] = {
        "status": STATUS_MAP[status_key],
        "updated": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
    }
    save_state(root, state)
    print(f"[checkpoint] {module_id} -> {STATUS_MAP[status_key]}")


def cmd_verify(root: Path, module_id: str, files: list):
    state = load_state(root)
    missing = []
    for f in files:
        p = root / f
        if not (p.exists() and p.stat().st_size > 0):
            missing.append(f)
    if missing:
        print(f"[checkpoint] ✗ {module_id} 磁盘核验失败，缺失/为空：{missing}", file=sys.stderr)
        # 未验证状态记录
        state.setdefault("modules", {}).setdefault(module_id, {})["status"] = "未验证"
        save_state(root, state)
        sys.exit(1)
    state.setdefault("modules", {})[module_id] = {
        "status": "已验证",
        "updated": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
    }
    save_state(root, state)
    print(f"[checkpoint] ✓ {module_id} 磁盘核验通过（stat 存在且非空）")


def _force_utf8_stdio():
    """stdio 加固（v3.16.0）：Windows 控制台默认 GBK，报告里的 ✓/✗/⚠ 会 UnicodeEncodeError
    直接崩掉输出（2026-09-12 实跑实测）。errors=replace 兜底——报告永不为编码问题静默失败。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def main():
    _force_utf8_stdio()
    args = [a for a in sys.argv[1:]]
    if len(args) < 2:
        print(__doc__)
        sys.exit(1)
    project_dir, cmd = args[0], args[1]
    root = Path(project_dir)
    if not root.is_dir():
        print(f"[checkpoint] 目录不存在: {project_dir}", file=sys.stderr)
        sys.exit(2)
    rest = args[2:]
    if cmd == "status":
        cmd_status(root)
    elif cmd == "expect" and len(rest) >= 2:
        cmd_expect(root, rest[0], rest[1], rest[2:])
    elif cmd == "mark" and len(rest) >= 2:
        cmd_mark(root, rest[0], rest[1])
    elif cmd == "verify" and len(rest) >= 1:
        cmd_verify(root, rest[0], rest[1:])
    else:
        print(f"[checkpoint] 未知命令或参数不足: {cmd} {rest}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
