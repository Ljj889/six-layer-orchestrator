# -*- coding: utf-8 -*-
import json, urllib.request
PKGS = ["regex", "requests", "cosmic-ray", "eventsourcing", "litellm", "msgspec",
        "check-jsonschema", "pytest-jsonschema", "jsonschema-rs", "strictyaml",
        "Cerberus", "voluptuous", "schema", "attrs", "configobj"]
UA = {"User-Agent": "scan-c/1.0"}

def fetch(p):
    r = urllib.request.Request("https://pypi.org/pypi/%s/json" % p, headers=UA)
    with urllib.request.urlopen(r, timeout=30) as x:
        return json.loads(x.read().decode("utf-8"))

for pkg in PKGS:
    try:
        d = fetch(pkg)
    except Exception as e:
        print("== %s == ❓ %r" % (pkg, e)); continue
    info = d["info"]; urls = d.get("urls") or []
    reqs = [r for r in (info.get("requires_dist") or []) if "extra ==" not in r]
    lic = (info.get("license") or "").replace("\n", " ")
    if len(lic) > 70: lic = lic[:70] + "…"
    ws = None
    if urls:
        newest = max(urls, key=lambda u: u.get("upload_time") or "")
        cand = [u for u in urls if u.get("packagetype") == "bdist_wheel"] or urls
        win = [u for u in cand if "win_amd64" in u.get("filename", "")]
        anyw = [u for u in cand if u.get("filename", "").endswith("py3-none-any.whl")]
        pick = (win or anyw or cand)[0]
        ws = (pick.get("filename"), pick.get("size"), newest.get("upload_time"))
    print("== %s == v%s | lic=%r | expr=%r | up=%s | req_py=%s | deps=%d %s"
          % (pkg, info["version"], lic, info.get("license_expression"), ws[2] if ws else "?",
             info.get("requires_python"), len(reqs), reqs))
    if ws:
        print("   wheel: %s  %.1fKB" % (ws[0], ws[1] / 1024.0))
    print()
