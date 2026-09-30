#!/usr/bin/env bash
# 扫描员B：核仓级 LICENSE 文件（PyPI metadata 常为 None，必须回仓核）
# 用法: bash _probe_license.sh <owner/repo> [<owner/repo> ...]
for r in "$@"; do
  echo "=============================================================="
  echo "### github.com/$r"
  ok=0
  for f in LICENSE LICENSE.md LICENSE.txt license LICENCE COPYING; do
    for br in main master; do
      code=$(curl -s -o "/tmp/lic_$$.txt" -w "%{http_code}" --max-time 20 \
        "https://raw.githubusercontent.com/$r/$br/$f")
      if [ "$code" = "200" ]; then
        echo "  file: $f @ $br (HTTP 200)"
        echo "  --- 首 4 行 ---"
        head -4 "/tmp/lic_$$.txt" | sed 's/^/    /'
        echo "  --- 判定关键词 ---"
        grep -o -i -E "MIT License|Apache License|BSD [0-9]-Clause|GNU (AFFERO )?GENERAL PUBLIC LICENSE|Mozilla Public License|Business Source License|Elastic License|Creative Commons" "/tmp/lic_$$.txt" | sort -u | head -3 | sed 's/^/    /'
        ok=1
        break 2
      fi
    done
  done
  [ "$ok" = "0" ] && echo "  ❓ 未在默认分支找到常见 LICENSE 文件名"
  # 仓库元数据
  curl -s --max-time 20 "https://api.github.com/repos/$r" -o "/tmp/repo_$$.json"
  if [ -s "/tmp/repo_$$.json" ]; then
    python3 - "/tmp/repo_$$.json" <<'PY' 2>/dev/null
import json,sys
try:
    d=json.load(open(sys.argv[1],encoding="utf-8"))
except Exception as e:
    print("  ❓ 仓库元数据解析失败"); sys.exit()
if d.get("message"):
    print("  ❓ GitHub API:",d["message"]); sys.exit()
print("  stars        :",d.get("stargazers_count"))
print("  license(API) :",(d.get("license") or {}).get("spdx_id"))
print("  pushed_at    :",d.get("pushed_at"))
print("  archived     :",d.get("archived"))
print("  open_issues  :",d.get("open_issues_count"))
print("  default_branch:",d.get("default_branch"))
PY
  fi
done
