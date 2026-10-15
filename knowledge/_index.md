# knowledge/ 经验资产库 · 索引（canonical entry）

> **read_knowledge 唯一入口**（rule 59）：先读本文件，禁止盲搜。检索 = 按问题类型/tags 匹配下表，不按项目名（NASA LLIS 覆辙）。
> 版本：v3.9.3 首建 · 复核点：每个新项目启动（Phase 0.5 顺带 review 召回列表）
> 维护纪律：资产落盘后 30 秒内追一行；被吸收进 SKILL.md rule 的资产可从库移除（空库=吸收彻底）。

| 路径 | 类型 | 状态 | tags | 摘要 | last_verified |
|---|---|---|---|---|---|
| rules/R-001_execution_boundary.md | rule | active | 执行边界,安全,沙箱,runtime | 默认拒绝：无网出口/文件限临时目录/硬超时 | 2026-08-11 |
| rules/R-002_cost_circuit_breaker.md | rule | active | 成本控制,熔断,token预算,runtime | 成本熔断一等公民：调用前 budget gate，告警异步无效（rule 57 的来源） | 2026-08-11 |
| rules/R-003_loop_guardrails.md | rule | active | 循环护栏,死循环,runtime | 循环护栏默认开：max_iterations/无进展检测/目标校验 | 2026-08-11 |
| rules/R-004_structured_envelope_fail_loud.md | rule | active | 结构化输出,fail-loud,runtime | 响应信封 {status,data,error,trace_id} + 绝不静默吞 | 2026-08-11 |
| rules/R-005_checkpointer_transactional.md | rule | active | checkpoint,持久化,事务,schema版本 | Checkpointer 事务化+复合键+schema 版本化（M_CKPT 已落地） | 2026-08-11 |
| rules/R-006_dangerous_op_policy_gate.md | rule | active | 危险操作,策略门,审计,安全 | 危险操作模型外硬策略门+不可变审计（rule 36 引擎化） | 2026-08-11 |
| decisions/ADR-001_shared_state_layer.md | decision | active | 共享状态,黑板,交接schema,架构决策 | 显式共享状态层+类型化交接 schema（阶段 2 落地） | 2026-08-11 |
| decisions/ADR-002_cache_friendly_prompt.md | decision | active | 提示词缓存,性能,prompt组装 | 静态前缀/动态尾部分离，cache hit 当核心指标（7%→84%） | 2026-08-11 |
| framework-skills/experience-distiller.md | framework-skill | active | 经验蒸馏,知识沉淀,Phase7 | 按名可调用的蒸馏能力（Phase 7 专用，模板见 task_templates） | 2026-08-12 |
| guides/G-001_environment_pitfalls.md | guide | active | 环境坑,Windows,沙箱,Electron,git,git代理,pathspec,Python,控制台编码,运行时探针,PATH,WSL,审批模型 | 实战环境坑合集 v1.4（v1.3 基础上 + **node/npm 不在 PATH（指向已删除版本目录）→运行时探针+绝对路径** / **无 Git Bash 只有 WSL → .sh 的 C:/ 路径不兼容，改用 .ps1** / **读+写/删混命令→审批超时被取消，拆独立命令、清理走 node fs.rmSync** / **git http.proxy 指向未运行的代理→直连绕过 `-c http.proxy=`**） | 2026-09-12 |
| guides/G-002_effect_acceptance_guide.md | guide | active | 效果类,主观验收,MOS,语音,净机模拟,user-data-dir,审美反馈 | 效果类验收指南（MOS/CMOS/MUSHRA + 维度拆解 + 盲测，rule 61 操作手册）；**v2 补净机模拟（`--user-data-dir` 干净档案验首启，不动真实数据）+ 审美/口吻类反馈"一句话确认"话术** | 2026-09-12 |
| guides/G-003_agent_channel_fallback.md | guide | active | 编排,子Agent,通道故障,出口,CDP,实例占用 | 子 Agent 通道失效→rule 46 直执行出口；**变体1 任务书空投递 / 变体2 返回工具轨迹无正文**的鉴别与处置；CDP 前探测实例占用与 DB 备份（2026-08-16 番茄钟 + 2026-09-02 便签实战） | 2026-09-02 |
| rules/R-007_zombie_capability.md | rule | active | 僵尸能力,调用点,验收,死代码,第二真相源,preload参数焊死,状态同步 | 无调用点的能力=僵尸（galagame 关系系统 scanRelationshipState 零调用/备份双实现/idb 单例未 init）：新能力必须有宿主接线点；验收前 grep 调用方，无调用点禁止标已验证；**v2 补 preload/胶水层参数焊死变体**（handler 支持但 preload 不传=渲染端能力事实不存在，逐参数对齐 preload↔handler↔d.ts 三处）；**v3 补切换类状态同步变体**（切角色不同步 pet_name / 亮暗跟随系统而非应用内主题 → 列派生状态清单 + 结构性断言） | 2026-09-12 |
| guides/G-004_monorepo_build_order.md | guide | active | monorepo,workspace,构建顺序,dist,typecheck | 改 workspace 底层包先 build 再 typecheck 消费方——消费方解析 dist 而非 src，TS2353 假错识别法（galagame 统一设置面板实战） | 2026-09-01 |
| guides/G-005_web_automation_env.md | guide | active | 环境坑,web,CDP,vite,自动化验证,临时脚本 | web 前端自动化验证坑：vite preview 127.0.0.1/CDP page target/node 加载 TS 源码包须 tsx/BOM 扫描/临时脚本清理 fs.unlinkSync/PATH 每命令前置（galagame 实战） | 2026-09-01 |
| decisions/ADR-003_settings_entry_consolidation.md | decision | active | 设置面板,信息架构,功能与设置配套,UI | 设置集中单一入口分 tab（⚙️+模型/语音/数据）；新功能默认自带设置项 UI；共用配置 UI 注明（galagame 统一设置面板实战） | 2026-09-01 |
| guides/G-006_framework_compliance.md | guide | active | 框架合规,软约束失效,合规检查,six_layer_check,并发会话,启发式噪音 | 软约束失效解毒剂：调用 skill 但骨架被跳过的根因 + 合规检查脚本用法（galagame 教训，配套 scripts/six_layer_check.py，rule 64 引擎化落地案例）；**v2 补脚本 Gate FAIL 甄别与空洞 PASS**（改动范围对焦→产物级取证→噪音放行；"0 个期望类全命中"=vacuous 未验证） | 2026-09-06 |
| rules/R-008_type_gate_false_green.md | rule | active | 类型检查,假绿,tsconfig,include,不可达分支,验证 | 新增目录必须进 tsconfig include，否则 typecheck 是假绿（实测既有 overlay 漏检多年）；不可达分支须标[不可测·已降级]+造脏数据定向验证，不假装已验证 | 2026-09-02 |
| rules/R-009_module_removability.md | rule | active | 解耦,可移除性,编译期依赖,回调注入,红线自洽 | 可移除性优先于整洁性：宿主相关代码内联宿主文件 + 回调注入替代反向 import；验收=grep 外部引用须收敛到单一装配文件 | 2026-09-02 |
| framework-skills/ts-smoke-harness.md | framework-skill | active | 验证,冒烟,esbuild,无测试框架,真实模块,rule73 | 无测试框架时满足 rule 73④"导入真实模块"的手法：esbuild bundle 真实源码→node require 断言行为（实测抓到 typecheck 发现不了的语义与幂等缺陷） | 2026-09-02 |
| rules/R-010_build_config_silent_failure.md | rule | active | 构建配置,静默失效,tailwind,vite,tsconfig,IPC,渲染端 | 构建配置漏扫=静默失效：三层全绿≠没坏——五处高危点（tsconfig include/vite input/tailwind content/preload d.ts/IPC 通道一致性）已引擎化为 six_layer_check render-silent-fail（rule 79，2026-09-05 便签实战硬伤2） | 2026-09-05 |
| rules/R-011_project_reference_first.md | rule | active | 复用优先,项目内参照,检索序,重造轮子,交互渲染 | 改行为前先 grep 项目内已验证同类实现（拖拽/setBounds 两次重造轮子教训）；rule 64 检索序第一环=项目内参照（最廉先验），找不到才升经验库→网→复现 | 2026-09-05 |
| rules/R-012_idempotent_import_visibility.md | rule | active | 幂等,配置注入,静默失效,首启导入,分发预置,验收清单,rule80 | 幂等导入必须留痕：跳过必打日志 + 字段级 skip(reason=user-set/default-equal/empty) + 版本化重导 + 交付标注"只对新档生效" + 直读设置表核对（2026-09-12 番茄宠物V2 preset/personalize 双命中） | 2026-09-12 |
| framework-skills/real-source-repro.md | framework-skill | active | 复现,取证,最小样例,esbuild,私有函数,真实数据,rule41,rule82,rule73 | 真实源码函数 + 真实数据的最小复现手法：esbuild 转译**真实源文件片段**取私有函数，打印"实际发出去了什么"——禁复刻逻辑自测（2026-09-12 番茄宠物V2 嵌套标签定位 + 抓出僵尸分支） | 2026-09-12 |
| rules/R-013_gitignore_whitelist_dryrun.md | rule | active | gitignore,白名单,静默入库,密钥泄漏,dry-run,构建产物,keystore | gitignore 白名单解锁=静默入库：只写 `!父目录/` 会连 keystore/缓存一起放行——**必须"逐级包含→再排除"链 + 提交前 `git add -n` dry-run 取证**（【通用基线】来源：伴学·CMD24窗 2026-10-09） | 2026-10-09 |
| rules/R-014_single_source_of_truth.md | rule | active | 单一真相源,交叉核查,静默失效,硬编码,多副本,断言,契约同步,COLS,改名 | 一处信息散落多边=漏改静默：①尽量收敛到单一真相源（文档层=规则归属总表/代码层=共用常量/契约层=禁手改生成物）②无法收敛时列全副本清单逐处核对 ③配硬校验（加列四处同步 CREATE_TABLE_SQL+MIGRATIONS+EXPECTED_COLUMNS+COLS）④改名先全库 grep（排除构建产物）（【通用基线】来源：伴学·CMD24窗 2026-10-09） | 2026-10-09 |
| rules/R-015_distribution_precheck.md | rule | active | 分发,平台副本,副本领先,真相源,先取证后覆盖,非全绿不许发,rm-rf,静默删除,dry-run | 分发前必跑 `--check`、非全绿不许发：`sync_one` 是"先 rm -rf 后 cp"，目标副本独有文件被静默删除，且新增知识资产不改版本号 → 版本领先检测不触发（2026-10-09 R-013/R-014 副本领先事故的护栏；A3 P2-1 前置 fail-closed 为后续） | 2026-10-15 |

## 四桶说明
- `rules/`：红线，注入 constitution 常驻（当前 **R-001~R-015**；R-007 僵尸能力 / R-008 类型门禁假绿 / R-009 可移除性 / R-010 构建配置静默失效 / R-011 项目内参照物优先 / R-012 幂等导入可见性 / **R-013 gitignore 白名单静默入库** / **R-014 信息散落多边漏改静默** / **R-015 分发前必跑 --check 非全绿不许发**——后六者属"看起来已验证其实没有"家族且都可 grep/断言硬校验；**R-013/R-014 标注【通用基线】，来源：伴学·CMD24窗 2026-10-09**；**R-015 来源：2026-10-15 R-013/R-014 副本领先事故复盘（监理裁决"立刻生效"）**）
- `decisions/`：ADR，注入 plan 作 rationale（当前 ADR-001~003）
- `framework-skills/`：可调用能力（当前：experience-distiller 经验蒸馏 · ts-smoke-harness 无测试框架冒烟 · real-source-repro 真实源码函数复现）
- `guides/`：可选操作手册（当前：G-001 环境坑 v1.4 · G-002 效果类验收 v2 · G-003 子Agent通道 v1.1 · G-004 monorepo构建 · G-005 web自动化 · G-006 框架合规检查 v2）
