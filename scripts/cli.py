#!/usr/bin/env python3
"""cli.py — 引擎总入口（rule 64 引擎化 · L1a · 开发文档 §4.2 · D-15/D-17/D-18/D-19）

设计要点（与开发文档逐条对应）：
  1. **in-process 包裹（默认）+ `--isolate` 逃生阀**（K-2 / D-15）：
     默认在**当前进程内** import 目标脚本并调用其 `main()`（实测约 13× 快于起子进程），
     `--isolate` 走 subprocess（隔离环境/调试用）。**两条路径的退出码与语义必须等价**。
  2. **三调用约定分派表**（D-15）：`dir-first` / `argparse` / `positional`；
     dir-first 脚本额外支持"动词在前"的写法（自动归一化）。
  3. **子命令 Gate 语义契约层**（D-15）：与形态无关——专覆盖"失败不走退出码"的脚本
     （如 `read_knowledge` 0 命中默认 WARN 而非绿）。语义 = `PASS/WARN/FAIL/SKIP`。
  4. **零副作用**：不改 cwd、不改 env、调用后恢复 sys.argv / sys.stdout / sys.modules。
  5. **引擎参数单一来源**（D-18）：启动校验 `engine_config.json` 每键 schema + 合法域，
     **非法即 FAIL（不许静默取默认）**；打印生效参数与来源。
  6. **运行时寻址 + 版本核对**（R-06）：打印当前寻址副本版本；与仓库版本不一致 → 警告。
  7. **总开关**（R-01）：`SIXLAYER_ENGINE=off` → 全部子命令旁路，**exit 3 = 未执行**
     （刻意不用 0：0 会被 Gate 当成"通过"，那就把回滚开关变成了新的假绿源）。

用法：
    python scripts/cli.py [--project DIR] [--isolate] [--json] <subcommand> [args...]

子命令：
    run <script> [args...]     通用包裹（脚本名可省略 .py）
    self-test                  引擎自测总入口（委托 six_layer_check self-test）
    params                     打印生效参数 + 来源 + 版本寻址（含配置校验）
    version                    只打印版本与寻址
    status append|check ...    状态板（rule 84 · D-02/D-22）
    route-error ...            错误路由（rule 33 · D-14）
    compress ...               上下文压缩（rule 83 · LC1/LC2/LC3）
    design ...                 设计锁定 Gate（rule 65）
    llm ...                    LLM 调用层（rule 56 · 默认关闭）

退出码：0=成功 / 1=参数或配置失败 / 2=找不到脚本 / 3=引擎已旁路（未执行，不构成验证）
        其余：**原样透传被包裹脚本的退出码**（退出码保真）
"""
from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPTS_DIR.parent
CONFIG_PATH = SCRIPTS_DIR / "engine_config.json"

BYPASS_RC = 3  # 「引擎旁路、未执行」专用退出码（见头部第 7 条）

# ── 三调用约定分派表（D-15）────────────────────────────────────────────────
# dir-first  : <dir> <verb> [args]
# argparse   : 自带 argparse（首个参数不是目录）
# positional : 纯位置参数
CONVENTIONS = {
    "checkpoint": "dir-first",
    "cost_log": "dir-first",
    "lifecycle": "dir-first",
    "six_layer_check": "dir-first",   # 另含 verb-first 子命令（render-silent-fail 等）
    "validate_output": "positional",
    "read_knowledge": "argparse",
    "runtime_probe": "argparse",
    "rule_index": "argparse",
    "state_board": "dir-first",
    "route_error": "argparse",
    "compress": "argparse",
    "design_gate": "argparse",
    "llm_client": "argparse",
    "write_assert": "argparse",
}

# ── 子命令 Gate 语义契约层（D-15）──────────────────────────────────────────
# 默认规则：rc != 0 → FAIL；rc == 0 → PASS。
# patterns 用于覆盖"失败不走退出码"的脚本（按序匹配 stdout）。
SEMANTICS = {
    "read_knowledge": {"patterns": [("0 命中", "WARN")]},   # 默认 WARN 非绿（rule 59）
    "six_layer_check": {"patterns": [("空洞 PASS", "WARN"), ("vacuous", "WARN")]},
    "runtime_probe": {"patterns": [("status=degraded", "WARN"), ("不可测", "SKIP")]},
    "rule_index": {"patterns": []},
}

# cli.py 自身子命令 → 目标脚本（门面映射）
FACADE = {
    "self-test": "six_layer_check",
    "status": "state_board",
    "route-error": "route_error",
    "compress": "compress",
    "design": "design_gate",
    "llm": "llm_client",
}


def _force_utf8_stdio():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


class _Tee:
    """同时写多个流（原 stdout + 捕获缓冲），用于既回显又做语义判定。"""

    def __init__(self, *streams):
        self.streams = streams

    def write(self, s):
        for st in self.streams:
            try:
                st.write(s)
            except Exception:
                pass
        return len(s)

    def flush(self):
        for st in self.streams:
            try:
                st.flush()
            except Exception:
                pass

    def isatty(self):
        return False


# ── engine_config 校验（D-18：每键 schema + 合法域，非法即 FAIL）────────────
SCHEMA = {
    "llm.model_whitelist": {"type": "list_str", "min_len": 1},
    "llm.reasoning_effort": {"type": "enum", "values": ["low", "high", "max"]},
    "llm.temperature": {"type": "float", "min": 0.0, "max": 2.0},
    "llm.request_timeout_sec": {"type": "int", "min": 1, "max": 600},
    "llm.max_retries": {"type": "int", "min": 0, "max": 5},
    "budget.per_wave_tokens": {"type": "int", "min": 1},
    "budget.alert_ratio": {"type": "float", "min": 0.0, "max": 1.0},
    "budget.ask_human_ratio": {"type": "float", "min": 0.0, "max": 1.0},
    "timeout.dispatch_sec": {"type": "int", "min": 1},
    "calibration.window_days": {"type": "int", "min": 1},
    "engine.enabled": {"type": "bool"},
}


class ConfigError(Exception):
    pass


def _dig(cfg: dict, dotted: str):
    cur = cfg
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None, False
        cur = cur[part]
    return cur, True


def _check_key(key: str, value, spec: dict):
    t = spec["type"]
    if t == "enum":
        if value not in spec["values"]:
            raise ConfigError(f"{key}={value!r} 不在合法域 {spec['values']} —— 不许静默取默认")
    elif t == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConfigError(f"{key} 必须是整数，实际 {type(value).__name__}")
        if value < spec.get("min", -(10 ** 18)) or value > spec.get("max", 10 ** 18):
            raise ConfigError(f"{key}={value} 越界 [{spec.get('min')},{spec.get('max')}]")
    elif t == "float":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ConfigError(f"{key} 必须是数值，实际 {type(value).__name__}")
        if not (spec.get("min", float("-inf")) <= value <= spec.get("max", float("inf"))):
            raise ConfigError(f"{key}={value} 越界 [{spec.get('min')},{spec.get('max')}]")
    elif t == "bool":
        if not isinstance(value, bool):
            raise ConfigError(f"{key} 必须是布尔，实际 {type(value).__name__}")
    elif t == "list_str":
        if not isinstance(value, list) or len(value) < spec.get("min_len", 0):
            raise ConfigError(f"{key} 必须是非空字符串数组")
        for x in value:
            if not isinstance(x, str):
                raise ConfigError(f"{key} 元素必须是字符串，发现 {type(x).__name__}")


def load_engine_config(strict: bool = True) -> dict:
    """读 + 校验 engine_config.json。strict=True 时非法即 raise ConfigError（D-18）。"""
    raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    for key, spec in SCHEMA.items():
        value, present = _dig(raw, key)
        if not present:
            if strict:
                raise ConfigError(f"{key} 缺失 —— engine_config 必须显式定义每一键"
                                  f"（schema 里有、配置里没有 = FAIL）")
            continue
        if value is None:
            continue  # 允许 null = 「未校准」，由消费方显式处理
        _check_key(key, value, spec)
    return raw


def _skill_version(d: Path):
    p = d / "SKILL.md"
    if not p.exists():
        return None
    import re
    m = re.search(r"v\d+\.\d+\.\d+", p.read_text(encoding="utf-8", errors="replace"))
    return m.group(0) if m else None


def _repo_dir():
    env = os.environ.get("SIXLAYER_REPO")
    if env and Path(env).is_dir():
        return Path(env)
    for base in [Path.cwd(), *Path.cwd().parents]:
        marker = base / ".sixlayer_repo"
        if marker.exists():
            try:
                cand = Path(marker.read_text(encoding="utf-8").strip())
                if cand.is_dir():
                    return cand
            except Exception:
                pass
    return None


def _engine_enabled() -> bool:
    return os.environ.get("SIXLAYER_ENGINE", "").strip().lower() != "off"


def _banner_bypass():
    print("[engine] bypass (SIXLAYER_ENGINE=off) —— 全部子命令旁路，未执行任何检查；"
          f"本结果不构成验证（rule 42），退出码 {BYPASS_RC}=未执行", file=sys.stderr)


def _print_params(cfg: dict, addressed: Path):
    print(f"[engine_config] source={CONFIG_PATH.relative_to(SKILL_DIR) if CONFIG_PATH.is_relative_to(SKILL_DIR) else CONFIG_PATH}")
    for key in ("llm.model_whitelist", "llm.reasoning_effort", "llm.temperature",
                "llm.request_timeout_sec", "llm.max_retries", "budget.per_wave_tokens",
                "budget.alert_ratio", "budget.ask_human_ratio", "timeout.dispatch_sec",
                "calibration.window_days"):
        v, present = _dig(cfg, key)
        print(f"[engine_config] {key}={v if present else '<undef>'} source={CONFIG_PATH.name}")
    ver = _skill_version(addressed)
    repo = _repo_dir()
    repo_ver = _skill_version(repo) if repo else None
    if repo_ver is None:
        match = "unknown(未设 SIXLAYER_REPO / 无 .sixlayer_repo 标记)"
    else:
        match = "true" if repo_ver == ver else f"FALSE(repo={repo_ver})"
    print(f"[engine] version={ver} addressed={addressed} repo_version={repo_ver or '-'} match={match}")
    if repo_ver is not None and repo_ver != ver:
        print("[engine] ⚠ 版本漂移：运行时副本与仓库不一致 —— 需回流或重跑 sync_to_platforms"
              "（R-06）；请记 cost_log 异常类型列", file=sys.stderr)


# ── 调用约定归一化 ─────────────────────────────────────────────────────────
# ── 已知动词表（归一化用）────────────────────────────────────────────────
# ★ 必需：dir-first 脚本（如 six_layer_check）**另含 verb-first 子命令**
# （write-assert / render-silent-fail …）。若只按"第一个参数是不是目录"来交换，
# 会把 `write-assert <dir>` 误交换成 `<dir> write-assert`，于是脚本收不到动词、
# 静默退回默认合规检查路径，**返回 0 = 假绿**（本节自测真红过一次）。
KNOWN_VERBS = {
    "checkpoint": {"status", "expect", "mark", "verify"},
    "cost_log": {"add", "summary", "audit", "tail"},
    "lifecycle": {"get", "transit", "history"},
    "state_board": {"init", "check", "append"},
    "six_layer_check": {"render-silent-fail", "product-assert", "active-tree", "self-test",
                        "dispatch-check", "write-conflict", "write-assert"},
}


def normalize_argv(script: str, argv: list) -> list:
    """dir-first 脚本额外接受"动词在前"写法：<verb> <dir> ... → <dir> <verb> ...
    ① 首参是**已知动词** → 原样保留（verbs 优先，不再看它是不是目录）
    ② 否则仅当第一个参数不是已存在目录、而第二个是目录时才交换（避免误伤正常写法）。"""
    if CONVENTIONS.get(script) != "dir-first" or len(argv) < 2:
        return list(argv)
    a, b = argv[0], argv[1]
    if a in KNOWN_VERBS.get(script, set()):
        return list(argv)
    if not Path(a).is_dir() and Path(b).is_dir():
        return [b, a] + list(argv[2:])
    return list(argv)


def _resolve_script(name: str) -> Path:
    p = Path(name)
    if p.suffix != ".py":
        p = SCRIPTS_DIR / (name + ".py")
    elif not p.is_absolute():
        p = SCRIPTS_DIR / p.name
    return p


def _run_in_process(script_path: Path, argv: list) -> tuple:
    """在当前进程内执行目标脚本，**忠实模拟 `python script.py`**，返回 (rc, stdout_text)。

    ★ 关键（2026-09-30 实证两次修正）：
      ① 必须让脚本处在 `__name__ == "__main__"` 的命名空间里执行，这样脚本底部的
         `if __name__ == "__main__": main()` 守卫会**照常触发** —— 与起子进程完全同构。
         若改成"import 后手动调 main()"，则对**没有守卫**的脚本会多跑一次
         （子进程什么都不做 → rc=0；in-process 却执行了 main → rc≠0；逃生阀不等价，实测 1 vs 0）。
      ② **不能用 `module_from_spec` + 改 `mod.__name__`**：`SourceFileLoader` 会抛
         `ImportError: loader ... cannot handle __main__`。故改为直接 `compile + exec`
         到自建命名空间（顺带好处：**完全不污染 sys.modules**，零副作用更彻底）。
    """
    src = script_path.read_text(encoding="utf-8")
    code = compile(src, str(script_path), "exec")
    ns = {
        "__name__": "__main__",
        "__file__": str(script_path),
        "__builtins__": __builtins__,
        "__spec__": None,
        "__loader__": None,
        "__package__": None,
        "__doc__": None,
    }
    buf = io.StringIO()
    old_argv = list(sys.argv)
    old_stdout, old_stderr = sys.stdout, sys.stderr
    old_path = list(sys.path)
    rc = 0
    try:
        sys.argv = [str(script_path)] + list(argv)
        # 忠实模拟 `python scripts/foo.py`：脚本所在目录进 sys.path[0]（供 import 同目录模块）
        sys.path.insert(0, str(script_path.parent))
        sys.stdout = _Tee(old_stdout, buf)
        sys.stderr = _Tee(old_stderr, buf)
        try:
            exec(code, ns)
        except SystemExit as e:
            c = e.code
            rc = 0 if c is None else (c if isinstance(c, int) else 1)
    finally:
        sys.argv = old_argv
        sys.path = old_path
        sys.stdout, sys.stderr = old_stdout, old_stderr
    return rc, buf.getvalue()


def _run_isolate(script_path: Path, argv: list) -> tuple:
    r = subprocess.run([sys.executable, str(script_path)] + list(argv),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    sys.stdout.write(r.stdout or "")
    if r.stderr:
        sys.stderr.write(r.stderr)
    return r.returncode, out


def classify(script: str, rc: int, output: str) -> str:
    """Gate 语义契约层：把 (rc, 输出) 映射为 PASS/WARN/FAIL/SKIP（与调用形态无关）。"""
    if rc != 0:
        return "FAIL"
    for pat, verdict in SEMANTICS.get(script, {}).get("patterns", []):
        if pat in output:
            return verdict
    return "PASS"


def run_script(script: str, argv: list, isolate: bool, as_json: bool) -> int:
    path = _resolve_script(script)
    if not path.exists():
        print(f"[cli] 找不到脚本: {path}", file=sys.stderr)
        return 2
    argv = normalize_argv(path.stem, argv)
    rc, out = (_run_isolate if isolate else _run_in_process)(path, argv)
    verdict = classify(path.stem, rc, out)
    line = (f"[cli] sub={path.stem} convention={CONVENTIONS.get(path.stem, '?')} "
            f"isolate={int(isolate)} rc={rc} semantic={verdict} "
            f"argv={json.dumps(argv, ensure_ascii=False)}")
    print(line)
    if as_json:
        print(json.dumps({"script": path.stem, "rc": rc, "semantic": verdict,
                          "isolate": bool(isolate), "argv": argv}, ensure_ascii=False))
    return rc


def main() -> int:
    _force_utf8_stdio()
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--project", default="")
    ap.add_argument("--isolate", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("-h", "--help", action="store_true")
    args, rest = ap.parse_known_args()

    if args.help or not rest:
        print(__doc__)
        return 0 if args.help else 1

    addressed = SKILL_DIR
    try:
        cfg = load_engine_config(strict=True)
    except ConfigError as e:
        print(f"[engine_config] FAIL —— {e}", file=sys.stderr)
        print("[engine_config] D-18：每键带 schema + 合法域，非法即 FAIL（不许静默取默认）",
              file=sys.stderr)
        return 1
    except Exception as e:
        print(f"[engine_config] FAIL —— 无法读取 {CONFIG_PATH}: {e}", file=sys.stderr)
        return 1

    if not _engine_enabled():
        _banner_bypass()
        return BYPASS_RC

    sub, sub_args = rest[0], rest[1:]

    if sub == "params":
        _print_params(cfg, addressed)
        return 0
    if sub == "version":
        print(f"[engine] version={_skill_version(addressed)} addressed={addressed}")
        return 0
    if sub == "run":
        if not sub_args:
            print("[cli] run 需要脚本名", file=sys.stderr)
            return 1
        # --project 显式传参（D-19）：若给了且是该脚本的首个位置参数，则前置
        argv = list(sub_args[1:])
        if args.project and CONVENTIONS.get(Path(sub_args[0]).stem) in ("dir-first", "positional"):
            argv = [args.project] + argv
        return run_script(sub_args[0], argv, args.isolate, args.json)

    target = FACADE.get(sub, sub)
    argv = list(sub_args)
    if args.project and CONVENTIONS.get(target) == "dir-first" and args.project not in argv:
        argv = [args.project] + argv
    print(f"[engine_config] reasoning_effort={_dig(cfg, 'llm.reasoning_effort')[0]} "
          f"source={CONFIG_PATH.name}")
    return run_script(target, argv, args.isolate, args.json)


if __name__ == "__main__":
    sys.exit(main())
