# ============================================================
# sync_to_platforms.ps1 - Windows-native twin of sync_to_platforms.sh
# v1.0 - 2026-09-12 - added because this machine has NO usable bash
#        (WSL launcher exists but NO distro is registered -> bash.exe cannot run;
#         Git Bash / MSYS / Cygwin are not installed). Keep both scripts in the repo;
#         run this .ps1 on Windows. The .sh twin is for machines that do have bash.
# v1.1 - 2026-09-12 - version check upgraded: sample >=2 marks (first+last) instead of
#        only the first one; detect target-leads-repo drift; add SKILL.md MD5 +
#        per-dir file counts. Reason: v3.14.0 drift was missed by the single-mark check.
# v1.2 - 2026-09-30 - fix wb target path: the .sh twin was fixed in v3.18.0
#        (six-layer-orchestrator -> the real CJK skill dir name) but the .ps1 was missed,
#        so ps1 sync would silently write into a non-existent old dir. The CJK dir name
#        is spelled via UTF-16 code units to keep this file ASCII-only.
# v1.3 - 2026-09-30 - D-08 companion change (banner trimmed to last 3 versions):
#        1) version anchors switched to two FIXED points - frontmatter version + the
#           '## Workflow' banner version - instead of "first+last mark in the whole file"
#           (after trimming, the "last mark" degenerates into a historical note like
#           v3.9.12 buried in rule text, so the anchor drifts);
#        2) root-level files (SKILL.md + CHANGELOG.md) are now distributed and verified
#           by MD5/existence (before, only SKILL.md was checked; adding CHANGELOG.md
#           would have gone red because the target lacked it).
#
# Usage:
#   powershell -File sync_to_platforms.ps1            # sync all three targets
#   powershell -File sync_to_platforms.ps1 wb         # only WorkBuddy
#   powershell -File sync_to_platforms.ps1 cb         # only CodeBuddy
#   powershell -File sync_to_platforms.ps1 codex      # only Codex
#   powershell -File sync_to_platforms.ps1 -Check     # read-only consistency check
#
# Behavior: copies root files (SKILL.md, CHANGELOG.md) + knowledge/ + references/ +
#           scripts/ into each platform skills dir; never touches .bak / archive.
# ASCII-only on purpose: Windows PowerShell 5.1 mis-decodes BOM-less UTF-8 .ps1.
# ============================================================
param(
  [Parameter(Position = 0)][string]$Target = '',
  [switch]$Check
)
$ErrorActionPreference = 'Stop'

$repo = $PSScriptRoot
$rootFiles = @('SKILL.md', 'CHANGELOG.md')
$dirs = @('knowledge', 'references', 'scripts')
# wb skill dir name is CJK; spelled via code units (see header note) to keep this file
# ASCII-only. Do NOT hardcode the CJK string literal here (PS 5.1 mis-decodes BOM-less UTF-8).
$wbDirName = -join [char[]]@(0x516D, 0x5C42, 0x7F16, 0x6392, 0x6846, 0x67B6)
$targets = [ordered]@{
  wb    = (Join-Path $env:USERPROFILE ".workbuddy\skills\$wbDirName")
  cb    = 'C:\Users\one\.codebuddy\skills\six-layer-orchestrator'
  codex = 'D:\Ai\codex\skills\six-layer-orchestrator'
}

function Get-VersionMarks([string]$path) {
  # all version marks in order, de-duplicated
  if (-not (Test-Path $path)) { return @() }
  $m = [regex]::Matches((Get-Content $path -Raw -Encoding UTF8), 'v\d+\.\d+\.\d+')
  $seen = New-Object System.Collections.Generic.List[string]
  foreach ($x in $m) { if (-not $seen.Contains($x.Value)) { [void]$seen.Add($x.Value) } }
  return , @($seen.ToArray())
}

function Get-Anchors([string]$path) {
  # two FIXED anchors: [0] frontmatter version (first mark), [1] '## Workflow' banner version
  if (-not (Test-Path $path)) { return @('', '') }
  $raw = Get-Content $path -Raw -Encoding UTF8
  $fm = [regex]::Match($raw, 'v\d+\.\d+\.\d+')
  $fmV = ''
  if ($fm.Success) { $fmV = $fm.Value }
  $bnV = ''
  $lines = Get-Content $path -Encoding UTF8
  foreach ($ln in $lines) {
    if ($ln -match '^## Workflow') {
      $b = [regex]::Match($ln, 'v\d+\.\d+\.\d+')
      if ($b.Success) { $bnV = $b.Value }
      break
    }
  }
  return , @($fmV, $bnV)
}

function Get-MaxVersion([string]$path) {
  $v = Get-VersionMarks $path
  if ($v.Count -eq 0) { return '' }
  $max = $v[0]
  foreach ($x in $v) {
    try {
      if ([version]($x -replace '^v', '') -gt [version]($max -replace '^v', '')) { $max = $x }
    } catch { }
  }
  return $max
}

function Get-Md5([string]$path) {
  if (-not (Test-Path $path)) { return '-' }
  return (Get-FileHash $path -Algorithm MD5).Hash
}

function Get-DirFileCount([string]$dst, [string]$d) {
  # exclude __pycache__/*.pyc (engine runtime artifacts: not distributed, else false counts)
  $p = Join-Path $dst $d
  if (-not (Test-Path $p)) { return -1 }
  return (Get-ChildItem $p -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -notlike '*.pyc' -and $_.FullName -notmatch '__pycache__' } |
    Measure-Object).Count
}

function Compare-Version([string]$dst) {
  # two fixed anchors (frontmatter + banner), then detect "target leads repo" drift
  $bad = 0
  $srcSkill = Join-Path $repo 'SKILL.md'
  $dstSkill = Join-Path $dst 'SKILL.md'
  if (-not (Test-Path $dstSkill)) { return 1 }
  $sa = Get-Anchors $srcSkill
  $dv = Get-VersionMarks $dstSkill
  $sample = @()
  foreach ($a in $sa) { if ($a -ne '' -and $sample -notcontains $a) { $sample += $a } }
  if ($sample.Count -eq 0) { Write-Host "  x repo SKILL.md has no version anchor"; return 1 }
  $miss = @()
  foreach ($s in $sample) { if ($dv -notcontains $s) { $miss += $s } }
  if ($miss.Count -eq 0) {
    Write-Host ("  ok version anchors: {0}" -f ($sample -join ' + '))
  } else {
    Write-Host ("  x version anchor missing in target: {0}" -f ($miss -join ', ')); $bad++
  }
  $smax = Get-MaxVersion $srcSkill
  $dmax = Get-MaxVersion $dstSkill
  if ($smax -ne '' -and $dmax -ne '') {
    try {
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
  foreach ($f in $rootFiles) {
    if (-not (Test-Path (Join-Path $dst $f))) { Write-Host "  x missing root file $f"; $bad++ }
  }
  foreach ($d in $dirs) {
    if (-not (Test-Path (Join-Path $dst $d))) { Write-Host "  x missing dir $d/"; $bad++ }
  }
  $bad += Compare-Version $dst
  foreach ($f in $rootFiles) {
    $sh = Get-Md5 (Join-Path $repo $f)
    $dh = Get-Md5 (Join-Path $dst $f)
    if ($sh -eq $dh) { Write-Host "  ok $f md5 $($sh.Substring(0,8))" }
    else { Write-Host "  x $f differs: repo=$($sh.Substring(0,8)) target=$($dh.Substring(0,8))"; $bad++ }
  }
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
  foreach ($f in $rootFiles) {
    Copy-Item (Join-Path $repo $f) (Join-Path $dst $f) -Force
  }
  foreach ($d in $dirs) {
    $to = Join-Path $dst $d
    if (Test-Path $to) { Remove-Item $to -Recurse -Force }
    Copy-Item (Join-Path $repo $d) $to -Recurse -Force
  }
  Write-Host "  copied $($rootFiles -join ', ') + $($dirs -join '/')/"
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
