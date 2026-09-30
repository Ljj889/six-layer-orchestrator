# -*- coding: utf-8 -*-
"""扫描员 A · 补测：最新/首次发版日期 + any-llm-sdk 等包名核对。"""
import json
import urllib.request

PKGS = ["any-llm-sdk", "sseclient-py", "durable-rules", "simpleeval", "json-repair",
        "litellm", "openai", "instructor", "jsonschema", "pydantic", "tiktoken",
        "aisuite", "httpx-sse", "fastjsonschema", "stamina"]

UA = {"User-Agent": "scan-a/1.0"}


def fetch(pkg):
    url = "https://pypi.org/pypi/%s/json" % pkg
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


for pkg in PKGS:
    try:
        d = fetch(pkg)
    except Exception as e:
        print("== %s == ❓ %r" % (pkg, e))
        continue
    info = d["info"]
    # 收集所有文件上传时间
    times = []
    for ver, files in (d.get("releases") or {}).items():
        for f in files:
            t = f.get("upload_time_iso_8601") or f.get("upload_time")
            if t:
                times.append((t, ver))
    times.sort()
    latest_ver = info.get("version")
    latest_t = None
    for t, v in reversed(times):
        if v == latest_ver:
            latest_t = t
            break
    print("== %s ==" % pkg)
    print("  version    : %s" % latest_ver)
    print("  latest_up  : %s" % latest_t)
    print("  first_up   : %s" % (times[0][0] if times else None))
    print("  n_releases : %d" % len(set(v for _, v in times)))
    print("  license    : %r | expr=%r" % ((info.get("license") or "")[:60], info.get("license_expression") or ""))
    print()
