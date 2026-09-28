#!/usr/bin/env bash
# ============================================================
# sync_to_platforms.sh — 将 six-layer-orchestrator 仓库同步到三处平台 skills 目录
# v1.0 · 2026-09-01 · rule 64 引擎化（能脚本化的不靠自觉）
# v1.1 · 2026-09-12 · 校验升级：版本标记抽检 >=2 处（首个+末个）+ 目标领先检测 + SKILL.md MD5 +
#                     逐目录文件数（排除 __pycache__/*.pyc）——v3.14.0 漂移曾被"只看首个版本"漏掉
#
# 用法：
#   ./sync_to_platforms.sh            # 同步全部三处
#   ./sync_to_platforms.sh wb         # 只同步 WorkBuddy
#   ./sync_to_platforms.sh cb         # 只同步 CodeBuddy
#   ./sync_to_platforms.sh codex      # 只同步 Codex
#   ./sync_to_platforms.sh --check    # 只校验三处一致性，不改动文件
#
# 前置：本脚本位于仓库根目录（与 SKILL.md 同级）。
# 行为：复制 SKILL.md + knowledge/ + references/ + scripts/ 到目标目录；
#       不触碰目标目录的 .bak / archive（历史备份）。
# ============================================================

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL="SKILL.md"
DIRS=("knowledge" "references" "scripts")

# 目标平台定义（可自行增删）
declare -A TARGETS=(
  [wb]="C:/Users/one/.workbuddy/skills/六层编排框架"
  [cb]="C:/Users/one/.codebuddy/skills/six-layer-orchestrator"
  [codex]="D:/Ai/codex/skills/six-layer-orchestrator"
)

md5_of() {
  if command -v md5sum >/dev/null 2>&1; then md5sum "$1" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then shasum "$1" | awk '{print $1}'
  else echo '-'; fi
}

count_files() {
  # 排除 __pycache__/*.pyc（引擎运行产物不进分发，否则计数假阳性）
  find "$1" -type f ! -path '*__pycache__*' ! -name '*.pyc' 2>/dev/null | wc -l | tr -d ' ' || true
}

check_consistency() {
  local dst="$1"
  local missing=0
  [[ -f "$dst/$SKILL" ]] || { echo "  ✗ 缺 $SKILL"; missing=1; }
  for d in "${DIRS[@]}"; do
    [[ -d "$dst/$d" ]] || { echo "  ✗ 缺目录 $d/"; missing=1; }
  done
  # 版本标记抽检 >=2 处（首个 + 末个）；并检测目标副本"领先"真相源（需回流）
  local src_marks dst_marks s_first s_last v ok
  src_marks="$(grep -o 'v[0-9]\+\.[0-9]\+\.[0-9]\+' "$REPO_DIR/$SKILL" | awk '!seen[$0]++' || true)"
  dst_marks="$(grep -o 'v[0-9]\+\.[0-9]\+\.[0-9]\+' "$dst/$SKILL" | awk '!seen[$0]++' || true)"
  if [[ -z "$src_marks" ]]; then
    echo "  ✗ 仓库 SKILL.md 无版本标记"; missing=1
  else
    s_first="$(printf '%s\n' "$src_marks" | head -1)"
    s_last="$(printf '%s\n' "$src_marks" | tail -1)"
    ok=1
    for v in "$s_first" "$s_last"; do
      if ! printf '%s\n' "$dst_marks" | grep -qx "$v"; then
        echo "  ✗ 目标缺版本标记: $v"; missing=1; ok=0
      fi
    done
    [[ $ok -eq 1 ]] && echo "  ✓ 版本抽检通过（$s_first + $s_last；共 $(printf '%s\n' "$src_marks" | grep -c .) 个标记）"
    if [[ -n "$dst_marks" ]]; then
      local s_max d_max
      s_max="$(printf '%s\n' "$src_marks" | sort -V | tail -1)"
      d_max="$(printf '%s\n' "$dst_marks" | sort -V | tail -1)"
      if [[ "$d_max" != "$s_max" && "$(printf '%s\n%s\n' "$s_max" "$d_max" | sort -V | tail -1)" == "$d_max" ]]; then
        echo "  ✗ 目标副本版本更高（$d_max > $s_max）——平台副本可能领先真相源，需回流"; missing=1
      fi
    fi
  fi
  # SKILL.md 内容一致（MD5；无 md5sum/shasum 时降级为 '-' 跳过）
  local sh dh
  sh="$(md5_of "$REPO_DIR/$SKILL")"; dh="$(md5_of "$dst/$SKILL")"
  if [[ "$sh" == "$dh" ]]; then
    echo "  ✓ SKILL.md MD5 一致（${sh:0:8}）"
  else
    echo "  ✗ SKILL.md 不一致: 仓库=${sh:0:8} 目标=${dh:0:8}"; missing=1
  fi
  # 逐目录文件数（防"少拷文件"这类静默分叉）
  local rn dn
  for d in "${DIRS[@]}"; do
    rn="$(count_files "$REPO_DIR/$d")"; dn="$(count_files "$dst/$d")"
    if [[ "$rn" == "$dn" ]]; then
      echo "  ✓ $d 文件数 $rn"
    else
      echo "  ✗ $d 文件数: 仓库=$rn 目标=$dn"; missing=1
    fi
  done
  # 知识资产条数
  local src_n dst_n
  src_n="$(grep -c '^| \(rules\|decisions\|guides\|framework-skills\)/' "$REPO_DIR/knowledge/_index.md" || true)"
  dst_n="$(grep -c '^| \(rules\|decisions\|guides\|framework-skills\)/' "$dst/knowledge/_index.md" || true)"
  if [[ "$src_n" == "$dst_n" ]]; then
    echo "  ✓ 知识资产 $src_n 条"
  else
    echo "  ✗ 资产数不一致: 仓库=$src_n 目标=$dst_n"; missing=1
  fi
  return $missing
}

sync_one() {
  local dst="$1"
  echo "=== 同步 → $dst ==="
  if [[ ! -d "$dst" ]]; then
    echo "  目标目录不存在，创建…"
    mkdir -p "$dst"
  fi
  cp "$REPO_DIR/$SKILL" "$dst/$SKILL"
  for d in "${DIRS[@]}"; do
    rm -rf "$dst/$d"
    cp -r "$REPO_DIR/$d" "$dst/$d"
  done
  echo "  已复制 $SKILL + ${DIRS[*]}/"
  check_consistency "$dst" && echo "  ✓ 一致性通过" || echo "  ⚠ 一致性检查有缺（见上）"
}

# 入口
if [[ "${1:-}" == "--check" ]]; then
  echo "=== 一致性校验（只读）==="
  for key in "${!TARGETS[@]}"; do
    echo "[$key]"
    check_consistency "${TARGETS[$key]}" || true
  done
  exit 0
fi

if [[ -n "${1:-}" ]]; then
  key="$1"
  [[ -n "${TARGETS[$key]:-}" ]] || { echo "未知平台: $key（可选: ${!TARGETS[*]} / --check）"; exit 1; }
  sync_one "${TARGETS[$key]}"
else
  for key in "${!TARGETS[@]}"; do
    sync_one "${TARGETS[$key]}"
  done
fi

echo ""
echo "完成。三处同步后建议跑: ./sync_to_platforms.sh --check"
