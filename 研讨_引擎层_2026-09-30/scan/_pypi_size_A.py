# -*- coding: utf-8 -*-
"""扫描员 A · 体积实测：取顶层 urls 里的 wheel/sdist 体积。"""
import json
import urllib.request

PKGS = ["litellm", "openai", "aisuite", "any-llm-sdk", "sseclient-py", "httpx-sse",
        "pydantic", "pydantic-core", "jsonschema", "rpds-py", "fastjsonschema",
        "instructor", "outlines", "json-repair", "tiktoken", "tokenizers",
        "simpleeval", "durable-rules", "tenacity"]

UA = {"User-Agent": "scan-a/1.0"}


def fetch(pkg):
    req = urllib.request.Request("https://pypi.org/pypi/%s/json" % pkg, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


for pkg in PKGS:
    try:
        d = fetch(pkg)
    except Exception as e:
        print("== %s == ❓ %r" % (pkg, e))
        continue
    urls = d.get("urls") or []
    print("== %s == ver=%s" % (pkg, d["info"].get("version")))
    for u in urls:
        fn = u.get("filename", "")
        pk = u.get("packagetype")
        # 只关心 win_amd64 wheel 与 py3-none-any wheel 与 sdist
        if "win_amd64" in fn or fn.endswith("py3-none-any.whl") or pk == "sdist":
            print("   %-70s %8.1f KB  (%s)" % (fn, (u.get("size") or 0) / 1024.0, pk))
    print()
