# -*- coding: utf-8 -*-
"""汇总 pip --dry-run --report 的真实依赖解析结果"""
import json, glob, os

base = os.path.dirname(os.path.abspath(__file__))
rows = []
for f in sorted(glob.glob(os.path.join(base, "_rep_*.json"))):
    d = json.load(open(f, encoding="utf-8"))
    inst = d.get("install", [])
    url = [i for i in inst if i["metadata"]["name"].lower().replace("_", "-") ==
           os.path.basename(f)[5:-5].lower().replace("_", "-")]
    total = sum((i.get("download_info") or {}).get("archive_info", {}).get("size", 0) or 0 for i in inst)
    names = sorted(i["metadata"]["name"] for i in inst)
    wins = []
    for i in inst:
        dl = i.get("download_info", {})
        u = dl.get("url", "")
        sz = (dl.get("archive_info") or {}).get("size") or 0
        if ".whl" in u:
            wins.append((i["metadata"]["name"], os.path.basename(u.split("?")[0]), sz))
    rows.append((os.path.basename(f), names, total, wins))

for fn, names, total, wins in rows:
    print("===== %s =====" % fn)
    print("  解析出的包数 : %d" % len(names))
    print("  包清单       : %s" % ", ".join(names))
    print("  下载总体积   : %.2f MB" % (total / 1048576.0))
    binp = [w for w in wins if "py3-none-any" not in w[1] and "py2.py3-none-any" not in w[1]]
    print("  非纯 wheel  : %s" % (", ".join("%s(%s,%.2fMB)" % (n, f.split("-")[-1], s / 1048576.0)
                                    for n, f, s in binp) or "无（全纯 Python）"))
    print()
