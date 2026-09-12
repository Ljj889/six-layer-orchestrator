# 现象排查卡（Symptom Triage Cards · rule 80）

> 版本：v2.1（v3.16.0 番茄宠物V2 实战蒸馏）| 用途：用户报**现象类问题**时的标准取证流程 | 定位：rule 80 的落地模板，与 `six_layer_check.py render-silent-fail` / `product-assert` / `active-tree`、rule 81 长排错检查点、rule 41 归因闭环联动
> v2.1 增补：① 验收声明三要素（档案状态/代码来源/启动方式）② 现象→可判定断言模板（预期日志行 + 反证信号）③ 输入输出可见日志纪律 ④ 接手类现象先跑 active-tree（rule 82）
> 来源：2026-09-05 家俊 Electron 便签实战复盘硬伤3——"看不到"问题三轮往返（第一轮靠猜、第二轮才加日志、第三轮才做对照实验）。**分诊应该一轮就有，而不是摸出来。**
> v2.0 深化（家俊标准）：每卡补齐 ①第 0 步环境快照（漂移五族）②可粘贴诊断日志代码片段 ③用户动作序列 ④字段化回传格式 ⑤确认执行人（机器断言 vs 用户回执）。

---

## 使用规则（先读这段）

1. **取证优先（硬规则）**：现象类问题禁止未取证就改代码。第一动作三件——① 加最小诊断日志；② 按对应卡片向用户要**标准数据**（一次要全，不要挤牙膏）；③ 设计对照实验（一次只改一个变量）。
2. **第 0 步环境快照（v3.14.1）**：任何排查动作之前，先比对"用户环境 vs 开发环境"漂移五族（版本/缓存/配置/数据密度/状态）——**测试环境永远 ≠ 用户环境**（案例：迁移门控静默跳过，测试库全新而用户库 db_version 已漂移，一条 SQL 就能定位却第二轮才做）。采集零门槛：优先 `npm run diag` 一键脚本，禁止挤牙膏式问答。
3. **先跑脚本再人工**：涉及渲染端窗口/样式/IPC 的现象，先跑 `python scripts/six_layer_check.py render-silent-fail <项目根>` + build 后 `product-assert`——30 秒排除/命中一半以上高频根因（rule 79）。
4. **判定树走完再动手**：按卡片"判定顺序"从上往下，每步有结论才走下一步；证伪的假设立即落盘（rule 81：`[排错检查点] 已排除: X | 当前嫌疑: Y | 下一步: Z`）。
5. **修复收工 = 现象消失被证实（rule 41 归因闭环）**：机器可判定项附自动断言输出；用户确认项附回执+截图+声明"变量唯一、未重启未清缓存"。
6. **验收声明三要素（v3.16.0）**：任何一方说"我跑通了"都不构成证据——必须同时声明 **档案状态**（新档/旧档）、**代码来源**（源码/构建产物/包内 asar）、**启动方式**（dev/packaged）。三者任一不同 = **不算同一验证**（实测：用户"自己电脑解压跑了没问题"用的是**已有档案**、完全没走首启注入路径，属无效验证）。缺三要素的验收按未验证处理（rule 42）。
7. **接手类现象先跑活跃树判定（v3.16.0 · rule 82）**：现象是"改了没效果 / 改了没变化"、且项目里有**多棵候选树**（独立版 vs 根级、备份 vs 活跃）时——第一动作是 `python scripts/six_layer_check.py active-tree <候选1> <候选2>`，先确认改的是活跃树，再进排查卡。否则修复可能全打在死树上**且不报任何错**。
8. **修复后必须回归**：按卡末"回归验证"确认现象消失且无新现象（rule 43 两层制）。

---

## 第 0 步 · 环境快照（所有卡共用 · 漂移五族）

**采集方式（零门槛，二选一）**：
- 项目有 `npm run diag` → 让用户双击/粘贴执行，回传输出；
- 没有 → 把下面这条"最小快照清单"发给用户，逐项回填（或按卡 3 的模板给项目补 diag 脚本）。

**回传格式（字段化，禁止自由叙述）**：
```
[ENV-SNAPSHOT]
app_version=<用户机上应用版本>
db_version=<用户库 schema 版本>(expected=<代码期望版本>)
deps=<package.json 关键依赖版本 vs lock>
cache_mtime=<缓存目录最后修改时间> cache_orphan=<是否存在无主缓存目录>
config_user=<用户配置文件关键字段值>(default=<代码默认值>)
data_rows=<用户核心表行数量级>
status=ok | unavailable（采集失败必须显式标注，禁止静默当 PASS）
```

**漂移五族对照**：① 版本（app/db schema/依赖）② 缓存（mtime/孤儿缓存）③ 配置（用户值 vs 代码默认）④ 数据密度（用户量级 vs 测试造数）⑤ 状态（中间态/迁移中断/脏数据）。**任一族漂移 → 先修环境再查代码**。

---

## 卡 1 · 窗口不可见 / "什么都看不到"

**第 0 步**：跑环境快照（重点看 app_version 与 cache_orphan）。

**第一步取什么数据（标准五项，一次要全）+ 采集片段**：
在主进程窗口创建后加：
```js
console.log('[DIAG-WIN]', JSON.stringify({
  visible: win.isVisible(), pos: win.getPosition(), size: win.getSize(),
  alwaysOnTop: win.isAlwaysOnTop(),
  loaded: false
}))
win.webContents.on('did-finish-load', () => console.log('[DIAG-WIN] did-finish-load=true'))
win.webContents.on('render-process-gone', (_e, d) => console.log('[DIAG-WIN] gone', JSON.stringify(d)))
```
渲染端入口首行加：
```js
console.log('[DIAG-RENDER] mounted', location.href)
window.addEventListener('error', e => console.log('[DIAG-RENDER] error', e.message))
```

**用户动作序列**：① 正常启动应用 ② 等 10 秒 ③ 把控制台/日志文件内容原样回传（或运行 `npm run diag --window`）④ 如果方便，截一张全屏（含任务栏）。

**回传格式**：
```
[SYMPTOM-DATA:win]
visible= pos= size= alwaysOnTop=
did-finish-load=true|false
render-mounted=true|false href=
console_errors=<前 5 条>
```

**判定顺序**：① `did-finish-load=false` → 加载失败（路径 404 / vite input 漏登记 → 跑 `render-silent-fail`）② `visible=false`/尺寸 0/坐标在屏外 → 修创建参数 ③ `render-mounted=false` → preload 未加载或 JS 崩（看 console_errors）④ 全正常但用户看不见 → 对照实验：关其他窗口排除 z-order；透明窗查 `transparent:true` + 背景透明 ⑤ 仍无结论 → 走 rule 64 纠错先检索（项目内参照 → 经验库 → 网）。

**高频根因**：① html 入口未进 vite input（404 白屏）② preload 路径错/未加载 → 渲染端 JS 崩 ③ 透明窗背景全透明 ④ z-order/遮挡 ⑤ 多显示器坐标漂移

**确认执行人**：机器可判定（visible/pos/size/did-finish-load）→ 自动断言；最终"用户能看见"→ 用户回执（附"未重启未清缓存"声明）。

**回归验证**：正常启动 + 异常路径各一次，窗口均出现且诊断日志齐全。

---

## 卡 2 · 样式全丢 / "界面全没样式但 build 绿"

**第 0 步**：环境快照（重点 deps 与 cache）。

**第一步（30 秒）**：先跑 `python scripts/six_layer_check.py render-silent-fail <项目根>`（tailwind content 漏扫=第一根因）+ build 后跑 `product-assert <项目根>`（产物 CSS 里根本没有类=本轮新增的产物级黑洞，四轮排错案例第一轮就能抓到）。

**判定顺序**：① `product-assert` FAIL → 产物 CSS 缺类，回查 content 配置与构建链 ② devtools 查产物 `<style>`/link css 是否含 `.bg-`/`.flex` 规则 → 完全没有 = content/postcss 链断 ③ `dist/` 里 css 体积 0KB/几 KB → content 没扫到任何类 ④ postcss 链：`postcss.config.*` 是否注册 tailwind 插件、css 入口 `@tailwind`/`@import "tailwindcss"` ⑤ 样式表在但个别元素没样式 → 查该目录是否在 content 覆盖内（v4 查 `@source`）。

**采集片段（构建脚本尾部，预埋取证）**：
```js
// build 后自动断言（或并入 CI）：node scripts/product-assert-check.js
const css = fs.readFileSync('dist/assets/index.css', 'utf8')
for (const cls of ['bg-rose-500', 'flex', 'rounded-lg']) {
  if (!css.includes(cls)) { console.error(`[PRODUCT-ASSERT] missing: ${cls}`); process.exitCode = 1 }
}
```

**用户动作序列**：① 完整重新 build ② 回传 `dist/assets/*.css` 文件大小 ③ 打开应用截图一张。

**回传格式**：
```
[SYMPTOM-DATA:style]
css_files_size=<各 css 文件字节数>
product_assert=<PASS|FAIL + 缺失类清单>
tw_config_content=<content 数组内容>
```

**高频根因**：① tailwind content 漏新目录 ② postcss 未接 tailwind ③ css 入口没被页面引 ④ v3/v4 混用（v4 靠 `@source`）⑤ class 动态拼接被 purge

**确认执行人**：机器可判定（产物 grep + 页面元素 computed style）→ 自动断言；最终观感 → 用户回执。

**回归验证**：重跑 build（tailwind 构建期扫描）→ `product-assert` PASS → 页面样式正常。

---

## 卡 3 · IPC 无响应 / "调用没返回"

**第 0 步**：环境快照（重点 app_version 与 db_version——迁移门控漂移会让 handler 早退）。

**第一步（30 秒）**：跑 `render-silent-fail`（IPC 通道集合比对直接列出"preload 调了但主进程没注册"的通道）。

**采集片段（两侧边界预埋，IPC 边界切面）**：
```js
// 主进程：每个 handler 首行
console.log('[DIAG-IPC-IN]', 'win:info', JSON.stringify(args ?? {}))
// preload：invoke 包装
const invoke = (ch, ...a) => { console.log('[DIAG-IPC-OUT]', ch); return ipcRenderer.invoke(ch, ...a) }
```

**用户动作序列**：① 复现一次"没响应"的操作 ② 回传日志中 `[DIAG-IPC-OUT]` 与 `[DIAG-IPC-IN]` 成对情况 ③ 附 app 版本。

**回传格式**：
```
[SYMPTOM-DATA:ipc]
called_out=<preload 发起的通道列表>
handled_in=<主进程收到的通道列表>
version=app=<..> db=<..>
```

**判定顺序**：① `render-silent-fail` 报 preload 通道未注册 → 补 handler ② 通道名逐字符核对（建议常量化两侧 import）③ handler 注册时机（app.whenReady 前/条件分支跳过——rule 72 僵尸检查）④ contextBridge key 与 `window.<key>` 一致性 ⑤ 返回值不可结构化克隆 → 收敛纯 JSON ⑥ 仍无结论 → 两侧日志比对定位断点侧。

**高频根因**：① 通道拼写不一致 ② handler 忘注册/被跳过 ③ preload 未重新编译 ④ 返回值不可克隆 ⑤ `sandbox:true` 限制

**确认执行人**：机器可判定（通道集合 + invoke 返回值）→ 自动断言。

**回归验证**：每条涉及通道真实触发一次，断言返回值正确（rule 43 真实交互路径）。

---

## 现象 → 可判定断言模板（v3.16.0 · 每条关键链路必填）

口语现象不能直接当验收标准——**落码前**先把它转成两字段断言，**落码后**照单收证据：

```
[ASSERT:现象] <用户原话，一个字不改>
预期日志行 = <可 grep 的行，含关键变量：文本 / 参数 / 引擎 / 档案路径>
反证信号   = <出现 X 也证明防护生效，不算 FAIL（实测：[vp] 流结束丢弃未完成标签残渣）>
机器可判定 = <自动断言：grep 产物 / SQL 查状态字段 / 脚本子命令 exit code>
用户确认项 = <听感/观感：回执 + 截图 + 声明"变量唯一、未重启未清缓存">
验收三要素 = 档案=<新档|旧档> 代码来源=<源码|构建产物|asar> 启动=<dev|packaged>
```

**纪律**：
1. **每条关键链路必须有一行"输入输出可见"的日志**——打印实际收到的文本 / 参数 / 命中的引擎名 / 用的档案目录；它是最便宜的取证包，出事那一轮就有人能判读（实测：日志只打 `additions` 不打 `req text`，导致"标签是否被当正文发出去"无法自证，多花一轮）。
2. **预期日志行与反证信号先写下来再加日志**（防事后解释、防"看到什么都能解释成套话"）。
3. 断言逐条进交付说明给结论（PASS / FAIL / 未验证），禁止"全绿=全通"式表述（rule 42）。

---

## 证据升级（三张卡走完仍无结论时）

按顺序收齐再升级，不要挤牙膏式提问：
1. 现象截图/录屏 + 期望行为描述
2. `[ENV-SNAPSHOT]` + `[SYMPTOM-DATA:*]` 全量回传
3. 复现步骤（最小复现路径）+ 是否必现
4. 上轮 `[排错检查点]` 记录（已排除什么，别重复排查）

然后走 rule 64 纠错先检索：**项目内参照 grep** → `read_knowledge(现象关键词)` → WebSearch → 才考虑再动代码。

## 决策卡（可粘贴到任意开发窗口）

```
用户报了一个现象（不是报错）。按取证优先执行：
⓪ 先要 [ENV-SNAPSHOT]（npm run diag 或最小快照清单）——漂移五族先比对，先修环境再查代码
⓪.5 项目里有多棵候选树（独立版/根级/备份）→ 先跑 active-tree 判活跃树（rule 82）：
    不确认就动手 = 修复可能全打在死树上且不报错
① 跑 python scripts/six_layer_check.py render-silent-fail <项目根>（窗口/样式/IPC 现象）
   build 涉及样式改动 → 再跑 product-assert（含时序与稳定性：打包进程/两次采样/zip>asar）
② 按对应现象排查卡，一次向用户要全标准数据 + 加最小诊断日志（有预埋取证包直接要回传）
③ 设计对照实验（一次只改一个变量），每个被证伪的假设立即落盘 lessons.md
④ 超过 3 个假设证伪仍无结论 → 写断点小结再继续（rule 81）
⑤ 定位根因前禁止改代码；修复交付必须附「现象消失证据」
   （机器可判定=自动断言；用户确认=回执+截图+未重启未清缓存声明）——rule 41 归因闭环
⑥ 交付前把现象写成 [ASSERT] 两字段（预期日志行 + 反证信号）+ 验收三要素
   （档案=新档/旧档 · 代码来源=源码/产物/asar · 启动=dev/packaged）——缺则按未验证（rule 42）
```
