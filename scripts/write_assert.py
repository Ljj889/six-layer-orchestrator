#!/usr/bin/env python3
"""write_assert.py — 写入/搬运类产物断言（rule 79 产物断言家族**第三类** · D-05 · L1a）

前两类是"产物**内容**断言"（Tier A/B）。**第三类管"搬运 / 写入 / 落位"**：
代码把产物写到最终位置之后，**按最终位置的字节数 + 位置逐项回读**，而不是只看返回值 / 只看大小。

★ 为什么必须逐项回读最终位置（伴学 P0 实战）：
   真机上 `java.nio.Files.copy(Path,Path)` 经 `plus.android` **不报错，但产出 0 字节**；
   同族还有"暂存路径少个斜杠 → 文件名叫错，而大小校验照样通过"——**两个静默假绿**。

★ 0 字节的三种语义（**必须区分，不许一律当失败/一律当通过**）：
    src 空 + dst 空 → **SKIP**（源头本来就是空的，不是写入失败）
    src 非空 + dst 空 → **FAIL**（这就是"copy 不报错却产出 0 字节"）
    dst 不存在       → **FAIL**

★ 降级计数器（D-05）：连续 N 次（默认 3）"拿不到字节"→ FAIL；
   但判"**逃逸 vs 环境缺失**"之前**先跑能力探针** —— 本机永久缺失的读能力
   → 显式标 `[不可测·环境缺失]`，**不占计数器**（防 R-12 的永久逃逸口）。

声明文件 `write-assert.json`（放项目根或 --decl 指定）：
    [
      {"src": "tmp/stage/a.png", "dst": "out/final/a.png"},     # src 可选
      {"dst": "out/final/b.mp4"}                                 # 只断言存在且非空
    ]

用法：
    python scripts/write_assert.py <项目目录> [--decl write-assert.json] [--strict] [--json]

退出码：0=PASS（可有 SKIP）/ 1=FAIL / 2=无声明文件或目录不存在
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

DEFAULT_DECL = "write-assert.json"
SKIP_LIMIT = 3          # 连续跳过后升 FAIL 的阈值（D-05 降级计数器）
_COUNTER_FILE = ".write-assert.skip-streak"


def _utf8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _probe_read_capability(root: Path) -> dict:
    """能力探针：本机"能不能读文件字节"。返回 {ok, reason}。
    永久缺失（如目录不可读）→ 标 [不可测·环境缺失]，不占降级计数器。"""
    try:
        probe = root / ".write-assert.probe"
        probe.write_bytes(b"x")
        ok = probe.read_bytes() == b"x"
        probe.unlink()
        return {"ok": bool(ok), "reason": "" if ok else "读回字节失败"}
    except Exception as e:
        return {"ok": False, "reason": f"{type(e).__name__}: {e}"}


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def check_one(root: Path, item: dict) -> dict:
    """逐项回读最终位置。返回 {name, status: PASS|FAIL|SKIP, detail}"""
    dst_rel = str(item.get("dst") or "").strip()
    if not dst_rel:
        return {"name": "<missing dst>", "status": "FAIL", "detail": "声明缺少 dst 字段"}
    dst = root / dst_rel
    if not dst.exists():
        return {"name": dst_rel, "status": "FAIL", "detail": "最终位置不存在（未落位）"}
    dst_size = dst.stat().st_size
    src_rel = str(item.get("src") or "").strip()
    src = (root / src_rel) if src_rel else None

    if dst_size == 0:
        if src is not None and src.exists() and src.stat().st_size == 0:
            return {"name": dst_rel, "status": "SKIP",
                    "detail": "src 与 dst 均为 0 字节（源头本来就空，非写入失败）"}
        return {"name": dst_rel, "status": "FAIL",
                "detail": "最终位置 0 字节而源非空 —— 典型『copy 不报错却产出 0 字节』静默假绿"}

    if src is not None and src.exists():
        if _sha(src) != _sha(dst):
            return {"name": dst_rel, "status": "FAIL",
                    "detail": f"字节不一致（src={src.stat().st_size}B dst={dst_size}B，sha256 不同）"}
        return {"name": dst_rel, "status": "PASS",
                "detail": f"{dst_size}B · sha256 与源一致（按最终位置回读）"}
    return {"name": dst_rel, "status": "PASS",
            "detail": f"{dst_size}B · 存在且非空（未给 src，不做内容比对）"}


def run(root: Path, decl_name: str, strict: bool) -> int:
    decl = root / decl_name
    if not decl.exists():
        print(f"[write-assert] 无声明文件 {decl}（非前端/无搬运场景可忽略）", file=sys.stderr)
        return 2
    try:
        items = json.loads(decl.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[write-assert] 声明文件解析失败: {e}", file=sys.stderr)
        return 2
    if not isinstance(items, list) or not items:
        print("[write-assert] 声明必须是非空数组", file=sys.stderr)
        return 2

    cap = _probe_read_capability(root)
    results = []
    for it in items:
        if not cap["ok"]:
            results.append({"name": str(it.get("dst")), "status": "SKIP",
                            "detail": f"[不可测·环境缺失] 能力探针失败：{cap['reason']}"
                                      "（不占降级计数器）"})
            continue
        results.append(check_one(root, it))

    n_fail = sum(1 for r in results if r["status"] == "FAIL")
    n_skip = sum(1 for r in results if r["status"] == "SKIP")

    # 降级计数器（只统计"环境具备但拿不到字节"的跳过；环境缺失不占）
    counter_file = root / _COUNTER_FILE
    streak = 0
    if counter_file.exists():
        try:
            streak = int(counter_file.read_text(encoding="utf-8").strip() or "0")
        except Exception:
            streak = 0
    env_missing_only = cap["ok"] is False
    if n_skip > 0 and not env_missing_only:
        streak += 1
    else:
        streak = 0
    try:
        counter_file.write_text(str(streak), encoding="utf-8")
    except Exception:
        pass
    counter_tripped = streak >= SKIP_LIMIT

    print(f"[write-assert] {root} 声明={decl_name} 项={len(results)} "
          f"PASS={sum(1 for r in results if r['status'] == 'PASS')} FAIL={n_fail} SKIP={n_skip}")
    for r in results:
        mark = {"PASS": "✓", "FAIL": "✗", "SKIP": "-"}[r["status"]]
        print(f"  {mark} [{r['status']}] {r['name']}  ({r['detail']})")
    print(f"[write-assert] 降级计数器 streak={streak}/{SKIP_LIMIT}"
          + ("（**已超限 → FAIL**）" if counter_tripped else "")
          + ("  · 能力探针=" + ("ok" if cap["ok"] else f"缺失({cap['reason']})")))
    print("[write-assert] 它不保证什么：只验『最终位置的字节』，不验内容语义/权限/后续是否被覆盖")
    if counter_tripped:
        print(f"[write-assert] FAIL：连续跳过超限（streak={streak}）—— 「跳过」已成常态逃逸口（D-05）",
              file=sys.stderr)
        return 1
    bad = n_fail + (n_skip if strict else 0)
    return 1 if bad else 0


def main_with_argv(root: Path, extra: list, strict: bool = False) -> int:
    decl = DEFAULT_DECL
    for a in extra:
        if a.startswith("--decl="):
            decl = a.split("=", 1)[1]
    return run(root, decl, strict)


def main() -> int:
    _utf8()
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--decl", default=DEFAULT_DECL)
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("-h", "--help", action="store_true")
    args, rest = ap.parse_known_args()
    if args.help or not rest:
        print(__doc__)
        return 0 if args.help else 2
    root = Path(rest[0])
    if not root.is_dir():
        print(f"[write-assert] 目录不存在: {root}", file=sys.stderr)
        return 2
    return run(root, args.decl, args.strict)


if __name__ == "__main__":
    sys.exit(main())
