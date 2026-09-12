# ============================================================
# sync_to_platforms.ps1 - Windows-native twin of sync_to_platforms.sh
# v1.0 - 2026-09-12 - added because this machine has NO usable bash
#        (WSL launcher exists but NO distro is registered -> bash.exe cannot run;
#         Git Bash / MSYS / Cygwin are not installed). Keep both scripts in the repo;
#         run this .ps1 on Windows. The .sh twin is for machines that do have bash.
# v1.1 - 2026-09-12 - version check upgraded: sample >=2 marks (first+last) instead of
#        only the first one; detect target-leads-repo drift; add SKILL.md MD5 +
#        per-dir file counts. Reason: v3.14.0 drift was missed by the single-mark check.
#
# Usage:
#   powershell -File sync_to_platforms.ps1            # sync all three targets
#   powershell -File sync_to_platforms.ps1 wb         # only WorkBuddy
#   powershell -File sync_to_platforms.ps1 cb         # only CodeBuddy
#   powershell -File sync_to_platforms.ps1 codex      # only Codex
#   powershell -File sync_to_platforms.ps1 -Check     # read-only consistency check
#
# Behavior: copies SKILL.md + knowledge/ + references/ + scripts/ into each
#           platform skills dir; never touches .bak / archive in the targets.
# ASCII-only on purpose: Windows PowerShell 5.1 mis-decodes BOM-less UTF-8 .ps1.
# ============================================================
param(
  [Parameter(Position = 0)][string]$Target = '',
  [switch]$Check
)
$ErrorActionPreference = 'Stop'

$repo = $PSScriptRoot
$skill = 'SKILL.md'
$dirs = @('knowledge', 'references', 'scripts')
$targets = [ordered]@{
  wb    = 'C:\Users\one\.workbuddy\skills\six-layer-orchestrator'
  cb    = 'C:\Users\one\.codebuddy\skills\six-layer-orchestrator'
  codex = 'D:\Ai\codex\skills\six-layer-orchestrator'
}

function Get-VersionMarks([string]$path) {
  # 全部版本标记（按出现顺序去重）——用于"抽检 >=2 处"而不是只看首个
  if (-not (Test-Path $path)) { return @() }
  $m = [regex]::Matches((Get-Content $path -Raw -Encoding UTF8), 'v\d+\.\d+\.\d+')
  $seen = New-Object System.Collections.Generic.List[string]
  foreach ($x in $m) { if (-not $seen.Contains($x.Value)) { [void]$seen.Add($x.Value) } }
  return , @($seen.ToArray())
}

function Get-Md5([string]$path) {
  if (-not (Test-Path $path)) { return '-' }
  return (Get-FileHash $path -Algorithm MD5).Hash
}

function Get-DirFileCount([string]$dst, [string]$d) {
  # 排除 __pycache__/*.pyc（引擎运行产物：不进分发，否则计数假阳性）
  $p = Join-Path $dst $d
  if (-not (Test-Path $p)) { return -1 }
  return (Get-ChildItem $p -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -notlike '*.pyc' -and $_.FullName -notmatch '__pycache__' } |
    Measure-Object).Count
}

function Compare-Version([string]$dst) {
  # 抽检首个+末个版本标记，并检测"目标副本版本更高"（= 平台副本可能领先真相源，需回流）
  $bad = 0
  $sv = Get-VersionMarks (Join-Path $repo $skill)
  $dv = Get-VersionMarks (Join-Path $dst $skill)
  if ($sv.Count -eq 0) { Write-Host "  x repo SKILL.md has no version mark"; return 1 }
  $sample = @($sv[0])
  if ($sv.Count -gt 1 -and $sv[-1] -ne $sv[0]) { $sample += $sv[-1] }
  $miss = @()
  foreach ($s in $sample) { if ($dv -notcontains $s) { $miss += $s } }
  if ($miss.Count -eq 0) {
    Write-Host ("  ok version sampled {0}/{1}: {2}" -f $sample.Count, $sv.Count, ($sample -join ' + '))
  } else {
    Write-Host ("  x version mark missing in target: {0}" -f ($miss -join ', ')); $bad++
  }
  if ($dv.Count -gt 0) {
    try {
      $smax = ($sv | Sort-Object { [version]($_ -replace '^v', '') } | Select-Object -Last 1)
      $dmax = ($dv | Sort-Object { [version]($_ -replace '^v', '') } | Select-Object -Last 1)
      if ([version]($dmax -replace '^v', '') -gt [version]($smax -replace '^v', '')) {
        Write-Host "  x target leads repo: target=$dmax repo=$smax (platform copy ahead of source of truth - backflow needed)"
        $bad++
      }
    } catch { Write-Host "  ! version compare skipped (unparsable mark)" }
  }
  return $bad
}

function Get-AssetCount([string]$dst) {
  $idx = Join-Path $dst 'knowledge\_index.md'
  if (-not (Test-Path $idx)) { return -1 }
  $txt = Get-Content $idx -Raw -Encoding UTF8
  return ([regex]::Matches($txt, '(?m)^\| (rules|decisions|guides|framework-skills)/')).Count
}

function Test-Consistency([string]$dst) {
  $bad = 0
  if (-not (Test-Path (Join-Path $dst $skill))) { Write-Host "  x missing $skill"; $bad++ }
  foreach ($d in $dirs) {
    if (-not (Test-Path (Join-Path $dst $d))) { Write-Host "  x missing dir $d/"; $bad++ }
  }
  $bad += Compare-Version $dst
  $sh = Get-Md5 (Join-Path $repo $skill)
  $dh = Get-Md5 (Join-Path $dst $skill)
  if ($sh -eq $dh) { Write-Host "  ok SKILL.md md5 $($sh.Substring(0,8))" }
  else { Write-Host "  x SKILL.md differs: repo=$($sh.Substring(0,8)) target=$($dh.Substring(0,8))"; $bad++ }
  foreach ($d in $dirs) {
    $rn = Get-DirFileCount $repo $d
    $dn2 = Get-DirFileCount $dst $d
    if ($rn -eq $dn2 -and $rn -ge 0) { Write-Host "  ok $d files $rn" }
    else { Write-Host "  x $d file count: repo=$rn target=$dn2"; $bad++ }
  }
  $sn = Get-AssetCount $repo
  $dn = Get-AssetCount $dst
  if ($sn -eq $dn -and $sn -ge 0) { Write-Host "  ok assets $sn" } else { Write-Host "  x asset count: repo=$sn target=$dn"; $bad++ }
  return $bad
}

function Sync-One([string]$dst) {
  Write-Host "=== sync -> $dst ==="
  if (-not (Test-Path $dst)) { New-Item -ItemType Directory -Path $dst -Force | Out-Null }
  Copy-Item (Join-Path $repo $skill) (Join-Path $dst $skill) -Force
  foreach ($d in $dirs) {
    $to = Join-Path $dst $d
    if (Test-Path $to) { Remove-Item $to -Recurse -Force }
    Copy-Item (Join-Path $repo $d) $to -Recurse -Force
  }
  Write-Host "  copied $skill + $($dirs -join '/')/"
  if ((Test-Consistency $dst) -eq 0) { Write-Host "  ok consistency passed" } else { Write-Host "  ! consistency has gaps (see above)" }
}

if ($Check) {
  Write-Host "=== consistency check (read-only) ==="
  foreach ($k in $targets.Keys) {
    Write-Host "[$k]"
    [void](Test-Consistency $targets[$k])
  }
  exit 0
}

if ($Target) {
  if (-not $targets.Contains($Target)) {
    Write-Host "unknown target: $Target (valid: $($targets.Keys -join ' / ') or -Check)"
    exit 1
  }
  Sync-One $targets[$Target]
} else {
  foreach ($k in $targets.Keys) { Sync-One $targets[$k] }
}

Write-Host ''
Write-Host 'done. verify with: powershell -File sync_to_platforms.ps1 -Check'
