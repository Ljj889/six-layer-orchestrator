# -*- coding: utf-8 -*-
"""扫描员 C · PyPI 实测脚本：取 license / requires_dist / 最新上传时间 / wheel 体积。
只用 stdlib（urllib + json）。跑法：
  python _pypi_probe.py
"""
import json
import sys
import urllib.request

PKGS = [
    "pytest", "pytest-cov", "coverage", "pluggy", "iniconfig", "packaging", "colorama",
    "jsonschema", "jsonschema-specifications", "referencing", "rpds-py",
    "fastjsonschema",
    "pydantic", "pydantic-core", "annotated-types", "typing-extensions",
    "json-repair",
    "pyrate-limiter", "limits", "circuitbreaker", "tenacity",
    "tiktoken", "llmlingua", "sumy",
    "mutmut", "hypothesis", "great_expectations", "pytest-randomly",
    "pip-licenses",
    "PyYAML",
]

UA = {"User-Agent": "scan-c/1.0"}


def fetch(pkg):
    url = "https://pypi.org/pypi/%s/json" % pkg
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def wheelsize(urls):
    """挑最新版 wheel 体积：优先 win_amd64，其次 any；返回 (文件名, 字节, 上传时间) 或 None"""
    if not urls:
        return None
    # 找最新上传的那个文件的上传时间
    newest = max(urls, key=lambda u: u.get("upload_time") or "")
    cand = [u for u in urls if u.get("packagetype") == "bdist_wheel"]
    if not cand:
        cand = urls
    win = [u for u in cand if "win_amd64" in u.get("filename", "")]
    anyw = [u for u in cand if u.get("filename", "").endswith("py3-none-any.whl")]
    pick = (win or anyw or cand)[0]
    return pick.get("filename"), pick.get("size"), newest.get("upload_time")


for pkg in PKGS:
    try:
        d = fetch(pkg)
    except Exception as e:
        print("== %s == ❓ FETCH_FAIL %r" % (pkg, e))
        continue
    info = d["info"]
    reqs = info.get("requires_dist") or []
    # 只列运行期依赖（去掉 extra 的）
    runtime = [r for r in reqs if "extra ==" not in r]
    lic = info.get("license") or ""
    if len(lic) > 90:
        lic = lic[:90] + "…"
    lic_expr = info.get("license_expression") or ""
    urls = d.get("urls") or []
    ws = wheelsize(urls)
    print("== %s ==" % pkg)
    print("  version      : %s" % info["version"])
    print("  license      : %r" % lic)
    print("  license_expr : %r" % lic_expr)
    print("  classifiers  : %s" % [c for c in info.get("classifiers", []) if "License" in c])
    print("  latest_upload: %s" % (ws[2] if ws else "❓"))
    print("  requires_py  : %s" % info.get("requires_python"))
    print("  runtime_deps : %d -> %s" % (len(runtime), runtime))
    if ws:
        print("  wheel        : %s  %.1f KB" % (ws[0], ws[1] / 1024.0))
    print()
