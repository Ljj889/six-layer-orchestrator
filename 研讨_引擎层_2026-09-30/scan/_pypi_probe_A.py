# -*- coding: utf-8 -*-
"""扫描员 A · PyPI 实测：license / license_expression / 运行期依赖 / 最新上传时间 / wheel 体积。
只用 stdlib。跑法：
  <python> _pypi_probe_A.py > _pypi_A_out.txt 2>&1
"""
import json
import urllib.request

PKGS = [
    # 多 provider / 统一调用
    "litellm", "openai", "aisuite", "any-llm", "httpx", "requests",
    # SSE
    "sseclient-py", "httpx-sse", "sse-starlette", "eventsource",
    # 结构化输出 / JSON 容错
    "pydantic", "pydantic-core", "jsonschema", "instructor", "outlines",
    "json-repair", "fastjsonschema", "typeguard",
    # token 计数
    "tiktoken", "tokenizers", "transformers",
    # 规则引擎 / 重试
    "simpleeval", "durable-rules", "tenacity", "backoff", "stamina",
    # 辅助
    "pip-licenses", "funcchain",
]

UA = {"User-Agent": "scan-a/1.0"}


def fetch(pkg, timeout=30):
    url = "https://pypi.org/pypi/%s/json" % pkg
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def pick_wheel(urls):
    if not urls:
        return None
    newest = max(urls, key=lambda u: u.get("upload_time") or "")
    cand = [u for u in urls if u.get("packagetype") == "bdist_wheel"] or urls
    win = [u for u in cand if "win_amd64" in u.get("filename", "")]
    anyw = [u for u in cand if u.get("filename", "").endswith("py3-none-any.whl")]
    pick = (win or anyw or cand)[0]
    return pick.get("filename"), pick.get("size"), newest.get("upload_time")


for pkg in PKGS:
    try:
        d = fetch(pkg)
    except Exception as e:
        print("== %s == ❓ FETCH_FAIL %r" % (pkg, e))
        print()
        continue
    info = d["info"]
    reqs = info.get("requires_dist") or []
    runtime = [r for r in reqs if "extra ==" not in r]
    lic = (info.get("license") or "")
    if len(lic) > 80:
        lic = lic[:80] + "…"
    ws = pick_wheel(info.get("urls") or [])
    print("== %s ==" % pkg)
    print("  version      : %s" % info.get("version"))
    print("  license      : %r" % lic)
    print("  license_expr : %r" % (info.get("license_expression") or ""))
    print("  license_cls  : %s" % [c for c in info.get("classifiers", []) if c.startswith("License")])
    print("  upload_time  : %s" % (ws[2] if ws else None))
    print("  requires_py  : %s" % info.get("requires_python"))
    print("  runtime_deps : %d -> %s" % (len(runtime), runtime))
    if ws:
        print("  wheel        : %s  %.1f KB" % (ws[0], (ws[1] or 0) / 1024.0))
    print()
