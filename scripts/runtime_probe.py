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
    [PROBE] python=3.13.12 path=C:\\...\\python.exe source=self
    [PROBE] node=22.22.2-3 path=C:\\...\\node.exe source=fallback
    [PROBE] py_launcher=broken
    [PROBE] status=ok          # 或 status=degraded missing=node

探针策略（从廉到贵，绝对路径回退）:
    1. PATH 直接调用（shutil.which + 版本命令）
    2. 常见受管目录扫描（~/.workbuddy/binaries/node/versions/*/node.exe、nvm、Program Files\\nodejs）
    3. 全失败 → status=degraded + 打印可粘贴的降级命令（G-001 口径）

退出码: 0=所需项全可用 / 1=有必需项不可用
"""
from __future__ import annotations

import argparse
import json
import os
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


def probe() -> dict:
    p = {"python": _probe_python(), "node": _probe_node(), "py_launcher": _probe_py_launcher()}
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
