#!/usr/bin/env python3
"""runtime_probe.py — 运行时探针（rule 78 v3.16.0 扩展 · 所有脚本 Gate 的前置动作）

来源：2026-09-12 番茄宠物V2 实战——本机 PATH 指向**已被删除**的 node 版本目录，
`node` / `npm` 全不可用，构建/类型 Gate 必然失败；`py.exe` 启动器只列注册表条目、
不保证真能跑（G-001 v1.4）。按 rule 78：任何脚本 Gate 执行前先跑本探针，
探针失败 → 降级为"手写等价记录 + 标注未验证"，**禁止静默跳过**。

用法:
    python runtime_probe.py                      # 全部探针（人类可读）
    python runtime_probe.py --json               # 机器可读
    python runtime_probe.py --require node       # node 必需：不可用 → exit 1
    python runtime_probe.py --require node,python

输出（可 grep）:
    [PROBE] python=3.14.3 path=C:\\...\\python.exe source=self
    [PROBE] node=22.22.2-3 path=C:\\...\\node.exe source=fallback
    [PROBE] py_launcher=broken
    [PROBE] bash=ok|missing|blocked path=... version=...   # v3.21.0 三态（D-09/R-12）
    实测本机（2026-09-30）：**bash=ok**（`~/.workbuddy/binaries/PortableGit/.../bash.EXE` 在 PATH 上）
    —— 研讨期"本机 bash 被永久拦"的判断已被实测推翻，`.sh` 检查本机可正常跑。
    [PROBE] status=ok          # 或 status=degraded missing=node

探针策略（从廉到贵，绝对路径回退）:
    1. PATH 直接调用（shutil.which + 版本命令）
    2. 常见受管目录扫描（~/.workbuddy/binaries/node/versions/*/node.exe、nvm、Program Files\\nodejs）
    3. 全失败 → status=degraded + 打印可粘贴的降级命令（G-001 口径）

★ bash 三态（v3.21.0 · D-09 / R-12）——**blocked ≠ missing**，两者处置完全不同：
    ok      = 可用，`.sh` 检查正常跑
    missing = 本机**根本没有** bash → 显式标 `[不可测·环境缺失]`，记未验证（不记 PASS）
    blocked = **存在但跑不起来**（WSL 启动器无发行版 / 沙箱拦 / 占位可执行）→ **FAIL 级异常**，
              因为"看起来有 bash 却静默跳过"是永久逃逸口（R-12）

退出码: 0=所需项全可用 / 1=有必需项不可用
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


def _run(cmd: list, timeout: int = 10):
    """执行命令，返回 (stdout+stderr 首行, returncode)；异常返回 ("", -1)"""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        out = (r.stdout or r.stderr or "").strip().splitlines()
        return (out[0].strip() if out else ""), r.returncode
    except Exception:
        return "", -1


def _node_candidates():
    """受管/常见 node 安装目录（新→旧排序），yield Path"""
    home = Path.home()
    roots = [home / ".workbuddy" / "binaries" / "node" / "versions",
             home / "AppData" / "Roaming" / "nvm",
             Path("C:/nvm4w"),
             Path("C:/Program Files/nodejs"),
             Path("C:/Program Files (x86)/nodejs")]
    for base in roots:
        if not base.is_dir():
            continue
        if base.name in ("versions", "nvm", "nvm4w"):
            try:
                subs = sorted((d for d in base.iterdir() if d.is_dir()),
                              key=lambda d: d.name, reverse=True)
            except OSError:
                continue
            for d in subs:
                yield d
        else:
            yield base


def _probe_node() -> dict:
    exe = shutil.which("node")
    if exe:
        ver, rc = _run([exe, "--version"])
        if rc == 0 and ver:
            return {"ok": True, "version": ver.lstrip("v"), "path": exe, "source": "path"}
    binname = "node.exe" if os.name == "nt" else "node"
    for cand in _node_candidates():
        path = cand / binname
        if path.is_file():
            ver, rc = _run([str(path), "--version"])
            if rc == 0 and ver:
                return {"ok": True, "version": ver.lstrip("v"), "path": str(path),
                        "source": "fallback"}
    return {"ok": False, "version": None, "path": None, "source": "missing"}


def _probe_python() -> dict:
    return {"ok": True, "version": sys.version.split()[0], "path": sys.executable, "source": "self"}


def _probe_py_launcher() -> dict:
    """Windows py.exe 启动器：存在 ≠ 可用（G-001 实测：只列注册表条目）"""
    if os.name != "nt":
        return {"ok": False, "version": None, "path": None, "source": "n/a"}
    exe = shutil.which("py")
    if not exe:
        return {"ok": False, "version": None, "path": None, "source": "missing"}
    ver, rc = _run([exe, "-V"])
    if rc == 0 and ver:
        return {"ok": True, "version": ver, "path": exe, "source": "path"}
    return {"ok": False, "version": None, "path": exe, "source": "broken"}


def _try_bash(exe: str):
    """真实往返：跑 `bash -c "echo BASH_OK"`。返回 (ok, version)。

    与 `_probe_node` 同硬线：**只认真能跑**——存在、在 PATH 上、有 --version，都不算证据。
    """
    _, rc = _run([exe, "-c", "echo BASH_OK"], timeout=15)
    full = ""
    try:
        r = subprocess.run([exe, "-c", "echo BASH_OK"], capture_output=True, text=True,
                           timeout=15, encoding="utf-8", errors="replace")
        full = (r.stdout or "") + (r.stderr or "")
    except Exception:
        full = ""
    if rc == 0 and "BASH_OK" in full:
        ver, _ = _run([exe, "--version"])
        m = re.search(r"(\d+\.\d+(?:\.\d+)?)", ver or "")   # "GNU bash, version 5.2.26(1)" → 5.2.26
        return True, (m.group(1) if m else None)
    return False, None


def _bash_candidates():
    """受管 / 常见 Git-for-Windows bash 的**绝对路径**候选（新→旧），yield Path。

    为什么必须有候选回退（2026-10-15 实测，G-001 同族）：
      Windows 的 `shutil.which("bash")` 会先命中 `C:\\WINDOWS\\system32\\bash.exe`——
      那是 **WSL 启动器占位**：在 PATH 上，但本机无 WSL 发行版 → 跑不起来（blocked）。
      而本机实际存在**两个真 bash**（PortableGit 受管目录、Git for Windows 安装目录），
      只是不在 PATH 首位 → 不找回退就永远判 blocked（等于永久逃逸口，R-12）。
    """
    home = Path.home()
    pg = home / ".workbuddy" / "binaries" / "PortableGit"
    for base in (pg / "versions", pg):
        if not base.is_dir():
            continue
        if base.name == "versions":
            try:
                subs = sorted((d for d in base.iterdir() if d.is_dir()),
                              key=lambda d: d.name, reverse=True)
            except OSError:
                subs = []
            for d in subs:
                yield d / "bin" / "bash.exe"
        else:
            yield base / "bin" / "bash.exe"
    # 由 PATH 上的 git.exe 反推 Git for Windows 根：<root>/cmd/git.exe → <root>/bin/bash.exe
    git = shutil.which("git")
    if git:
        try:
            root = Path(git).resolve().parent.parent
            yield root / "bin" / "bash.exe"
            yield root / "usr" / "bin" / "bash.exe"
        except OSError:
            pass
    for p in ("C:/Program Files/Git/bin/bash.exe",
              "C:/Program Files (x86)/Git/bin/bash.exe"):
        yield Path(p)


def _probe_bash() -> dict:
    """bash 三态探针（v3.21.0 新增 · D-09 / R-12）。

    必须区分三态，因为它们**处置完全不同**：
      ok      —— 可用，`.sh` 检查正常跑
      missing —— 本机**根本没有** bash → 显式标 `[不可测·环境缺失]`（永久态，不掩盖、也不算 PASS）
      blocked —— **存在但跑不起来**（WSL 启动器无发行版 / 沙箱拦 / PATH 上有占位）→ 记 FAIL 级异常，
                 因为"看起来有 bash 却静默跳过"正是 R-12 要治的**永久逃逸口**。

    实测本机：`shutil.which('bash')` 能找到 Windows 的 WSL 启动器（`system32\\bash.exe`），
    但 `bash -c "echo BASH_OK"` 无输出 → **blocked**，不是 missing。

    2026-10-15 取新（本机实测）：`shutil.which("bash")` 命中的是 `C:\\WINDOWS\\system32\\bash.exe`
    （WSL 占位，**blocked**），但本机真 bash 有两个且可用（PortableGit 受管目录 / Git for Windows
    安装目录，GNU bash 5.3.15）→ 本探针改为 **PATH 优先 + 候选回退**，回退命中记 `source="fallback"`。
    三态语义不变：只有在 PATH 与全部候选**都跑不起来**时才是 blocked；**一个都没找到**才是 missing。
    """
    tried = []
    exe = shutil.which("bash")
    if exe:
        ok, ver = _try_bash(exe)
        if ok:
            return {"ok": True, "state": "ok", "path": exe, "version": ver, "source": "path"}
        tried.append(exe)
    for cand in _bash_candidates():
        sp = str(cand)
        if sp in tried:
            continue
        try:
            if not cand.is_file():
                continue
        except OSError:
            continue
        ok, ver = _try_bash(sp)
        if ok:
            return {"ok": True, "state": "ok", "path": sp, "version": ver,
                    "source": "fallback"}
        tried.append(sp)
    if tried:
        return {"ok": False, "state": "blocked", "path": tried[0], "version": None,
                "source": "blocked"}
    return {"ok": False, "state": "missing", "path": None, "version": None,
            "source": "missing"}


def probe_bash() -> dict:
    """公开入口：bash 三态探针的唯一实现（禁止各处自己 `shutil.which("bash")`——R-014：

    一处信息散落多边 = 漏改静默。`six_layer_check.py` 的 `.sh` 语法用例必须走本函数，
    否则"探针已支持候选回退、用例却仍只认 PATH"会形成新的静默分叉。
    """
    return _probe_bash()


def probe() -> dict:
    p = {"python": _probe_python(), "node": _probe_node(),
         "py_launcher": _probe_py_launcher(), "bash": _probe_bash()}
    p["status"] = "ok" if p["node"]["ok"] else "degraded"
    return p


def render(p: dict) -> str:
    lines = [f"[PROBE] python={p['python']['version']} path={p['python']['path']} "
             f"source={p['python']['source']}"]
    n = p["node"]
    if n["ok"]:
        lines.append(f"[PROBE] node={n['version']} path={n['path']} source={n['source']}")
    else:
        lines.append("[PROBE] node=missing path=- source=-")
    pl = p["py_launcher"]
    if pl["source"] in ("broken", "missing"):
        lines.append(f"[PROBE] py_launcher={pl['source']}")
    b = p["bash"]
    lines.append(f"[PROBE] bash={b['state']} path={b['path'] or '-'} "
                 f"version={b['version'] or '-'} source={b.get('source', '-')}")
    if b["state"] == "ok" and b.get("source") == "fallback":
        lines.append("→ bash 取自候选回退：PATH 上的 bash 是坏入口（WSL 占位 / 沙箱拦），"
                     "本次用真 bash 跑（G-001 同族：PATH 指向坏入口）")
    elif b["state"] == "missing":
        lines.append("→ bash=missing：本机**不存在** bash → `.sh` 检查显式标 `[不可测·环境缺失]`"
                     "（D-09：不存在≠跳过，记未验证，不记 PASS）")
    elif b["state"] == "blocked":
        lines.append("→ bash=blocked：bash **存在但跑不起来**（WSL 无发行版 / 沙箱拦 / 占位可执行）"
                     "→ 按 R-12 记 **FAIL 级异常**，不许静默跳过（'存在却跳过'= 永久逃逸口）")
    lines.append(f"[PROBE] status={p['status']}" + ("" if n["ok"] else " missing=node"))
    if not n["ok"]:
        lines.append("→ 降级（rule 78）：本机 node 不可用——该脚本 Gate 改为手写等价记录 + 标注未验证，"
                     "禁止静默跳过")
        lines.append("→ 修复：把受管 node 目录前置到 PATH 再执行 Gate（G-001 口径）：")
        lines.append("   $nd='<受管node目录>'; $env:PATH=\"$nd;$env:PATH\"   # PowerShell")
        cands = "; ".join(str(c) for c in _node_candidates())
        lines.append("→ node 候选目录：" + (cands or "(未找到候选)"))
    return "\n".join(lines)


def main() -> int:
    for stream in (sys.stdout, sys.stderr):   # Windows GBK 控制台防 UnicodeEncodeError
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--require", default="", help="必需项，逗号分隔：node,python")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("-h", "--help", action="store_true")
    args, _ = ap.parse_known_args()
    if args.help:
        print(__doc__)
        return 0
    p = probe()
    print(json.dumps(p, ensure_ascii=False, indent=2) if args.json else render(p))
    required = [x.strip() for x in args.require.split(",") if x.strip()]
    missing = [r for r in required if not (p.get(r) or {}).get("ok")]
    if missing:
        print(f"[PROBE] status=blocked require_missing={','.join(missing)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
