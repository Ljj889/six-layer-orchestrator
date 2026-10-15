---
title: gitignore 白名单解锁 = 静默入库（提交前必跑 dry-run）
version: 1
owner: 调度器（蒸馏自 2026-10-09 伴学·CMD24窗）
last_verified: 2026-10-09
review_cycle: 90d
status: active
tags: [gitignore, 白名单, 静默入库, 密钥泄漏, dry-run, 构建产物, keystore]
source: 伴学·CMD24窗 —— 给 unpackage 开白名单只写 `!app/unpackage/`，整个 cache（含 keystore、apk 缓存）被静默解锁入库，`git add -n` dry-run 才发现
supersedes: null
superseded_by: null
---
# R-013 gitignore 白名单解锁 = 静默入库

**当** 用 `.gitignore` **白名单**（`!` 规则）放行构建产物里的**部分**文件（如图标、精简后的资源）时 → **易犯** 只给**父目录**开白名单（如 `!app/unpackage/`）——**目录一旦放行，其下全部内容（含 keystore、apk 缓存、中间产物）一并解锁**；而 `git status` 只是安静地多出一堆文件（**不报错、不警告**），若顺手 `git add .` 提交，**密钥级文件就静默入库了** → **护栏**：

1. **白名单必须"逐级包含 → 再排除"**，不能只写 `!父目录/`。链式写法（伴学实测，如此才恰好列出 7 个目标 png）：
   `!app/unpackage/` → `app/unpackage/*`（先排除全部）→ `!app/unpackage/res/` → `app/unpackage/res/*` → `!app/unpackage/res/icons/` → `!app/unpackage/res/icons/*.png`（只放行目标）
2. **改完 `.gitignore` 必跑 `git add -n`（dry-run）**：提交前先看"**到底会加什么**"，确认清单里**没有密钥 / 缓存类文件**，才真提交。
3. **密钥类永不进白名单**：keystore / `.env*` / `*local.json` / 证书目录——任何情况都不放行；项目里已有兜底 ignore 规则时，**白名单不得覆盖它们**。
4. **提交后仍复核一次**：`git show --stat` 扫新增文件的**类型**（不是只看数量）——发现意外类型立即 revert。

**关联**：R-007（僵尸能力——"该被忽略却入库"与"无调用点"同属**静默**家族）、G-001（环境坑）、rule 80（取证优先：**dry-run 就是提交前的取证**）、rule 43（False Green 认知）。

**【来源：伴学·CMD24窗，2026-10-09】｜【通用基线】**
