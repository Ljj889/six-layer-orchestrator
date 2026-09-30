#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫描员B：计算 PyPI 包的「默认安装」传递依赖闭包大小（排除 extras）。
用法: python dep_closure.py <pkg> [<pkg> ...]
说明：只统计 base 依赖（跳过带 `extra ==` 标记的行），递归解析。
"""
import json, re, sys, urllib.request, urllib.error, time

CACHE = {}

def fetch(pkg):
    pkg = pkg.lower().replace("_", "-")
    if pkg in CACHE:
        return CACHE[pkg]
    url = f"https://pypi.org/pypi/{pkg}/json"
    try:
        with urllib.request.urlopen(url, timeout=25) as r:
            d = json.load(r)
    except Exception as e:
        CACHE[pkg] = ("ERR:" + str(e)[:60], None, None)
        return CACHE[pkg]
    info = d["info"]
    up = d.get("urls") or []
    date = up[0]["upload_time"][:10] if up else "?"
    CACHE[pkg] = (None, info, date)
    return CACHE[pkg]


def dep_names(requires_dist):
    """把 requires_dist 拆成 (name, is_extra_guarded)"""
    out = []
    if not requires_dist:
        return out
    for spec in requires_dist:
        if not spec:
            continue
        # 去掉环境标记
        parts = spec.split(";", 1)
        core = parts[0].strip()
        marker = parts[1] if len(parts) > 1 else ""
        if "extra ==" in marker:
            continue  # 可选 extra，默认不装
        # 取包名
        m = re.match(r"^([A-Za-z0-9_.\-]+)", core)
        if not m:
            continue
        out.append(m.group(1).lower().replace("_", "-"))
    return out


def closure(root):
    seen = set()
    order = []
    queue = [root.lower().replace("_", "-")]
    errs = []
    while queue:
        p = queue.pop(0)
        if p in seen:
            continue
        seen.add(p)
        order.append(p)
        err, info, _ = fetch(p)
        if err:
            errs.append(f"{p}({err})")
            continue
        for d in dep_names(info.get("requires_dist")):
            if d not in seen:
                queue.append(d)
        time.sleep(0.05)
    return seen, order, errs


if __name__ == "__main__":
    for pkg in sys.argv[1:]:
        seen, order, errs = closure(pkg)
        err, info, date = fetch(pkg)
        lic = None
        if not err:
            lic = info.get("license_expression") or (info.get("license") or "")[:40] or "❓"
        direct = len(dep_names(info.get("requires_dist"))) if not err else "?"
        print(f"### {pkg}")
        print(f"    需装包总数(含自身) : {len(seen)}")
        print(f"    直接依赖(base)    : {direct}")
        print(f"    license           : {lic}")
        print(f"    最新发版          : {date}")
        print(f"    闭包成员          : {', '.join(sorted(seen))[:900]}")
        if errs:
            print(f"    ⚠ 解析失败: {', '.join(errs[:8])}")
        print()
