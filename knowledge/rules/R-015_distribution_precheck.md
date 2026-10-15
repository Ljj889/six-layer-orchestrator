---
title: 分发前必跑 --check，非全绿不许发（先取证，后覆盖）
version: 1
owner: 调度器（2026-10-15 监理裁决"立刻生效"·来源：R-013/R-014 副本领先事故复盘）
last_verified: 2026-10-15
review_cycle: 90d
status: active
tags: [分发, sync_to_platforms, 平台副本, 副本领先, 真相源, 先取证后覆盖, 非全绿不许发, rm-rf, 静默删除, dry-run]
source: 2026-10-15 —— R-013/R-014 于 2026-10-09 落盘在 WorkBuddy 平台副本、真相源仓库从未收到，10-11/10-15 两次审计均漏；而 sync_one 是"先 rm -rf 后 cp -r"，跑一次即静默删掉副本独有文件
supersedes: null
superseded_by: null
---
# R-015 分发前必跑 --check，非全绿不许发

**当** 准备执行 `sync_to_platforms`（把真相源分发到 WorkBuddy / CodeBuddy / Codex 三端）时 → **易犯** 拿到命令就直接开跑——因为 `sync_one` 是**先整目录删除、再整目录拷贝**（`sync_to_platforms.sh:144-145` 的 `rm -rf` + `cp -r`；`sync_to_platforms.ps1:179-180` 的 `Remove-Item -Recurse -Force` + `Copy-Item -Recurse -Force`） → **目标副本独有的文件会被当场静默删除**：不报错、不回滚、退出码照常为 0。且**越隐蔽越好**——`knowledge/` 里新增文件**不会**改动 `SKILL.md` 的版本号，而"版本领先检测"只比 `SKILL.md` 的版本标记，**因此完全不触发**；唯一会响的两个信号（`knowledge/` 文件数、`_index.md` 资产数）都是**事后**运行且**只打印不阻断**。 → **护栏**：

1. **分发前必跑只读校验（硬步骤）**：
   `powershell -NoProfile -ExecutionPolicy Bypass -File sync_to_platforms.ps1 --check`
   （bash 可用时等价：`./sync_to_platforms.sh --check`）。只读，不改盘。
2. **非全绿不许发**：输出里出现任何 `x` → **【停】**，先查"是不是平台副本领先"，**不许直接 sync**。
3. **判读口诀（两个方向处置相反）**：
   - `target > repo`（如 `x knowledge file count: repo=25 target=27`）= **副本领先** → **先回流**：把副本独有文件搬回真相源，再分发。
   - `target < repo` = 正常"待分发"，可以发。
   - `x … 目标副本版本更高（…需回流）` = 同第一种，**一律先回流**。
4. **副本独有内容绝不允许被覆盖掉**：回流方向必须是"副本 → 仓库"，**反过来 `cp` 会丢内容**；回流前后各比对一次内容（MD5/字节数），禁止"看起来搬过来了"。
5. **新增/移动知识资产后，必须重跑 `--check`**：`knowledge/rules|decisions|guides|framework-skills` 条数变化**不改版本号** → 老检测方法（只比版本锚点）看不见；`--check` 的 `asset count` 是唯一会响的信号。
6. **本条是"先取证再动手"家族的分发版**：与 R-013「改完 `.gitignore` 必跑 `git add -n` dry-run」同一手法——**把"看不到会失去什么"变成一条必跑命令**。

**已知缺口（已排期 A3 · 下一轮必须做，本轮只立纪律）**：`--check` 当前是**事后 + 非阻断**的（`sync_one` 先 `rm -rf` 再检查，且 `|| echo` 把非零吞掉）。排期项：
- **P2-1** 一致性检查**前置 + fail-closed**：发现"目标存在仓库没有的文件"→ 拒绝执行，须 `--force`；
- **P2-2** `rm -rf` / `Remove-Item` 改为先移入 `$dst/.trash-<ts>/`（可回滚，禁止静默删）；
- **P2-3** 新增 `--pull-back <wb|cb|codex>` 显式回流入口；
- **P2-4** `rule_index.py` 增报 `knowledge_rules`；`six_layer_check` 增加"仓库与三副本 `knowledge/` 清单一致"检查项。
**在 P2-1 落地前，第 1/2 条 SOP 纪律就是唯一防线——不得因为"排期了"就跳过它。**

**关联**：R-013（提交前 dry-run 取证——同型：先取证再动手）、R-014（一处信息散落多边 = 漏改静默——"平台副本"就是最典型的多副本）、R-007（僵尸能力 / 第二真相源）、R-005（事务化：删+写两步本应原子）、rule 41（取证优先）、rule 76（真相源纪律）、rule 64（能硬约束的不靠自觉——本条的终态是 P2-1）。

**【来源：2026-10-15 R-013/R-014 副本领先事故复盘 · 监理裁决"立刻生效"】**
