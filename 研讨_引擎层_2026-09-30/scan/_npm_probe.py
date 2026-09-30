# -*- coding: utf-8 -*-
import json, urllib.request, urllib.parse
UA={"User-Agent":"scan-c/1.0"}
for pkg in ["adr-tools","@meza/adr-tools","log4brains","markdownlint-cli2","mdformat"]:
    try:
        u="https://registry.npmjs.org/"+urllib.parse.quote(pkg,safe='@/')
        r=urllib.request.Request(u,headers=UA)
        d=json.load(urllib.request.urlopen(r,timeout=30))
    except Exception as e:
        print("== %s == ❓ %r"%(pkg,e)); continue
    latest=d.get("dist-tags",{}).get("latest")
    v=d["versions"].get(latest,{})
    print("== %s =="%pkg)
    print("   latest=%s  lic=%s  deps=%d"%(latest, v.get("license"),
          len(v.get("dependencies") or {})))
    print("   time=%s"%(d.get("time",{}).get(latest)))
    print("   repo=%s"%((v.get("repository") or {}).get("url")))
    print()
