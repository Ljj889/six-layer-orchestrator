"""six_layer_check.py — 六层框架合规检查（rule 64 硬约束优先 · 框架对齐 v3.16.0；自 v3.9.12 起）

来源：galagame 实战教训（2026-09-01）——调用 skill 但骨架流程被跳过
（无 Phase 0.5 / 无 Phase 7 蒸馏 / 无 lessons/cost_log），知识库零产出。
根因：SKILL.md 是提示词纪律（软约束），多轮/并发会话中会被稀释。
本脚本把"靠自觉记得走框架"变成"跑一下就知道缺什么"。

用法：
    python six_layer_check.py [项目目录] [--mode init|deliver|auto] [--json] [--strict]
    - 默认目录 = 当前工作目录
    - --mode init    ：开工前检查（应具备 Phase 0/0.5 痕迹）
    - --mode deliver ：收尾检查（应具备 Phase 5-7 痕迹）
    - --mode auto    ：全部检查（默认）
    - --json         ：输出 JSON（供程序消费）
    - --strict       ：有缺失即 exit 1（默认 exit 0=检查完成）

    python six_layer_check.py render-silent-fail <项目目录> [--json] [--strict]
    - 渲染端静默失效五项检查（rule 79 · v3.14.0 新增，2026-09-05 家俊 Electron 实战硬伤2）：
      tsconfig include / vite input / tailwind content / preload d.ts / IPC 通道一致性
      - 配置文件存在才检查，不存在标 SKIP（防误报）
      - typecheck 绿 + build 绿 + 不崩 ≠ 真的没坏：这五处任何一个漏扫都是静默失效

    python six_layer_check.py product-assert <项目目录> [--json] [--strict] [--force-with-reason=理由]
    - 产物级断言（rule 79 第六项 · v3.14.1 研讨会收敛）：build 绿 ≠ 产物真的含所需内容
      - Tier A 纯 Tailwind 项目：源码引用的 utility 类在产物 CSS 缺失≥3 → FAIL 阻断
      - CSS Modules/CSS-in-JS 共存 → WARN 不阻断（类名 hash 误报防护，红队裁决）
      - Tier B product-assert.json：[{"file": "dist/...*", "contains": "字面量"}] 断言通道名等
      - --force-with-reason=理由 留痕跳过（无 reason 跳过 = Red Flag）；产物陈旧告警
      - v3.16.0 增时序与稳定性：打包进程探针 / 产物尺寸两次采样 / zip>asar 归档时序

    python six_layer_check.py active-tree <候选目录1> [候选目录2 ...] [--userdata=<路径>] [--json] [--strict]
    - 活跃树判定四证据（rule 82 ① · v3.16.0 新增 · 2026-09-12 番茄宠物V2 实战）：
      接手交接文档 / 多棵候选树时，判断"哪棵树才是真正在跑的活跃树"——
      ① 最近提交时间（git log --date=iso）② 构建产物/可执行文件 mtime
      ③ 运行时痕迹（%APPDATA%\\<app> 下 db/日志 mtime —— 决定性证据）
      ④ 依赖与分发链路（node_modules / distribution / electron-builder extraResources）
      - 给 ≥2 个目录 → 附对比判定行（谁有运行时痕迹谁是活跃树）
      - 判据与文档冲突时**以磁盘为准**，向用户一句话确认后再动手（rule 82 红线）
      - --userdata=<路径>：显式指定 userData 目录（默认从 package.json 推断 name/productName/appId）

变更史：
    v3.9.12 初版（galagame 教训：调用 skill 但骨架流程被跳过）
    v3.14.0 增 render-silent-fail（rule 79 五项静默失效检查）
    v3.14.1 增 product-assert（rule 79 第六项产物级断言）
    v3.16.0 增 active-tree（rule 82 ① 四证据）+ product-assert 时序与稳定性（打包进程/两次采样/
            zip>asar）+ 产物目录选择兼容 dist-v3 / dist-v4 这类带后缀命名 + 报告头带运行时探针行
            + self-test 引擎自检（rule 64 回归网：17 条用例全在 tempfile 沙箱现造现跑）

    python six_layer_check.py self-test [--json] [--strict] [--keep-tmp]
    - 引擎自检（rule 64 回归网 · v3.16.0 新增）：把"真跑才发现"的历史问题固化成 17 条用例——
      全脚本可编译 / 运行时探针正反用例 / 活跃树四证据与死树识别 / 双树对比判定 /
      product-assert 目录优选·归档时序·两次采样·空洞 PASS / render-silent-fail 噪音剪枝·UI 域·DOM 白名单 /
      三件套正反向用例（含 exit code）/ **GBK 环境无 Traceback**（PYTHONIOENCODING=gbk 子进程复现）/
      分发脚本语法（缺 bash → SKIP 记未验证）。fixture 全在 tempfile 沙箱现造现删。
      - 退出码：0=无 FAIL；1=有 FAIL（--strict 时 SKIP 也算不通过）
      - --keep-tmp 保留沙箱供排查；**改引擎后必跑本条**，红了就知道哪条能力回归了

退出码：0=检查完成（非 strict） / 1=有缺失或 strict 判定不达标 / 2=目录不存在
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

# 检查项定义：(key, 名称, 目标路径/glob, 阶段, 说明)
# 阶段: init=开工前应备, deliver=收尾应备, both=全程
CHECKS = [
    ("git_repo",       "git 仓库（Phase 0 版本控制前置）",  ".git",              "init",
     "rule 11：无 git 禁止高风险开发"),
    ("git_baseline",   "git 已有提交基线",                  "git_commits",       "init",
     "rule 11：有仓库但无基线提交 = 未初始化"),
    ("knowledge_dir",  "知识资产目录（Phase 0.5）",          ("knowledge", "知识经验"), "init",
     "rule 11.1-11.4：防文件腐烂，缺则 read_knowledge 无入口"),
    ("knowledge_index","知识索引 _index.md",                ("knowledge/_index.md", "知识经验/_index.md"), "init",
     "rule 11.1：唯一入口路由表，缺失 = Phase 0.5 未初始化"),
    ("spec",           "spec.md（SDD 四件套）",             ("spec.md",),        "init",
     "rule 7：生产级/多模块项目应规格先行（可选）"),
    ("plan",           "plan.md",                           ("plan.md",),        "init", "rule 7"),
    ("tasks",          "tasks.md",                          ("tasks.md",),       "init", "rule 7"),
    ("constitution",   "constitution.md",                   ("constitution.md",), "init", "rule 7"),
    ("lessons",        "lessons.md（教训文件）",             ("lessons.md",),     "both",
     "rule 32/40：失败教训写入，重开先读"),
    ("cost_log",       "cost_log.md（成本账本）",            ("cost_log.md",),    "both",
     "rule 38/53：定长记录可 grep，异常类型列必填"),
    ("progress",       "progress.json（断点+三态）",         ("progress.json",),  "both",
     "rule 39：预期产物清单 + lifecycle 字段"),
    ("interfaces",     "interfaces.md（接口契约）",          ("interfaces.md",),  "both",
     "rule 18：并行对接唯一保障（单模块项目可无）"),
    ("phase_marks",    "PHASE_*_DONE/FAILED 标记",          "phase_marks",       "both",
     "rule 56：解析失败写 PHASE_X_FAILED，完成写 DONE"),
    ("memory_logs",    ".workbuddy/memory/ 过程日志",       ".workbuddy/memory", "both",
     "rule 66：过程文档先行，跨会话进 YYYY-MM-DD.md"),
    ("project_memory", ".workbuddy/memory/MEMORY.md",       ".workbuddy/memory/MEMORY.md", "deliver",
     "rule 66：长期项目约定沉淀"),
    ("handover_doc",   "交接文档.md（收尾强制）",           ("交接文档.md",),    "deliver",
     "全局收尾规则：项目根目录交接文档"),
    ("strategy_map",   "战略图.svg/html（收尾强制）",       ("战略图.svg", "战略图.html", "战略图.md"), "deliver",
     "全局收尾规则：进度/范围可视化"),
]


def _glob_exists(root: Path, patterns) -> bool:
    """任意一个路径/glob 存在即 True"""
    if isinstance(patterns, str):
        patterns = (patterns,)
    for p in patterns:
        # 目录存在性
        if (root / p).exists():
            return True
        # 带通配符则 glob
        if any(c in p for c in "*?"):
            if list(root.glob(p)):
                return True
    return False


def _git_has_commits(root: Path) -> bool:
    try:
        r = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--verify", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        return r.returncode == 0
    except Exception:
        return False


def _phase_marks_exist(root: Path) -> bool:
    return bool(list(root.glob("PHASE_*_DONE")) or list(root.glob("PHASE_*_FAILED")))


def check(project_dir: str, mode: str = "auto") -> dict:
    root = Path(project_dir)
    if not root.is_dir():
        return {"ok": False, "error": f"目录不存在: {project_dir}", "items": []}

    items = []
    missing = []
    for key, name, target, phase, note in CHECKS:
        if mode != "auto" and phase not in ("both", mode):
            continue
        if key == "git_baseline":
            exists = _git_has_commits(root)
        elif key == "phase_marks":
            exists = _phase_marks_exist(root)
        else:
            exists = _glob_exists(root, target)
        items.append({
            "key": key, "name": name, "phase": phase,
            "exists": exists, "note": note,
        })
        if not exists:
            missing.append(f"  ✗ [{phase}] {name}  <-  {note}")
    return {"ok": True, "root": str(root), "mode": mode, "items": items, "missing": missing}


def render_report(res: dict) -> str:
    if not res.get("ok"):
        return f"[six_layer_check] {res.get('error')}"
    lines = [f"[six_layer_check] 项目: {res['root']}  模式: {res['mode']}"]
    for it in res["items"]:
        mark = "✓" if it["exists"] else "✗"
        lines.append(f"  {mark} [{it['phase']:7s}] {it['name']}")
    missing = res.get("missing") or []
    if missing:
        lines.append("缺失项（= 框架骨架被跳过的证据）：")
        lines.extend(missing)
        lines.append("→ 开工前缺失：应补 Phase 0（git 基线）/ Phase 0.5（知识资产初始化 + read_knowledge 召回）")
        lines.append("→ 收尾缺失：应补 Phase 5 收尾核对（rule 51）+ Phase 7 蒸馏（六步含人工 Gate）")
    else:
        lines.append("✓ 全部检查项就绪")
    return "\n".join(lines)


# ---------- 渲染端静默失效五项检查（rule 79 · v3.14.0 新增） ----------
# 来源：2026-09-05 家俊 Electron 实战复盘硬伤2——Tailwind content 漏扫导致
# typecheck 绿 / build 绿 / 运行不崩，但 UI 全没样式，三轮才定位根因。
# 同类"静默失效"藏在五处配置里，本子命令一次扫完。
# 注意：这里做的是"计数/覆盖比对"，与上面 CHECKS 的"文件存在性"是两类检查，
# 不塞进 CHECKS 列表，独立成函数（Plan 评审结论）。

_SCAN_EXCLUDES = {"node_modules", ".git", "dist", "build", "out", "release",
                  "coverage", ".workbuddy", "archive", "__pycache__"}
# 前缀剪枝（v3.16.0 噪音治理）：out-old-2026…/out-rt4/dist-v3/dist-v4/tmp_memtest 这类
# 历史产物与临时目录不进源码遍历——rule 79 v3.15.0 实测：它们混入 tailwind content 比较域，
# 使 FAIL 列表充满噪音、真问题被淹没。
_SCAN_EXCLUDE_PREFIXES = ("dist", "out", "build", "release", "coverage", "tmp", "temp",
                          "archive", "old", "bak")
_SRC_EXTS = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".svelte"}
_UI_EXTS = {".tsx", ".jsx", ".html", ".vue", ".svelte", ".css"}


def _is_scan_excluded(name: str) -> bool:
    """剪枝判定：精确名 + 前缀 + 点目录"""
    if name in _SCAN_EXCLUDES or name.startswith("."):
        return True
    return name.lower().startswith(_SCAN_EXCLUDE_PREFIXES)


def _walk_src(root: Path):
    """遍历源码文件（剪枝 node_modules/dist*/out-*/tmp* 等），yield (Path, 相对posix路径)"""
    for dirpath, dirnames, filenames in os.walk(root):
        rel = Path(dirpath).relative_to(root)
        dirnames[:] = [d for d in dirnames if not _is_scan_excluded(d)]
        for fn in filenames:
            yield Path(dirpath) / fn, (rel / fn).as_posix() if str(rel) != "." else fn


def _iter_source_dirs(root: Path) -> set:
    """收集含源码/html 文件的目录（相对 posix 路径）"""
    dirs = set()
    for p, relp in _walk_src(root):
        if Path(relp).suffix.lower() in _SRC_EXTS | {".html"}:
            dirs.add(str(Path(relp).parent.as_posix()) if str(Path(relp).parent) != "." else ".")
    return dirs


def _glob_prefix(glob_pat: str) -> str:
    """把 glob 模式归约为'目录前缀'：./src/**/*.{js,ts} → src；src/*.{js,ts} → src；**/* → 空(覆盖一切)"""
    g = glob_pat.replace("\\", "/").strip()
    while g.startswith("./"):
        g = g[2:]
    i = g.find("/**")
    if i != -1:
        return g[:i].rstrip("/")
    g = re.sub(r"/\*.*$", "", g)   # 剥 /*、/*.{...}、/*.ts
    g = re.sub(r"\*.*$", "", g)    # 剥裸 * 开头
    return g.rstrip("/")


def _glob_covers(glob_pat: str, src_dir: str) -> bool:
    """近似判定 glob 是否覆盖某源码目录（宽进严出：有前缀关系即算覆盖，宁漏报不误报）"""
    g = _glob_prefix(glob_pat)
    if not g or g in ("**", "*"):
        return True
    d = src_dir.strip("/")
    if not d or d == ".":
        return True
    return d == g or d.startswith(g + "/") or g.startswith(d + "/")


def _check_tsconfig(root: Path, src_dirs: set) -> dict:
    name = "tsconfig include 覆盖源码目录"
    files = sorted(root.glob("tsconfig*.json"))
    if not files:
        return {"key": "tsconfig", "name": name, "status": "SKIP",
                "detail": "未找到 tsconfig*.json（可能不用 TS）"}
    patterns = []
    for f in files:
        try:
            txt = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        txt = re.sub(r"/\*.*?\*/", "", txt, flags=re.S)      # 去 jsonc 块注释
        txt = re.sub(r"^\s*//.*$", "", txt, flags=re.M)      # 去行注释
        try:
            cfg = json.loads(txt)
        except Exception:
            continue
        co = cfg.get("compilerOptions", {})
        patterns.extend(co.get("include") or [])
        patterns.extend(co.get("files") or [])
        if co.get("extends") and not patterns:
            return {"key": "tsconfig", "name": name, "status": "SKIP",
                    "detail": f"{f.name} extends {co['extends']}，include 在基配置中，需人工确认"}
    if not patterns:
        return {"key": "tsconfig", "name": name, "status": "PASS",
                "detail": "未显式 include/files（TS 默认包含全部）"}
    code_dirs = sorted(d for d in src_dirs if d != ".")
    uncovered = [d for d in code_dirs if not any(_glob_covers(p, d) for p in patterns)]
    if uncovered:
        return {"key": "tsconfig", "name": name, "status": "FAIL",
                "detail": "以下源码目录不在 include/files 内（typecheck 对其假绿，参照 R-008）: "
                          + ", ".join(uncovered)}
    return {"key": "tsconfig", "name": name, "status": "PASS",
            "detail": f"{len(patterns)} 个模式覆盖 {len(code_dirs)} 个源码目录"}


def _check_vite_input(root: Path) -> dict:
    name = "vite 多入口 input 登记"
    cfg_path = None
    for ext in ("ts", "js", "mjs", "cjs"):
        p = root / f"vite.config.{ext}"
        if p.exists():
            cfg_path = p
            break
    htmls = sorted(relp for _, relp in _walk_src(root)
                   if relp.lower().endswith(".html"))
    if not htmls:
        return {"key": "vite", "name": name, "status": "SKIP",
                "detail": "项目内无 html 入口"}
    if cfg_path is None:
        return {"key": "vite", "name": name, "status": "SKIP",
                "detail": "未找到 vite.config.*（可能不用 vite）"}
    txt = cfg_path.read_text(encoding="utf-8", errors="ignore")
    has_input = re.search(r"\binput\s*[:=]", txt)
    if len(htmls) == 1 and not has_input:
        return {"key": "vite", "name": name, "status": "PASS",
                "detail": "单入口，vite 默认 index.html"}
    if len(htmls) > 1 and not has_input:
        return {"key": "vite", "name": name, "status": "FAIL",
                "detail": f"发现 {len(htmls)} 个 html 但 vite 配置无 rollupOptions.input"
                          f"（新窗口不打包→加载 404 静默白屏）: {', '.join(htmls)}"}
    missing = [h for h in htmls if Path(h).name not in txt and h not in txt]
    if missing:
        return {"key": "vite", "name": name, "status": "FAIL",
                "detail": "以下 html 未出现在 vite input 中（不会被打包）: " + ", ".join(missing)}
    return {"key": "vite", "name": name, "status": "PASS",
            "detail": f"{len(htmls)} 个入口均已登记"}


def _ui_dirs(root: Path) -> set:
    """UI 目录（含 .tsx/.jsx/.html/.vue/.svelte/.css）——tailwind content 的比较域。
    排除 scripts/、tools/、纯 .ts 目录：rule 79 v3.15.0 实测噪音源（非 UI 目录混入比较域）。"""
    ui = set()
    for _, relp in _walk_src(root):
        if Path(relp).suffix.lower() in _UI_EXTS:
            parent = str(Path(relp).parent.as_posix())
            ui.add(parent if parent != "." else ".")
    return ui


def _check_tailwind_content(root: Path, src_dirs: set) -> dict:
    name = "tailwind content 覆盖源码目录"
    cfg_path = None
    for ext in ("js", "ts", "cjs", "mjs"):
        p = root / f"tailwind.config.{ext}"
        if p.exists():
            cfg_path = p
            break
    if cfg_path is None:
        for _, relp in _walk_src(root):
            if relp.lower().endswith(".css"):
                try:
                    if "tailwindcss" in (root / relp).read_text(encoding="utf-8", errors="ignore"):
                        return {"key": "tailwind", "name": name, "status": "SKIP",
                                "detail": "检测到 tailwind v4 CSS-first（@import \"tailwindcss\"），"
                                          "content 由 @source 管理，需人工核对"}
                except Exception:
                    pass
        return {"key": "tailwind", "name": name, "status": "SKIP",
                "detail": "未找到 tailwind.config.*（可能未用 tailwind）"}
    txt = cfg_path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"content\s*:\s*\[(.*?)\]", txt, flags=re.S)
    if not m:
        return {"key": "tailwind", "name": name, "status": "SKIP",
                "detail": "配置中未解析到 content 数组（可能用 preset），需人工确认"}
    pats = re.findall(r"['\"`]([^'\"`]+)['\"`]", m.group(1))
    code_dirs = sorted(d for d in _ui_dirs(root) if d != ".")   # UI 比较域（剪枝 scripts/tools/产物目录噪音）
    uncovered = [d for d in code_dirs if not any(_glob_covers(p, d) for p in pats)]
    if uncovered:
        return {"key": "tailwind", "name": name, "status": "FAIL",
                "detail": "以下 UI 目录不在 content 覆盖内（UI 样式静默丢失，硬伤2 三轮根因）: "
                          + ", ".join(uncovered) + f"（当前 {len(pats)} 个模式：{'; '.join(pats)}）"
                          + "；已按 v3.16.0 剪枝 dist*/out-*/tmp*/build* 类噪音"}
    return {"key": "tailwind", "name": name, "status": "PASS",
            "detail": f"{len(pats)} 个 content 模式覆盖 {len(code_dirs)} 个源码目录"}


# DOM 标准成员（window.document/location…）与浏览器构造器（window.HTMLInputElement…）不是 preload
# 命名空间——计入会制造"狼来了"误报（rule 79 v3.15.0：误报一次开发者永久 --skip）。
_DOM_WINDOW_MEMBERS = {
    "document", "location", "navigator", "history", "screen", "frames", "parent", "top", "self",
    "window", "globalThis", "console", "performance", "crypto", "localStorage", "sessionStorage",
    "indexedDB", "innerWidth", "innerHeight", "outerWidth", "outerHeight", "devicePixelRatio",
    "scrollX", "scrollY", "pageXOffset", "pageYOffset", "setTimeout", "setInterval",
    "clearTimeout", "clearInterval", "requestAnimationFrame", "cancelAnimationFrame",
    "getComputedStyle", "matchMedia", "fetch", "alert", "confirm", "prompt", "open", "close",
    "addEventListener", "removeEventListener", "dispatchEvent", "focus", "blur", "print", "stop",
}
_DOM_CTOR_RE = re.compile(
    r"^(?:HTML|SVG|CSS|DOM|XML|Math|JSON|Intl|WebGL|Audio|Image|Text|Element|Node|Event|Path|"
    r"URL|File|Blob|FormData|Date|RegExp|Request|Response|Headers|Abort|Message|Worker)")


def _check_preload_dts(root: Path) -> dict:
    name = "preload window.* 引用均有类型声明"
    refs = set()
    dts_files = []
    for p, relp in _walk_src(root):
        suffix = Path(relp).suffix.lower()
        if relp.lower().endswith(".d.ts"):
            dts_files.append(p)
            continue
        if suffix in _SRC_EXTS | {".html"}:
            try:
                txt = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for mm in re.finditer(r"window\.(\w+)\.", txt):
                refs.add(mm.group(1))
    if not refs:
        return {"key": "preload", "name": name, "status": "SKIP",
                "detail": "renderer 未引用 window.*（可能经 import 暴露）"}
    if not dts_files:
        return {"key": "preload", "name": name, "status": "FAIL",
                "detail": f"renderer 引用了 window.{sorted(refs)[0]}.* 等，但项目无任何 .d.ts 声明"
                          f"（preload 类型假绿，改 API 名不会报错）"}
    declared = set()
    for p in dts_files:
        txt = p.read_text(encoding="utf-8", errors="ignore")
        for mm in re.finditer(r"(\w+)\s*:\s*\{", txt):
            declared.add(mm.group(1))
        for mm in re.finditer(r"(?:readonly\s+)?(\w+)\s*[:(]", txt):
            declared.add(mm.group(1))
    missing = sorted(r for r in refs if r not in declared
                     and r not in _DOM_WINDOW_MEMBERS and not _DOM_CTOR_RE.match(r))
    if missing:
        return {"key": "preload", "name": name, "status": "FAIL",
                "detail": "以下 window.* 命名空间未在任何 d.ts 中声明: " + ", ".join(missing)
                          + "（DOM 标准成员/构造器已白名单排除）"}
    return {"key": "preload", "name": name, "status": "PASS",
            "detail": f"{len(refs)} 个 window.* 命名空间均有声明（{len(dts_files)} 个 d.ts）"}


def _check_ipc_consistency(root: Path) -> dict:
    name = "IPC 通道 preload↔main 集合一致"
    main_ch, preload_ch = set(), set()
    found = False
    for p, relp in _walk_src(root):
        if Path(relp).suffix.lower() not in _SRC_EXTS:
            continue
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        txt = re.sub(r"/\*.*?\*/|^\s*//.*$", "", txt, flags=re.S | re.M)  # 去注释
        if "ipcMain" in txt:
            for mm in re.finditer(r"ipcMain\.(?:handle|on)\(\s*['\"`]([\w:.\-/]+)['\"`]", txt):
                main_ch.add(mm.group(1))
                found = True
        if "ipcRenderer" in txt:
            for mm in re.finditer(r"ipcRenderer\.(?:invoke|send|on)\(\s*['\"`]([\w:.\-/]+)['\"`]", txt):
                preload_ch.add(mm.group(1))
                found = True
    if not found:
        return {"key": "ipc", "name": name, "status": "SKIP",
                "detail": "未发现字符串字面量通道（可能经常量注册或不用 IPC）"}
    orphan_pre = sorted(preload_ch - main_ch)
    orphan_main = sorted(main_ch - preload_ch)
    if orphan_pre:
        extra = f"；另有未被调用的 handler: {', '.join(orphan_main)}" if orphan_main else ""
        return {"key": "ipc", "name": name, "status": "FAIL",
                "detail": "preload 调用但主进程未注册（invoke 静默无响应）: "
                          + ", ".join(orphan_pre) + extra}
    if orphan_main:
        return {"key": "ipc", "name": name, "status": "FAIL",
                "detail": "主进程注册但 preload 未调用（疑似僵尸 handler，参照 R-007）: "
                          + ", ".join(orphan_main)}
    return {"key": "ipc", "name": name, "status": "PASS",
            "detail": f"两侧通道一致（{len(main_ch)} 条）"}


def check_render_silent_fail(project_dir: str) -> dict:
    """渲染端静默失效五项检查（rule 79）。配置存在才查，不存在 SKIP 防误报。"""
    root = Path(project_dir)
    if not root.is_dir():
        return {"ok": False, "error": f"目录不存在: {project_dir}"}
    src_dirs = _iter_source_dirs(root)
    items = [
        _check_tsconfig(root, src_dirs),
        _check_vite_input(root),
        _check_tailwind_content(root, src_dirs),
        _check_preload_dts(root),
        _check_ipc_consistency(root),
    ]
    return {"ok": True, "root": str(root), "mode": "render-silent-fail",
            "items": items,
            "fail_count": sum(1 for r in items if r["status"] == "FAIL"),
            "skip_count": sum(1 for r in items if r["status"] == "SKIP")}


def render_silent_fail_report(res: dict) -> str:
    lines = [f"[six_layer_check] 项目: {res['root']}  模式: {res['mode']}"
             f"（渲染端静默失效五项 · rule 79）"]
    for it in res["items"]:
        mark = {"PASS": "✓", "FAIL": "✗", "SKIP": "-"}.get(it["status"], "?")
        if it["status"] == "PASS":
            lines.append(f"  {mark} [{it['status']:4s}] {it['name']}  ({it['detail']})")
        else:
            lines.append(f"  {mark} [{it['status']:4s}] {it['name']}  <-  {it['detail']}")
    if res["fail_count"]:
        lines.append(f"✗ 发现 {res['fail_count']} 项静默失效隐患"
                     f"（SKIP {res['skip_count']} 项需人工复核）")
        lines.append("→ 处置对照 references/symptom_triage.md 卡2/卡3；知识库 R-008（类型门禁假绿）+ R-010")
    else:
        lines.append(f"✓ 五项检查通过（SKIP {res['skip_count']} 项：配置不存在，未触发）")
    return "\n".join(lines)


# ---------- 产物级断言（rule 79 第六项 · v3.14.1 新增） ----------
# 来源：2026-09-05 研讨会收敛（4 HT × 2 轮）——build 绿 ≠ 产物真的含所需样式/字面量。
# Tailwind content 漏扫实测四轮才定位，根因是"从没 grep 过产物 CSS"。
# 红队裁决（狼来了防线）：纯 Tailwind 项目硬阻断；检测到 CSS Modules/CSS-in-JS
# 共存 → 降级 WARN（类名 hash 会误报）；--force-with-reason 留痕跳过。

_PROD_DIRS = ("dist", "build", "out", "release")
_TAILWIND_PREFIXES = ("bg-", "text-", "border-", "p-", "px-", "py-", "pt-", "pb-", "pl-", "pr-",
                      "m-", "mx-", "my-", "mt-", "mb-", "ml-", "mr-", "w-", "h-", "min-w-", "max-w-",
                      "gap-", "rounded-", "shadow-", "font-", "leading-", "tracking-", "opacity-",
                      "z-", "top-", "right-", "bottom-", "left-", "inset-", "flex-", "grid-", "gap-")


def _latest_mtime(root: Path, dirs, exts=None) -> float:
    latest = 0.0
    for dirpath, dirnames, filenames in os.walk(root):
        rel_parts = Path(dirpath).relative_to(root).parts
        if any(_is_scan_excluded(p) for p in rel_parts):
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if not _is_scan_excluded(d)]
        for fn in filenames:
            if exts and Path(fn).suffix.lower() not in exts:
                continue
            try:
                m = (Path(dirpath) / fn).stat().st_mtime
                if m > latest:
                    latest = m
            except OSError:
                pass
    return latest


def _extract_expected_classes(root: Path) -> set:
    """从源码 class/className 字面量提取疑似 tailwind utility 类（动态类取静态前缀）"""
    expected = set()
    class_pat = re.compile(r"""class(?:Name)?\s*=\s*["'`]([^"'`]+)["'`]""")
    for p, relp in _walk_src(root):
        if Path(relp).suffix.lower() not in {".tsx", ".jsx", ".ts", ".js", ".html", ".vue", ".svelte"}:
            continue
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        txt = re.sub(r"/\*.*?\*/|^\s*//.*$", "", txt, flags=re.S | re.M)
        for mm in class_pat.finditer(txt):
            for tok in mm.group(1).split():
                if "${" in tok:
                    tok = tok.split("${")[0].rstrip("-")  # 动态类取静态前缀：bg-${c} → bg
                tok = tok.split(":")[-1]                  # 剥变体前缀 hover:bg-x → bg-x
                if any(tok.startswith(pre) or tok == pre[:-1] for pre in _TAILWIND_PREFIXES) and len(tok) > 2:
                    expected.add(tok)
    return expected


def _class_in_css(css_text: str, cls: str) -> bool:
    """字面量或 CSS 转义形式任一命中"""
    if cls in css_text:
        return True
    esc = cls.replace("[", r"\[").replace("]", r"\]").replace(":", r"\:").replace("/", r"\/").replace(".", r"\.")
    return esc in css_text


# ---------- 时序与稳定性（rule 79 第六项 · v3.16.0 扩展） ----------
# 来源：2026-09-12 番茄宠物V2 打包实战——打包**进行中**采样会拿到中间态
# （实测 asar 274→287MB / zip 256→268MB 变化中），据此下结论 = 假证据。
# 三条断言：① 打包进程探针（app-builder/7za/makensis 还在跑 → 别断言）
#          ② 产物尺寸两次采样必须相等（不等 = 中间态 → 断言无效）
#          ③ zip/安装器 mtime > asar mtime（归档装的是最终产物，否则是坏包）

_PACK_PROCESSES = ("app-builder.exe", "7za.exe", "7z.exe", "makensis.exe", "makensisw.exe")
_ARCHIVE_EXTS = {".zip", ".7z", ".msi", ".dmg", ".appimage", ".nsis"}


def _fmt_mtime(m: float) -> str:
    return datetime.fromtimestamp(m).strftime("%m-%d %H:%M:%S") if m else "-"


def _pack_processes() -> tuple:
    """探测打包进程：返回 (status, [进程名])；无法探测 → SKIP（不静默当 PASS）"""
    try:
        if os.name == "nt":
            r = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True,
                               text=True, timeout=20, encoding="utf-8", errors="replace")
            if r.returncode != 0:
                return "SKIP", []
            low = (r.stdout or "").lower()
            hits = [p for p in _PACK_PROCESSES if p in low]
            return ("WARN", hits) if hits else ("PASS", [])
        r = subprocess.run(["ps", "-eo", "comm"], capture_output=True, text=True, timeout=10,
                           encoding="utf-8", errors="replace")
        low = (r.stdout or "").lower()
        hits = [p for p in ("app-builder", "7za", "makensis") if p in low]
        return ("WARN", hits) if hits else ("PASS", [])
    except Exception:
        return "SKIP", []


def _tree_size(root: Path) -> tuple:
    """(总字节, 文件数, 最新 mtime)——产物尺寸采样用（rule 79 两次采样）"""
    total = 0
    count = 0
    newest = 0.0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for fn in filenames:
            try:
                st = (Path(dirpath) / fn).stat()
            except OSError:
                continue
            total += st.st_size
            count += 1
            newest = max(newest, st.st_mtime)
    return total, count, newest


def _find_archives(prod_dir: Path) -> list:
    """归档类产物（zip/7z/msi/dmg/安装器 exe）；排除 *-unpacked/ 下的应用主程序"""
    out = []
    for f in prod_dir.rglob("*"):
        if not f.is_file():
            continue
        suf = f.suffix.lower()
        if suf in _ARCHIVE_EXTS:
            out.append(f)
        elif suf == ".exe" and "unpacked" not in str(f).lower():
            out.append(f)
    return out


def _check_pack_timing(prod_dir: Path) -> list:
    """rule 79 第六项 · v3.16.0：时序与稳定性三项断言（返回 items 片段）"""
    items = []
    # ① 打包进程探针
    st, procs = _pack_processes()
    if st == "WARN":
        items.append({"key": "pack_proc", "name": "打包进程探针", "status": "WARN",
                      "detail": f"检测到打包进程仍在运行（{', '.join(procs)}）——等打包退出再断言，"
                                f"否则拿到的是中间态"})
    elif st == "PASS":
        items.append({"key": "pack_proc", "name": "打包进程探针", "status": "PASS",
                      "detail": "无打包进程在跑"})
    else:
        items.append({"key": "pack_proc", "name": "打包进程探针", "status": "SKIP",
                      "detail": "无法探测（tasklist/ps 不可用）——需人工确认打包已退出"})
    # ② 尺寸两次采样（不等 = 中间态 = 断言无效）
    s1 = _tree_size(prod_dir)
    time.sleep(0.8)
    s2 = _tree_size(prod_dir)
    if s1[:2] != s2[:2]:
        items.append({"key": "stability", "name": "产物稳定性（两次采样）", "status": "FAIL",
                      "detail": f"产物仍在变化：采样1={s1[0]}B/{s1[1]}文件 → 采样2={s2[0]}B/{s2[1]}文件"
                                f"——断言的是中间态，结论无效；等打包结束重跑"})
    else:
        items.append({"key": "stability", "name": "产物稳定性（两次采样）", "status": "PASS",
                      "detail": f"两次采样一致（{s2[0]}B / {s2[1]} 文件）"})
    # ③ zip > asar 归档时序
    asars = [f for f in prod_dir.rglob("app.asar") if f.is_file()]
    archives = _find_archives(prod_dir)
    if asars and archives:
        a_m = max(f.stat().st_mtime for f in asars)
        z = max(archives, key=lambda f: f.stat().st_mtime)
        z_m = z.stat().st_mtime
        if z_m < a_m:
            items.append({"key": "time_order", "name": "归档时序（zip > asar）", "status": "FAIL",
                          "detail": f"归档（{z.name} {_fmt_mtime(z_m)}）早于 asar（{_fmt_mtime(a_m)}）"
                                    f"——归档装的是旧产物 = 坏包；重跑完整打包流水线"})
        else:
            items.append({"key": "time_order", "name": "归档时序（zip > asar）", "status": "PASS",
                          "detail": f"{z.name} {_fmt_mtime(z_m)} > app.asar {_fmt_mtime(a_m)}"})
    else:
        items.append({"key": "time_order", "name": "归档时序（zip > asar）", "status": "SKIP",
                      "detail": f"缺一侧（asar={len(asars)} 归档={len(archives)}）——仅 unpacked 时跳过"})
    return items


def _pick_prod_dir(root: Path):
    """选产物目录，返回 (可交付产物目录 | None, CSS 扫描目录 | None, [全部候选名])。

    规则（2026-09-12 实战暴露两处误选后定）：
    - 候选 = 精确名（dist/build/out/release）+ 带后缀命名（dist-v3/dist-v4/build-win…），
      排除 distribution/（只有预置文件）；旧版只认精确名 → dist-v3/dist-v4 误报 SKIP。
    - **可交付产物优先**：含 .exe/.asar/.zip 等打包件的目录 > 纯构建输出目录（out/ 这类
      electron-vite 中间产物不应盖过 dist/ 里的安装包）；同级取最新。
    - **CSS 单独选**：Tier A 断言要 grep 文本 CSS，asar 内的 CSS 不可读 →
      在含 .css 的候选中取最新（可交付目录与 CSS 目录可不同，报告里分别标注）。"""
    pkg_exts = {".exe", ".asar", ".zip", ".7z", ".msi", ".dmg", ".appimage"}
    art_exts = pkg_exts | {".js", ".css", ".html"}
    cands = []
    for d in root.iterdir():
        if not d.is_dir() or d.name.startswith("."):
            continue
        n = d.name.lower()
        if n in ("distribution", "distribute", "dist-src"):
            continue
        if not (n in _PROD_DIRS or n.startswith("dist") or n.startswith("build")
                or n.startswith("release") or n.startswith("out-")):
            continue
        newest, has_pkg, has_css = 0.0, False, False
        for dirpath, dirnames, filenames in os.walk(d):
            dirnames[:] = [x for x in dirnames if x not in _SCAN_EXCLUDES and not x.startswith(".")]
            for fn in filenames:
                p = Path(dirpath) / fn
                suf = p.suffix.lower()
                if suf not in art_exts:
                    continue
                try:
                    newest = max(newest, p.stat().st_mtime)
                except OSError:
                    continue
                if suf in pkg_exts:
                    has_pkg = True
                if suf == ".css":
                    has_css = True
        if newest > 0.0:
            cands.append({"path": d, "m": newest, "pkg": has_pkg, "css": has_css})
    if not cands:
        return None, None, []
    names = sorted(c["path"].name for c in cands)
    pool = [c for c in cands if c["pkg"]] or cands
    prod = max(pool, key=lambda c: (c["m"], c["path"].name))
    css_pool = [c for c in cands if c["css"]] or [prod]
    css_dir = max(css_pool, key=lambda c: (c["m"], c["path"].name))["path"]
    return prod["path"], css_dir, names


def check_product_assert(project_dir: str) -> dict:
    """产物级断言（rule 79 第六项）：build 产物 grep 断言。纯 Tailwind 硬阻断，共存 WARN。"""
    root = Path(project_dir)
    if not root.is_dir():
        return {"ok": False, "error": f"目录不存在: {project_dir}"}
    prod_dir, css_dir, prod_cands = _pick_prod_dir(root)
    if prod_dir is None:
        return {"ok": True, "root": str(root), "mode": "product-assert", "forced_skip": None,
                "items": [{"key": "product", "name": "构建产物目录", "status": "SKIP",
                           "detail": "未找到 dist*/build*/out*/release*/ 产物目录——先 build 再断言"}],
                "fail_count": 0, "skip_count": 1, "warn_count": 0}

    items = []
    # 陈旧产物告警
    src_mtime = _latest_mtime(root, None, exts={".ts", ".tsx", ".js", ".jsx", ".css", ".html", ".vue"})
    try:
        prod_mtime = max((f.stat().st_mtime for f in prod_dir.rglob("*") if f.is_file()), default=0.0)
    except OSError:
        prod_mtime = 0.0
    if src_mtime and prod_mtime and prod_mtime < src_mtime:
        items.append({"key": "stale", "name": "产物新鲜度", "status": "WARN",
                      "detail": "产物目录早于源码修改（陈旧产物）——先重新 build 再断言，否则断言的是旧产物"})
    if len(prod_cands) > 1:
        others = [n for n in prod_cands if n not in (prod_dir.name, css_dir.name)]
        items.append({"key": "pick", "name": "产物目录选择", "status": "PASS",
                      "detail": f"可交付产物选 {prod_dir.name}/"
                                + (f"；CSS 扫描 {css_dir.name}/" if css_dir and css_dir != prod_dir else "")
                                + (f"；其他候选：{', '.join(others)}" if others else "")})
    # v3.16.0：时序与稳定性（打包进程 / 两次采样 / zip>asar）——打包进行中采样 = 假证据
    items.extend(_check_pack_timing(prod_dir))

    # Tier A 的 CSS 文本从 css_dir 读（asar 内的 CSS 不可读；可交付目录与 CSS 目录可不同）
    css_text = ""
    css_files = list(css_dir.rglob("*.css")) if css_dir else []
    for f in css_files:
        try:
            css_text += f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            pass

    # Tier A：纯 Tailwind 检测
    tw_cfg = any((root / f"tailwind.config.{e}").exists() for e in ("js", "ts", "cjs", "mjs"))
    if tw_cfg and css_files:
        coexist = []
        for _, relp in _walk_src(root):
            lp = relp.lower()
            if lp.endswith((".module.css", ".module.scss", ".module.less")):
                coexist.append(relp)
            elif lp.endswith((".ts", ".tsx", ".js", ".jsx")):
                try:
                    head = (root / relp).read_text(encoding="utf-8", errors="ignore")[:20000]
                except Exception:
                    continue
                if "styled-components" in head or "@emotion" in head or "styled(" in head:
                    coexist.append(relp)
        if coexist:
            items.append({"key": "tier_a", "name": "Tailwind 产物断言（Tier A）", "status": "WARN",
                          "detail": f"检测到 CSS Modules/CSS-in-JS 共存（{', '.join(coexist[:3])}{'…' if len(coexist) > 3 else ''}）"
                                    f"——类名 hash 会误报，降级 WARN 不阻断；如需硬断言用 Tier B 声明清单"})
        else:
            expected = _extract_expected_classes(root)
            missing = sorted(c for c in expected if not _class_in_css(css_text, c))
            if not expected:
                # 空洞 PASS 识别（rule 79 v3.15.0）：抽到 0 个期望类时"全部命中"是无信息量通过
                items.append({"key": "tier_a", "name": "Tailwind 产物断言（Tier A）", "status": "WARN",
                              "detail": f"抽到 0 个期望 utility 类 = 空洞 PASS（无信息量通过视为未验证）"
                                        f"——CSS 扫描目录 {css_dir.name}/ 可能不含应用样式；"
                                        f"补独立取证：建 product-assert.json（Tier B）或人工 grep 产物 CSS"})
            elif len(missing) >= 3:
                items.append({"key": "tier_a", "name": "Tailwind 产物断言（Tier A · 纯 Tailwind 硬 Gate）", "status": "FAIL",
                              "detail": f"产物 CSS 缺失 {len(missing)} 个源码引用的 utility 类（样式静默丢失）："
                                        + ", ".join(missing[:10]) + ("…" if len(missing) > 10 else "")})
            elif missing:
                items.append({"key": "tier_a", "name": "Tailwind 产物断言（Tier A）", "status": "PASS",
                              "detail": f"{len(expected)} 个期望类中 {len(missing)} 个未命中（<3 视为噪声）: " + ", ".join(missing)})
            else:
                items.append({"key": "tier_a", "name": "Tailwind 产物断言（Tier A）", "status": "PASS",
                              "detail": f"{len(expected)} 个期望 utility 类全部命中产物 CSS（{css_dir.name}/）"})

    # Tier B：作者声明清单（product-assert.json）
    pa_file = root / "product-assert.json"
    if pa_file.exists():
        try:
            rules = json.loads(pa_file.read_text(encoding="utf-8"))
        except Exception as e:
            items.append({"key": "tier_b", "name": "声明清单断言（Tier B）", "status": "FAIL",
                          "detail": f"product-assert.json 解析失败: {e}"})
            rules = []
        for i, r in enumerate(rules if isinstance(rules, list) else []):
            pat, contains = r.get("file"), r.get("contains")
            if not pat or not contains:
                items.append({"key": "tier_b", "name": f"声明清单[{i}]", "status": "FAIL",
                              "detail": "条目缺 file 或 contains 字段"})
                continue
            hits = list(prod_dir.glob(pat)) if not (root / pat).exists() else [root / pat]
            blob = ""
            for f in hits:
                try:
                    blob += f.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    pass
            if contains in blob:
                items.append({"key": "tier_b", "name": f"声明清单[{i}] {pat}∋{contains[:30]}", "status": "PASS", "detail": "命中"})
            else:
                items.append({"key": "tier_b", "name": f"声明清单[{i}] {pat}∋{contains[:30]}", "status": "FAIL",
                              "detail": "字面量未出现在产物中（通道名/expose key 静默丢失）"})
    if not any(it["key"] in ("tier_a", "tier_b") for it in items):
        items.append({"key": "product", "name": "产物断言", "status": "SKIP",
                      "detail": "无 tailwind 配置且无 product-assert.json——无可断言项（需要时建 product-assert.json）"})

    fail_count = sum(1 for it in items if it["status"] == "FAIL")
    skip_count = sum(1 for it in items if it["status"] == "SKIP")
    warn_count = sum(1 for it in items if it["status"] == "WARN")
    return {"ok": True, "root": str(root), "mode": "product-assert", "forced_skip": None,
            "items": items, "fail_count": fail_count, "skip_count": skip_count, "warn_count": warn_count}


def render_product_assert_report(res: dict) -> str:
    lines = [f"[six_layer_check] 项目: {res['root']}  模式: {res['mode']}（产物级断言 · rule 79 v3.16.0）"]
    for it in res["items"]:
        mark = {"PASS": "✓", "FAIL": "✗", "SKIP": "-", "WARN": "!"}.get(it["status"], "?")
        lines.append(f"  {mark} [{it['status']:4s}] {it['name']}  <-  {it['detail']}" if it["status"] != "PASS"
                     else f"  {mark} [{it['status']:4s}] {it['name']}  ({it['detail']})")
    if res.get("forced_skip"):
        lines.append(f"⚠️ 已留痕强制跳过: {res['forced_skip']}")
    if res["fail_count"]:
        lines.append(f"✗ 产物断言 {res['fail_count']} 项 FAIL——build 绿 ≠ 产物真的含所需内容（交付 Gate 阻断）")
        lines.append("→ 修复对照 references/symptom_triage.md 卡2；确认无样式需求可 --force-with-reason=理由 留痕跳过")
    elif res["warn_count"]:
        lines.append(f"⚠ 无 FAIL，但有 {res['warn_count']} 项 WARN（空洞 PASS / 中间态 / 共存降级）——"
                     f"按 rule 42 视为未验证：补独立取证，或 --force-with-reason=理由 留痕")
    else:
        lines.append(f"✓ 产物断言通过（FAIL 0 / WARN 0 / SKIP {res['skip_count']}）")
    return "\n".join(lines)


# ---------- 活跃树判定四证据（rule 82 ① · v3.16.0 新增） ----------
# 来源：2026-09-12 番茄宠物V2 实战——交接文档写"活跃目录是独立版、根级是旧备份"，
# 磁盘四证据全指向相反（根级当天 4 个提交 + 09:53 的 exe + %APPDATA% 有运行痕迹；
# 独立版源码停在三周前、对应 userData 不存在）。若照文档执行，10 个修复全打在死树上且不报错。
# 本子命令把"接手那一刻的四证据判定"引擎化；判据与文档冲突 → 以磁盘为准（rule 82 红线）。

def _git_last_commit(root: Path) -> dict:
    try:
        r = subprocess.run(["git", "-C", str(root), "log", "-1", "--date=iso",
                            "--format=%h|%ad|%s"], capture_output=True, text=True, timeout=10,
                           encoding="utf-8", errors="replace")
        if r.returncode != 0:
            return {"ok": False, "detail": "非 git 仓库或无提交"}
        parts = ((r.stdout or "").strip().split("|", 2) + ["", "", ""])[:3]
        return {"ok": bool(parts[0]), "detail": f"{parts[1]} {parts[0]} {parts[2][:60]}"}
    except Exception:
        return {"ok": False, "detail": "git 不可用"}


def _latest_product(root: Path) -> dict:
    """② 构建产物/可执行文件 mtime"""
    best, best_m = None, 0.0
    dirs = []
    for d in (root.iterdir() if root.is_dir() else []):
        if not d.is_dir() or d.name.startswith("."):
            continue
        n = d.name.lower()
        if n in ("distribution",):
            continue
        if n in _PROD_DIRS or n.startswith("dist") or n.startswith("build") or n.startswith("release"):
            dirs.append(d)
    for d in dirs:
        for dirpath, dirnames, filenames in os.walk(d):
            dirnames[:] = [x for x in dirnames if x not in _SCAN_EXCLUDES and not x.startswith(".")]
            for fn in filenames:
                if Path(fn).suffix.lower() in {".exe", ".asar", ".zip", ".7z", ".msi", ".dmg", ".appimage"}:
                    try:
                        m = (Path(dirpath) / fn).stat().st_mtime
                    except OSError:
                        continue
                    if m > best_m:
                        best, best_m = (Path(dirpath) / fn), m
    return {"ok": best is not None, "path": str(best) if best else None, "mtime": best_m,
            "dirs": [d.name for d in dirs]}


def _app_names(root: Path) -> list:
    """userData 目录名候选：package.json 的 name / productName / build.productName / appId 末段"""
    names = []
    pj = root / "package.json"
    if pj.exists():
        try:
            j = json.loads(pj.read_text(encoding="utf-8"))
        except Exception:
            j = {}
        build = j.get("build") if isinstance(j.get("build"), dict) else {}
        for v in (j.get("name"), j.get("productName"), build.get("productName"),
                  j.get("appId"), build.get("appId")):
            if isinstance(v, str) and v.strip():
                names.append(v.strip())
        aid = build.get("appId") or j.get("appId")
        if isinstance(aid, str) and "." in aid:
            names.append(aid.rsplit(".", 1)[-1])
    seen, out = set(), []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def _userdata_evidence(root: Path, override: str = None) -> dict:
    """③ 运行时痕迹（决定性证据）：%APPDATA%/<app> 下文件最新 mtime"""
    bases = [Path(override)] if override else []
    if not bases:
        appdata = os.environ.get("APPDATA")
        local = os.environ.get("LOCALAPPDATA")
        for nm in _app_names(root):
            if appdata:
                bases.append(Path(appdata) / nm)
            if local:
                bases.append(Path(local) / nm)
    for b in bases:
        if not b.is_dir():
            continue
        newest, newest_f, n_files = 0.0, None, 0
        for dirpath, dirnames, filenames in os.walk(b):
            dirnames[:] = [x for x in dirnames if not x.startswith(".")]
            for fn in filenames:
                p = Path(dirpath) / fn
                try:
                    m = p.stat().st_mtime
                except OSError:
                    continue
                n_files += 1
                if m > newest:
                    newest, newest_f = m, p
        if n_files:
            return {"ok": True, "path": str(b), "newest": str(newest_f), "mtime": newest,
                    "files": n_files}
    return {"ok": False, "path": str(bases[0]) if bases else None, "names": _app_names(root)}


def _deps_chain(root: Path) -> dict:
    """④ 依赖与分发链路：node_modules / distribution / electron-builder extraResources"""
    nm = root / "node_modules"
    nm_n = 0
    if nm.is_dir():
        try:
            nm_n = len(list(nm.iterdir()))
        except OSError:
            nm_n = 0
    dist_like = [d.name for d in root.iterdir()
                 if d.is_dir() and d.name in ("distribution", "pack-staging", "pack_staging", "resources")]
    builder, extra = None, False
    for f in ("electron-builder.yml", "electron-builder.yaml", "electron-builder.json"):
        p = root / f
        if p.exists():
            builder = f
            try:
                extra = "extraResources" in p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                pass
            break
    return {"ok": nm.is_dir() or bool(dist_like) or bool(builder), "node_modules": nm_n,
            "dist_dirs": dist_like, "builder": builder, "extra": extra}


def check_active_tree(project_dir: str, userdata: str = None) -> dict:
    root = Path(project_dir)
    if not root.is_dir():
        return {"ok": False, "error": f"目录不存在: {project_dir}"}
    g = _git_last_commit(root)
    p = _latest_product(root)
    u = _userdata_evidence(root, userdata)
    d = _deps_chain(root)
    items = [
        {"key": "git", "name": "① 最近提交（git log --date=iso）",
         "status": "PASS" if g["ok"] else "SKIP", "detail": g["detail"]},
        {"key": "product", "name": "② 构建产物/可执行文件 mtime",
         "status": "PASS" if p["ok"] else "WARN",
         "detail": (f"{p['path']} = {_fmt_mtime(p['mtime'])}" if p["ok"]
                    else "未找到构建产物（dist*/win-unpacked/*.exe / app.asar）")},
        {"key": "userdata", "name": "③ 运行时痕迹（userData db/日志）",
         "status": "PASS" if u["ok"] else "WARN",
         "detail": (f"{u['path']} 最新：{Path(u['newest']).name} = {_fmt_mtime(u['mtime'])}"
                    f"（{u['files']} 个文件）" if u["ok"] else
                    f"未找到 userData 目录（候选：{', '.join(u.get('names') or []) or '无'}）"
                    f"——该树很可能不是用户实际运行的活跃树")},
        {"key": "deps", "name": "④ 依赖与分发链路",
         "status": "PASS" if d["ok"] else "WARN",
         "detail": f"node_modules={d['node_modules']} 项 | 分发目录={'/'.join(d['dist_dirs']) or '无'} | "
                   f"{d['builder'] or '无 electron-builder 配置'}"
                   + ("（extraResources ✓）" if d["extra"] else "")},
    ]
    ev = sum(1 for it in items if it["status"] == "PASS")
    if ev == 4:
        verdict = "✅ 四证据齐——判定为活跃树"
    elif not u["ok"]:
        verdict = "⚠ 缺运行时痕迹（证据③）——非活跃树嫌疑：用户很可能没在跑这棵树（rule 82 实战主信号）"
    elif ev >= 2:
        verdict = f"⚠ 证据 {ev}/4——参照活跃树（信息不足，缺的项先补齐再判定）"
    else:
        verdict = f"✗ 证据仅 {ev}/4——疑似死树/旧备份"
    return {"ok": True, "root": str(root), "mode": "active-tree", "items": items,
            "evidence": ev, "max_evidence": 4, "verdict": verdict,
            "userdata_ok": u["ok"], "product_ok": p["ok"]}


def render_active_tree_report(res: dict) -> str:
    lines = [f"[six_layer_check] 项目: {res['root']}  模式: {res['mode']}"
             f"（活跃树判定四证据 · rule 82 ①）"]
    for it in res["items"]:
        mark = {"PASS": "✓", "FAIL": "✗", "SKIP": "-", "WARN": "!"}.get(it["status"], "?")
        lines.append(f"  {mark} [{it['status']:4s}] {it['name']}  {it['detail']}")
    lines.append(f"  证据 {res['evidence']}/{res['max_evidence']} → {res['verdict']}")
    return "\n".join(lines)


def render_active_tree_compare(results: list) -> str:
    lines = ["=== 活跃树对比（rule 82 ① · 判据与文档冲突时以磁盘为准）==="]
    for r in results:
        if not r.get("ok"):
            lines.append(f"  {r.get('root')}: {r.get('error')}")
            continue
        ud = "userData ✓" if r["userdata_ok"] else "userData ✗"
        pr = "产物 ✓" if r["product_ok"] else "产物 ✗"
        lines.append(f"  {r['root']}: 证据 {r['evidence']}/4 | {ud} | {pr}")
    live = [r for r in results if r.get("ok") and r.get("userdata_ok")]
    # 嵌套树同属一个 git 仓库时，证据①（提交时间）不具区分度——显式提示，防误判
    gits = {it.get("detail") for r in results if r.get("ok") for it in (r.get("items") or [])[:1]}
    if len(results) > 1 and len(gits) == 1:
        lines.append("  注：① 提交时间为同一 git 仓库共享（嵌套树场景）——不具区分度，以 ②③④ 为准")
    if len(live) == 1:
        lines.append(f"  → 判定：{live[0]['root']} 是活跃树（唯一有运行时痕迹者）；其余候选按死树/旧备份对待")
    elif not live:
        lines.append("  → 判定：无候选有运行时痕迹——都不是用户实际运行的树（或 userData 在别处），"
                     "需向用户确认运行入口（rule 82：一句话确认后再动手）")
    else:
        lines.append(f"  → 判定：{len(live)} 棵候选都有运行时痕迹——按产物 mtime + git 提交新旧取活跃者，"
                     f"并向用户一句话确认")
    return "\n".join(lines)


def _force_utf8_stdio():
    """Windows 控制台默认 GBK：✓/✗/⚠ 等符号会 UnicodeEncodeError 直接崩掉报告输出
    （2026-09-12 实跑暴露：active-tree 双树对比输出崩溃）。
    统一转 UTF-8（errors=replace 兜底）——报告永不为编码问题静默失败。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _safe_print(text: str):
    """报告输出最后一道防线：stdio 加固若被改坏（GBK 环境），退化为 ASCII 替换 + 明确告警，
    而不是抛 Traceback 让人猜（规则：红灯要可读；本函数自身只输出 ASCII）。"""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", "replace").decode("ascii"))
        print("[six_layer_check] WARN: non-ASCII report output failed under this console "
              "encoding - check _force_utf8_stdio() at the top of each script's main()")


def _safe_print_json(obj):
    """JSON 输出：GBK 环境退化为 ensure_ascii=True（仍是合法 JSON，不抛 Traceback）"""
    try:
        print(json.dumps(obj, ensure_ascii=False, indent=2))
    except UnicodeEncodeError:
        print(json.dumps(obj, ensure_ascii=True, indent=2))


def _runtime_probe_safe():
    """运行时探针（rule 78 v3.16.0）：脚本 Gate 前置动作。探针失败不阻断检查，
    但必须在报告头明示（禁止静默跳过，G-001 v1.4 口径）。"""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import runtime_probe
        return runtime_probe.probe()
    except Exception:
        return None


def _probe_line(p: dict) -> str:
    n = p.get("node") or {}
    txt = f"python={p['python']['version']} node={n.get('version') or 'missing'}"
    if not n.get("ok"):
        txt += "（降级：node 不可用 → 手写等价记录 + 标注未验证；rule 78）"
    return f"[PROBE] {txt} status={p.get('status')}"


# ---------- 引擎自检（self-test · v3.16.0 新增） ----------
# 来源：2026-09-12 引擎对齐实战——本轮修掉的真问题（GBK 控制台崩输出 / 噪音淹没真问题 /
# 空洞 PASS / 产物目录误选 / 归档时序无断言）**全部是"真跑才发现"的**（rule 43）。
# 把当时那些真跑用例固化成回归网（rule 64：能脚本化的绝不靠自觉）：
# 以后每次改引擎，先跑 `python six_layer_check.py self-test`——红了就知道哪条能力回归了。
# 设计约束：① 只用标准库 ② fixture 在 tempfile 沙箱现造现删（不依赖真实项目）
#          ③ 编码类问题用 PYTHONIOENCODING=gbk 子进程复现（确定性地抓编码回归）
#          ④ 本机缺 bash / powershell → SKIP（记未验证，不静默当 PASS）

def _w(p: Path, text: str = "x", mtime: float = None) -> Path:
    """写 fixture 文件（可指定 mtime；父目录自动建）"""
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    if mtime is not None:
        os.utime(p, (mtime, mtime))
    return p


def _run_proc(cmd, env=None, timeout=120):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                          env=env, encoding="utf-8", errors="replace")


def run_self_test(keep_tmp: bool = False) -> dict:
    items = []

    def add(name, ok, detail="", skip=False):
        items.append({"name": name, "detail": detail,
                      "status": "SKIP" if skip else ("PASS" if ok else "FAIL")})

    scripts_dir = Path(__file__).resolve().parent
    self_path = str(Path(__file__).resolve())
    py = sys.executable
    env_gbk = dict(os.environ, PYTHONIOENCODING="gbk")   # 复现 Windows GBK 控制台
    base = time.time() - 7200                            # fixture 时间基线（远离 now，防"陈旧产物"干扰）
    box = Path(tempfile.mkdtemp(prefix="sl_selftest_"))

    # 用例 0：全脚本可编译（compile 不落 __pycache__）
    py_files = sorted(scripts_dir.glob("*.py"))
    bad = []
    for f in py_files:
        try:
            compile(f.read_text(encoding="utf-8"), str(f), "exec")
        except SyntaxError as e:
            bad.append(f"{f.name}:{e.lineno}")
    add("全脚本可编译（compile，不落 pyc）", not bad,
        f"{len(py_files)} 个脚本" + (f" · 失败: {bad}" if bad else ""))

    # 用例 1：运行时探针（正反用例 + GBK 环境）
    r = _run_proc([py, str(scripts_dir / "runtime_probe.py"), "--require", "nonexistent"], env_gbk)
    add("runtime_probe --require 缺失 → exit 1",
        r.returncode == 1 and "status=blocked" in (r.stdout + r.stderr), f"rc={r.returncode}")
    add("runtime_probe GBK 环境无 Traceback", "Traceback" not in (r.stdout + r.stderr),
        "PYTHONIOENCODING=gbk")

    # 用例 2：活跃树四证据 + 死树识别 + 双树对比
    live = box / "live"
    _w(live / "package.json", json.dumps({"name": "sl-selftest-live", "productName": "SLSelftestLive"}), base)
    _w(live / "electron-builder.yml",
       "files: [out/**]\nextraResources:\n  - from: pack-staging\n    to: .\n", base)
    _w(live / "src" / "index.ts", "export {}\n", base)
    _w(live / "node_modules" / ".package-lock.json", "{}", base)
    for i in range(5):
        _w(live / "node_modules" / f"pkg{i}" / "index.js", "", base)
    _w(live / "dist" / "win-unpacked" / "resources" / "app.asar", "asar", base)
    _w(live / "dist" / "win-unpacked" / "SLSelftestLive.exe", "exe", base)
    _w(live / "dist" / "SLSelftestLive.zip", "zip", base + 600)
    ud = box / "userdata" / "sl-selftest-live"
    _w(ud / "data_1", "x", base + 900)
    _w(ud / "logs" / "main.log", "log", base + 900)
    rl = check_active_tree(str(live), userdata=str(ud))
    add("活跃树四证据：产物/运行时痕迹/分发链路可识别",
        rl["ok"] and rl["product_ok"] and rl["userdata_ok"] and rl["evidence"] >= 3,
        f"evidence={rl['evidence']}/4 product={rl['product_ok']} userdata={rl['userdata_ok']}")
    dead = box / "dead"
    _w(dead / "package.json", "{}", base)
    _w(dead / "src" / "a.ts", "", base)
    rd = check_active_tree(str(dead), userdata=str(box / "no_userdata"))
    add("死树识别：缺运行时痕迹 → 非活跃树嫌疑",
        (not rd["userdata_ok"]) and "非活跃树嫌疑" in rd["verdict"], rd["verdict"][:56])
    cmp_txt = render_active_tree_compare([rl, rd])
    add("双树对比判定：有运行时痕迹者胜出",
        "是活跃树（唯一有运行时痕迹者）" in cmp_txt, cmp_txt.strip().splitlines()[-1][:72])

    # 用例 3：product-assert（目录优选 / 归档时序 / 两次采样 / 空洞 PASS）
    pa = box / "pa"
    _w(pa / "tailwind.config.js", "module.exports={content:['./src/**/*.{ts,tsx}']}\n", base)
    _w(pa / "src" / "renderer" / "App.tsx",
       'export const A=()=> <div className="bg-rose-500 flex" />\n', base)
    _w(pa / "dist" / "win-unpacked" / "resources" / "app.asar", "asar", base)
    _w(pa / "dist" / "SLSelftest.zip", "zip", base + 600)
    _w(pa / "out" / "renderer" / "assets" / "index.css", ".bg-rose-500{}.flex{}\n", base + 1200)
    _w(pa / "out" / "renderer" / "assets" / "index.js", "js", base + 1200)
    ra = check_product_assert(str(pa))
    ka = {it["key"]: it for it in ra["items"]}
    add("产物目录选择：可交付产物(dist)优先于更新的 out",
        "可交付产物选 dist/" in ka.get("pick", {}).get("detail", ""),
        ka.get("pick", {}).get("detail", "")[:80])
    add("归档时序：zip 晚于 asar → PASS",
        ka.get("time_order", {}).get("status") == "PASS", ka.get("time_order", {}).get("detail", "")[:80])
    add("产物稳定性：两次采样一致 → PASS",
        ka.get("stability", {}).get("status") == "PASS", ka.get("stability", {}).get("detail", "")[:60])

    vac = box / "vac"
    _w(vac / "tailwind.config.js", "module.exports={content:['./src/**/*.tsx']}\n", base)
    _w(vac / "src" / "Plain.ts", "export const x = 1\n", base)
    _w(vac / "out" / "index.css", ".a{}\n", base)
    ta = {it["key"]: it for it in check_product_assert(str(vac))["items"]}.get("tier_a", {})
    add("空洞 PASS 识别：0 个期望类 → WARN（不算通过）",
        ta.get("status") == "WARN" and "空洞 PASS" in ta.get("detail", ""),
        f"status={ta.get('status')} · {ta.get('detail', '')[:48]}")

    bo = box / "bo"
    _w(bo / "dist" / "win-unpacked" / "resources" / "app.asar", "asar", base + 1200)
    _w(bo / "dist" / "SLSelftest.zip", "zip", base)
    to = {it["key"]: it for it in check_product_assert(str(bo))["items"]}.get("time_order", {})
    add("归档时序反向用例：zip 旧于 asar → FAIL（坏包）",
        to.get("status") == "FAIL", to.get("detail", "")[:80])

    # 用例 4：render-silent-fail（噪音剪枝 / UI 域 / DOM 白名单）
    fe = box / "fe"
    _w(fe / "tailwind.config.js", "module.exports={content:['./src/renderer/**/*.{ts,tsx}']}\n", base)
    _w(fe / "src" / "renderer" / "App.tsx", "export const A=()=>null\n", base)
    _w(fe / "src" / "main" / "main.ts", "export {}\n", base)
    _w(fe / "scripts" / "tool.ts", "export {}\n", base)
    _w(fe / "out-old-20260816" / "renderer" / "App.tsx", "export {}\n", base)
    _w(fe / "dist-v3" / "win-unpacked" / "renderer" / "App.tsx", "export {}\n", base)
    _w(fe / "tmp" / "x" / "renderer" / "App.tsx", "export {}\n", base)
    tw = {it["key"]: it for it in check_render_silent_fail(str(fe))["items"]}.get("tailwind", {})
    add("噪音剪枝：out-old-*/dist-v3/tmp 不进比较域（UI 目录已覆盖 → PASS）",
        tw.get("status") == "PASS", f"status={tw.get('status')} · {tw.get('detail', '')[:60]}")

    fe2 = box / "fe2"
    _w(fe2 / "tailwind.config.js", "module.exports={content:['./src/other/**/*.{ts,tsx}']}\n", base)
    _w(fe2 / "src" / "renderer" / "App.tsx", "export const A=()=>null\n", base)
    _w(fe2 / "src" / "main" / "main.ts", "export {}\n", base)
    _w(fe2 / "out-old-20260816" / "renderer" / "App.tsx", "export {}\n", base)
    tw2 = {it["key"]: it for it in check_render_silent_fail(str(fe2))["items"]}.get("tailwind", {})
    d2 = tw2.get("detail", "")
    add("tailwind 缺口报真问题、列表无噪音（src/renderer 在、out-old/src/main 不在）",
        tw2.get("status") == "FAIL" and "src/renderer" in d2
        and "out-old" not in d2 and "src/main" not in d2,
        f"status={tw2.get('status')} · {d2[:64]}")

    fe3 = box / "fe3"
    _w(fe3 / "src" / "renderer" / "x.ts",
       "export const f=()=>window.document.title+window.HTMLInputElement.name+window.myApi.ping()\n", base)
    _w(fe3 / "src" / "renderer" / "types.d.ts",
       "declare global { interface Window { myApi: { ping: () => void } } }\nexport {}\n", base)
    pl = {it["key"]: it for it in check_render_silent_fail(str(fe3))["items"]}.get("preload", {})
    add("preload d.ts：DOM 白名单生效（document/HTMLInputElement 不误报）",
        pl.get("status") == "PASS", f"status={pl.get('status')} · {pl.get('detail', '')[:56]}")

    fe4 = box / "fe4"
    _w(fe4 / "src" / "renderer" / "x.ts", "export const f=()=>window.undeclaredApi.z\n", base)
    _w(fe4 / "src" / "renderer" / "types.d.ts",
       "declare global { interface Window { myApi: {} } }\nexport {}\n", base)
    pl4 = {it["key"]: it for it in check_render_silent_fail(str(fe4))["items"]}.get("preload", {})
    add("preload d.ts：真未声明项仍报出",
        pl4.get("status") == "FAIL" and "undeclaredApi" in pl4.get("detail", ""),
        pl4.get("detail", "")[:64])

    # 用例 5：本脚本自身输出（GBK 环境不崩）
    rb = _run_proc([py, self_path, "active-tree", str(live), "--userdata=" + str(ud)], env_gbk)
    add("本脚本 active-tree 在 GBK 环境不崩（✓/✗ 安全）",
        rb.returncode == 0 and "Traceback" not in (rb.stdout + rb.stderr) and "活跃树" in rb.stdout,
        f"rc={rb.returncode} · stdout={len(rb.stdout)}B")
    rb2 = _run_proc([py, self_path, "product-assert", str(pa)], env_gbk)
    add("本脚本 product-assert 在 GBK 环境不崩（WARN 符号安全）",
        rb2.returncode == 0 and "Traceback" not in (rb2.stdout + rb2.stderr), f"rc={rb2.returncode}")

    # 用例 6：三件套正反向用例（GBK 环境，规则 39/38+53/63）
    tp = box / "tp"
    _w(tp / "art.txt", "x")
    _w(tp / "uv.md", "x")
    _w(tp / "acc.md", "x")
    S = str(scripts_dir)
    ck = [py, f"{S}/checkpoint.py", str(tp)]
    r_ck = [_run_proc(ck + a, env_gbk) for a in
            (["expect", "W1", "m1", "art.txt"], ["mark", "m1", "delivered"],
             ["verify", "m1", "art.txt"], ["verify", "m1", "nope.txt"])]
    rcs = [x.returncode for x in r_ck]
    add("checkpoint 三态 + 磁盘核验（含缺失反向用例）", rcs == [0, 0, 0, 1], f"rcs={rcs}")
    add("checkpoint GBK 环境无 Traceback",
        all("Traceback" not in (x.stdout + x.stderr) for x in r_ck), "PYTHONIOENCODING=gbk")
    r_c1 = _run_proc([py, f"{S}/cost_log.py", str(tp), "add", "m1", "lite", "0.1", "ok", "无"], env_gbk)
    r_c2 = _run_proc([py, f"{S}/cost_log.py", str(tp), "add", "m2", "BOGUS", "0.1", "ok", "无"], env_gbk)
    add("cost_log 记账 + 非法档位拒绝",
        r_c1.returncode == 0 and r_c2.returncode == 1, f"rcs={[r_c1.returncode, r_c2.returncode]}")
    lf = [py, f"{S}/lifecycle.py", str(tp)]
    r_l = [_run_proc(lf + a, env_gbk) for a in
           (["transit", "DELIVERED"], ["transit", "EXECUTING"],
            ["transit", "DELIVERED", "--evidence-file", str(tp / "uv.md")],
            ["transit", "ACCEPTED", "--evidence-file", str(tp / "acc.md")])]
    rls = [x.returncode for x in r_l]
    add("lifecycle 状态机：非法转移/证据门/正常链", rls == [1, 0, 0, 0], f"rcs={rls}")
    add("lifecycle GBK 环境无 Traceback",
        all("Traceback" not in (x.stdout + x.stderr) for x in r_l), "PYTHONIOENCODING=gbk")

    # 用例 7：分发脚本语法（本机缺 bash 时 SKIP，记未验证）
    ps1 = scripts_dir.parent / "sync_to_platforms.ps1"
    if ps1.exists() and shutil.which("powershell"):
        rr = _run_proc(["powershell", "-NoProfile", "-Command",
                        f"[void][scriptblock]::Create((Get-Content -Raw '{ps1}')); 'PARSE_OK'"])
        add("sync_to_platforms.ps1 语法解析",
            rr.returncode == 0 and "PARSE_OK" in (rr.stdout or ""), f"rc={rr.returncode}")
    else:
        add("sync_to_platforms.ps1 语法解析", True, "本机无 powershell", skip=True)
    sh = scripts_dir.parent / "sync_to_platforms.sh"
    if sh.exists() and shutil.which("bash"):
        probe = _run_proc(["bash", "-c", "echo BASH_OK"])
        if "BASH_OK" in (probe.stdout or ""):
            rr = _run_proc(["bash", "-n", str(sh)])
            add("sync_to_platforms.sh 语法检查（bash -n）", rr.returncode == 0,
                (rr.stderr or "")[:64] or "ok")
        else:
            add("sync_to_platforms.sh 语法检查（bash -n）", True,
                "bash 不可用（WSL 无发行版 / 无 Git Bash）→ 记未验证", skip=True)
    else:
        add("sync_to_platforms.sh 语法检查（bash -n）", True,
            "本机无 bash → 记未验证", skip=True)

    pass_count = sum(1 for it in items if it["status"] == "PASS")
    fail_count = sum(1 for it in items if it["status"] == "FAIL")
    skip_count = sum(1 for it in items if it["status"] == "SKIP")
    if not keep_tmp:
        shutil.rmtree(box, ignore_errors=True)
    return {"ok": True, "root": str(box), "mode": "self-test", "items": items,
            "pass_count": pass_count, "fail_count": fail_count, "skip_count": skip_count,
            "kept_tmp": keep_tmp}


def render_self_test(res: dict) -> str:
    lines = ["[six_layer_check] 引擎自检（self-test · rule 64 回归网 · 改引擎后必跑）"]
    for it in res["items"]:
        mark = {"PASS": "✓", "FAIL": "✗", "SKIP": "-"}.get(it["status"], "?")
        lines.append(f"  {mark} [{it['status']:4s}] {it['name']}"
                     + (f"  ({it['detail']})" if it["detail"] else ""))
    lines.append(f"总计：{res['pass_count']} PASS / {res['fail_count']} FAIL / {res['skip_count']} SKIP"
                 + (f"（沙箱保留：{res['root']}）" if res["kept_tmp"] else ""))
    if res["fail_count"]:
        lines.append("✗ 引擎自检 FAIL——有回归，按上表逐条定位（不要跳过）")
    else:
        lines.append("✓ 引擎自检通过（SKIP = 本机缺该环境能力，按 rule 42 记未验证）")
    return "\n".join(lines)


# ---------- dispatch-check / write-conflict（v3.17.0 新增 · 批1 引擎化） ----------
# dispatch-check：派发前任务卡 lint（rule 78 引擎对齐）
# write-conflict：并行写集冲突检查（读 progress.json 预期产物求交，rule 69/22）

def check_dispatch_card(card_path: str) -> dict:
    """派发前任务卡 lint：①≤150 行 ②有验收命令 ③两维档位打分 ④自包含声明 ⑤≥100 行有骨架。
    判定逻辑归 rule 47 判定表（references/model_routing.md），本函数只查结构（消除双重引擎化）。"""
    p = Path(card_path)
    if not p.exists():
        return {"ok": False, "error": f"任务卡不存在: {card_path}"}
    text = p.read_text(encoding="utf-8")
    lines = text.splitlines()
    problems = []
    if len(lines) > 150:
        problems.append(f"任务卡 {len(lines)} 行 > 150 行预算（rule 40 注入三级）")
    if not re.search(r'验收|验证|verify|test|npm run|pytest|assert|EARS', text, re.I):
        problems.append("缺验收命令/验收标准")
    has_cog = re.search(r'认知类型|认知复杂度|机械|标准写码|设计决策', text)
    has_cost = re.search(r'失败代价|回退成本|影响面|只读|孤岛|interfaces|共享模块', text)
    if not (has_cog and has_cost):
        problems.append("缺档位两维打分（认知类型 / 失败代价，rule 47 判定表）")
    if not re.search(r'自包含|self-contained|上下文自包含', text):
        problems.append("缺上下文自包含声明（rule 40）")
    if len(lines) >= 100 and not re.search(r'骨架|伪代码|pseudo|skeleton|函数签名|接口签名', text):
        problems.append("大任务(≥100 行)缺骨架/伪代码（rule 47②）")
    return {"ok": not problems, "problems": problems, "lines": len(lines)}


def check_write_conflict(project_dir: str) -> dict:
    """并行写集冲突检查：读 progress.json expected_products（pending）求文件交集。
    相交 → 强制合批（rule 22）或串行；不相交 → worktree 降为可选项（rule 69 隔离分级）。"""
    root = Path(project_dir)
    pj = root / "progress.json"
    if not pj.exists():
        return {"ok": True, "note": "无 progress.json（无预期产物清单），跳过"}
    try:
        state = json.loads(pj.read_text(encoding="utf-8"))
    except Exception as e:
        return {"ok": False, "error": f"progress.json 解析失败: {e}"}
    pending = [e for e in (state.get("expected_products") or []) if e.get("status") == "pending"]
    if not pending:
        return {"ok": True, "note": "无 pending 预期产物，跳过"}
    seen = {}
    conflicts = []
    for e in pending:
        mod = e.get("module", "?")
        for f in e.get("files", []):
            fn = str(f).strip().replace("\\", "/")
            if not fn:
                continue
            if fn in seen and seen[fn] != mod:
                conflicts.append({"file": fn, "module_a": seen[fn], "module_b": mod})
            else:
                seen[fn] = mod
    if conflicts:
        return {"ok": False, "conflicts": conflicts,
                "detail": "写集冲突：多模块预期写同一文件 → 强制合批(rule 22)或串行，禁止并行写"}
    return {"ok": True, "note": f"无写集冲突（{len(pending)} 个模块 pending，文件所有权互斥）"}


def main():
    _force_utf8_stdio()
    argv = sys.argv[1:]
    verb = None
    if argv and argv[0] in ("render-silent-fail", "product-assert", "active-tree", "self-test",
                            "dispatch-check", "write-conflict"):
        verb = argv[0]
        argv = argv[1:]
    force_reason = None
    userdata = None
    flags = set()
    for a in argv:
        if a.startswith("--force-with-reason="):
            force_reason = a.split("=", 1)[1]
        elif a.startswith("--userdata="):
            userdata = a.split("=", 1)[1]
        elif a.startswith("--"):
            flags.add(a)
    args = [a for a in argv if not a.startswith("--")]
    strict = "--strict" in flags
    as_json = "--json" in flags

    if verb == "self-test":
        res = run_self_test(keep_tmp="--keep-tmp" in flags)
        if as_json:
            _safe_print_json(res)
        else:
            _safe_print(render_self_test(res))
        bad = res["fail_count"] + (res["skip_count"] if strict else 0)
        sys.exit(1 if bad else 0)

    if verb == "active-tree":
        dirs = args or ["."]
        results = [check_active_tree(d, userdata) for d in dirs]
        if not any(r.get("ok") for r in results):
            _safe_print(f"[six_layer_check] {results[0].get('error')}")
            sys.exit(2)
        if as_json:
            _safe_print_json(results if len(results) > 1 else results[0])
        else:
            parts = [render_active_tree_report(r) if r.get("ok")
                     else f"[six_layer_check] {r.get('error')}" for r in results]
            if len(results) > 1:
                parts.append(render_active_tree_compare(results))
            _safe_print("\n".join(parts))
        if strict and any(r.get("ok") and (r["evidence"] < 4 or not r["userdata_ok"]) for r in results):
            sys.exit(1)
        sys.exit(0)

    if verb == "dispatch-check":
        if not args:
            _safe_print("[six_layer_check] dispatch-check 需要: <任务卡路径> [--force-with-reason=理由]")
            sys.exit(1)
        res = check_dispatch_card(args[0])
        if force_reason:
            res["forced_skip"] = force_reason
            res["ok"] = True
            res["problems"] = []
        probe = _runtime_probe_safe()
        if as_json:
            _safe_print_json(res)
        else:
            if res.get("ok"):
                head = (_probe_line(probe) + "\n") if probe else ""
                _safe_print(head + f"[dispatch-check] ✓ 任务卡通过（{res.get('lines')} 行）")
            else:
                for prob in res.get("problems", []):
                    _safe_print(f"[dispatch-check] ✗ {prob}")
        sys.exit(0 if res.get("ok") else 1)

    if verb == "write-conflict":
        res = check_write_conflict(args[0] if args else ".")
        if as_json:
            _safe_print_json(res)
        else:
            if res.get("ok"):
                _safe_print(f"[write-conflict] ✓ {res.get('note') or '通过'}")
            else:
                _safe_print(f"[write-conflict] ✗ {res.get('detail')}")
                for c in res.get("conflicts", []):
                    _safe_print(f"  {c['file']} ← {c['module_a']} vs {c['module_b']}")
        sys.exit(0 if res.get("ok") else 1)

    project_dir = args[0] if args else "."
    mode = "auto"
    for m in ("init", "deliver"):
        if f"--mode={m}" in flags or f"--mode {m}" in " ".join(sys.argv):
            mode = m

    if verb in ("render-silent-fail", "product-assert"):
        if verb == "render-silent-fail":
            res = check_render_silent_fail(project_dir)
        else:
            res = check_product_assert(project_dir)
        if not res.get("ok"):
            _safe_print(f"[six_layer_check] {res.get('error')}")
            sys.exit(2)
        if verb == "product-assert" and force_reason:
            res["forced_skip"] = force_reason
            res["fail_count"] = 0
        report = (render_silent_fail_report(res) if verb == "render-silent-fail"
                  else render_product_assert_report(res))
        probe = _runtime_probe_safe()
        if probe:
            res["runtime"] = probe
            report = _probe_line(probe) + "\n" + report
        if as_json:
            _safe_print_json(res)
        else:
            _safe_print(report)
        if strict and res.get("fail_count", 0) > 0:
            sys.exit(1)
        sys.exit(0)

    res = check(project_dir, mode)
    if not res.get("ok"):
        _safe_print(f"[six_layer_check] {res.get('error')}")
        sys.exit(2)
    report = render_report(res)
    probe = _runtime_probe_safe()
    if probe:
        res["runtime"] = probe
        report = _probe_line(probe) + "\n" + report
    if as_json:
        _safe_print_json(res)
    else:
        _safe_print(report)
    if strict and res.get("missing"):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
