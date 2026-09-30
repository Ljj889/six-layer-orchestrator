#!/usr/bin/env bash
# 扫描员B 用：批量拉 PyPI JSON，抽 license / requires_dist / 版本 / 发版日期
PKGS="$@"
for p in $PKGS; do
  echo "=============================================================="
  echo "### $p"
  curl -s --max-time 25 "https://pypi.org/pypi/$p/json" -o "/tmp/pypi_$p.json"
  if [ ! -s "/tmp/pypi_$p.json" ]; then
    echo "  ❓ 拉取失败/空（网络或包名错）"
    continue
  fi
  python3 - "$p" "/tmp/pypi_$p.json" <<'PY' 2>/dev/null || echo "  ❓ python3 解析失败"
import json,sys
p,fn=sys.argv[1],sys.argv[2]
try:
    d=json.load(open(fn,encoding="utf-8"))
except Exception as e:
    print("  ❓ JSON 解析失败:",e); sys.exit()
i=d.get("info",{})
print("  version      :",i.get("version"))
print("  license      :",repr(i.get("license")))
lic=i.get("license_expression")
print("  license_expr :",lic)
cls=[c for c in (i.get("classifiers") or []) if c.startswith("License")]
print("  license_cls  :",cls)
print("  requires_py  :",i.get("requires_python"))
rd=i.get("requires_dist") or []
print("  requires_dist(%d):"%len(rd))
for r in rd[:40]:
    print("      -",r)
u=d.get("urls") or []
if u:
    print("  latest_upload:",u[0].get("upload_time"),"| file:",u[0].get("filename"))
rel=d.get("releases") or {}
times=[]
for k,v in rel.items():
    for f in v:
        t=f.get("upload_time")
        if t: times.append((t,k))
times.sort()
print("  first_release:",times[0] if times else None)
# 最近 5 个版本
print("  last5_releases:", [t[1] for t in times[-5:]])
PY
done
