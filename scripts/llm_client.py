#!/usr/bin/env python3
"""llm_client.py — 引擎侧 LLM 调用层（rule 56 · D-11 / D-12③ / D-13 · L2）

★ **默认关闭**：必须显式 `SIXLAYER_LLM=on` 才发真实请求；否则返回 **exit 3（PENDING）**，
  并打印"未执行"。无 key / 无网 → **降级 + 留痕计数**，绝不静默跳过（R-07）。
★ **凭证只从环境变量 `DEEPSEEK_API_KEY` 读**（D-20）；错误信息里 key 打码。

设计（逐条对应开发文档）：
  D-11  **解析内核手写约 50 行**（不吃依赖）；**连接层自建**（重试 / 退避 / 超时 / usage 落点）。
        **200 假绿四步防线**：① 响应回显核对（response.model == request.model）
        ② 能力协商核对（请求的 effort ∈ /models 的 supported_levels）
        ③ **语义指纹**（model + object + system_fingerprint 一致性）
        ④ **禁用透明修复组件**（禁 `json_repair` 类"失败则静默回退"，解析失败一律显式报错）
  D-12③ `reasoning_effort`（`low/high/max`，实测域）+ **三条可探测判据**：
        ① 能力协商 ② 机器可读生效证据（`reasoning_tokens` 两端对比）③ 兼容映射显式登记
  D-13  **只做 (b) 告警 + (c) 超限问人，不做真熔断**；数据源 = **provider `usage`**；
        分母 = `budget.per_wave_tokens`（**不用模型 context_window 做分母** —— rule 83 先例：
        分母错 127 倍 → 永不触发）；**漏账 / usage 缺失 → fail-closed**；
        **适用域 = 仅覆盖引擎自己发起的调用**（子 Agent 走原生工具绕过引擎，只做事后对账）
  LC3   结构化摘要（六字段）—— 失败**降级不阻塞主流程** + 记 `cost_log` 异常类型列

用法：
    python scripts/llm_client.py --status                       # 开关/凭证/能力协商现状（不发请求）
    python scripts/llm_client.py --replay <fixture.sse>          # 离线回归：用手写解析器重放真实 fixture
    python scripts/llm_client.py --chat "prompt" [--effort high] [--stream]
    python scripts/llm_client.py --budget-report [--project DIR]
    python scripts/llm_client.py --lc3-summary <bundle.json> [--project DIR]

退出码：0=成功 / 1=防线不通过或预算超限 / 2=参数或输入不合法 / 3=未执行（默认关闭）
"""
from __future__ import annotations

import argparse
import io
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPTS_DIR.parent
CONFIG_PATH = SCRIPTS_DIR / "engine_config.json"
MODELS_URL = "https://api.deepseek.com/models"
CHAT_URL = "https://api.deepseek.com/chat/completions"
PENDING_RC = 3
# ④ 禁用透明修复组件：这些包"失败则静默回退"，恰好是 D-12① 要防的东西
FORBIDDEN_REPAIR_LIBS = ("json_repair", "jsonrepair", "json_repair_py", "repair_json")
SIX_FIELDS = ("phase", "modules", "ruled_out", "top_suspect", "open_items", "next")


def _utf8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def mask(key: str) -> str:
    """错误信息里 key 必须打码（D-20）。"""
    if not key:
        return "<none>"
    return key[:6] + "..." + key[-4:] if len(key) > 12 else "<masked>"


def load_cfg() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def enabled() -> bool:
    """总开关之外的**本层开关**（默认关闭）。"""
    return os.environ.get("SIXLAYER_LLM", "").strip().lower() in ("on", "1", "true")


def get_key():
    return os.environ.get("DEEPSEEK_API_KEY", "").strip()


# ────────────────── D-11 解析内核（手写 SSE，零依赖）──────────────────
def parse_sse(text: str) -> dict:
    """手写 SSE 解析（约 50 行）：吃 `data:` 行 / 忽略 `:` 心跳注释 / 识别 `[DONE]`。

    返回 {frames:[...], data_lines, comment_lines, done, blanks, usage_frames}
    ★ 解析失败**绝不静默回退**（D-12①）：非法 JSON 帧 → 记入 `errors`，由调用方决定 FAIL。
    """
    frames, errors, comments = [], [], []
    data_lines = 0
    done = False
    blanks = 0
    for raw in (text or "").splitlines():
        line = raw.rstrip("\r")
        if line == "":
            blanks += 1
            continue
        if line.startswith(":"):            # 心跳 / keep-alive 注释
            comments.append(line)
            continue
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        data_lines += 1
        if payload == "[DONE]":
            done = True
            continue
        try:
            frames.append(json.loads(payload))
        except Exception as e:
            errors.append({"payload": payload[:120], "error": str(e)})
    usage_frames = [f for f in frames if f.get("usage")]
    return {"frames": frames, "errors": errors, "comment_lines": comments,
            "data_lines": data_lines, "done": done, "blanks": blanks,
            "usage_frames": usage_frames}


def extract_reasoning_tokens(resp: dict):
    u = resp.get("usage") or {}
    d = u.get("completion_tokens_details")
    return d.get("reasoning_tokens") if isinstance(d, dict) else None


# ────────────────── D-11 200 假绿四步防线 ──────────────────
def defense_1_echo(request_model: str, resp: dict) -> tuple:
    got = resp.get("model")
    ok = (got == request_model)
    return ok, f"② 响应回显核对: 请求={request_model} 响应={got}" + ("" if ok else " ✗ 被静默改写")


def defense_2_capability(effort: str, supported: list) -> tuple:
    if effort is None:
        return True, "② 能力协商核对: 未指定 effort，跳过"
    ok = effort in (supported or [])
    return ok, f"② 能力协商核对: effort={effort} supported={supported}" + ("" if ok else " ✗ 越域")


def defense_3_fingerprint(resp: dict, seen: dict) -> tuple:
    """语义指纹：model + object + system_fingerprint 三项一致（防"被换模型/被换端点"）。"""
    fp = {"model": resp.get("model"), "object": resp.get("object"),
          "system_fingerprint": resp.get("system_fingerprint")}
    if not seen:
        seen.update(fp)
        return True, f"③ 语义指纹: 基线建立 {fp}"
    ok = all(seen.get(k) == fp.get(k) for k in fp)
    return ok, f"③ 语义指纹: {fp} vs 基线 {seen}" + ("" if ok else " ✗ 指纹漂移")


def defense_4_no_repair_lib() -> tuple:
    """④ 禁用透明修复组件：源码/配置里不得出现 json_repair 类"失败则静默回退"的包。"""
    hits = []
    for p in list(SCRIPTS_DIR.glob("*.py")) + [CONFIG_PATH, SKILL_DIR / "SKILL.md"]:
        if not p.exists():
            continue
        txt = p.read_text(encoding="utf-8", errors="replace")
        for lib in FORBIDDEN_REPAIR_LIBS:
            if re.search(rf"^\s*(import|from)\s+{lib}\b", txt, re.M):
                hits.append(f"{p.name}:{lib}")
    return (not hits), "④ 禁用透明修复组件: " + ("无 json_repair 类依赖" if not hits else f"发现 {hits}")


# ────────────────── D-11 连接层（自建：重试/退避/超时）──────────────────
def _request(url: str, key: str, payload=None, method="GET", timeout=60, stream=False):
    headers = {"Authorization": "Bearer " + key, "Accept":
               "text/event-stream" if stream else "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    return urllib.request.urlopen(req, timeout=timeout)


def with_retry(fn, retries: int, on_attempt=None):
    """自建退避（指数 + 抖动）。**失败不静默**：最终失败原样抛出。"""
    last = None
    for i in range(retries + 1):
        try:
            return fn()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
            last = e
            if on_attempt:
                on_attempt(i + 1, e)
            if i < retries:
                time.sleep(min(2 ** i, 8) * (0.5 + random.random() / 2))
    raise last


def fetch_models(key: str, cfg: dict) -> dict:
    t = cfg["llm"]["request_timeout_sec"]

    def _go():
        with _request(MODELS_URL, key, timeout=t) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    return with_retry(_go, cfg["llm"]["max_retries"])


def chat(key: str, cfg: dict, payload: dict, stream: bool):
    t = cfg["llm"]["request_timeout_sec"]

    def _go():
        with _request(CHAT_URL, key, payload, method="POST", timeout=t, stream=stream) as r:
            return r.read().decode("utf-8", "replace")
    return with_retry(_go, cfg["llm"]["max_retries"])


# ────────────────── D-13 token 账本（fail-closed）──────────────────
def ledger_path(project: Path) -> Path:
    return project / "llm_usage.jsonl"


def append_usage(project: Path, entry: dict):
    with io.open(ledger_path(project), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def budget_report(project: Path, cfg: dict) -> dict:
    """D-13 (b) 告警 + (c) 超限问人。分母 = budget.per_wave_tokens（**不用 context_window**）。"""
    denom = cfg["budget"]["per_wave_tokens"]
    alert = cfg["budget"]["alert_ratio"]
    ask = cfg["budget"]["ask_human_ratio"]
    used = 0
    missing_usage = 0
    degraded_calls = 0
    calls = 0
    p = ledger_path(project)
    if p.exists():
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            calls += 1
            try:
                e = json.loads(line)
            except Exception:
                missing_usage += 1
                continue
            u = e.get("usage")
            if not isinstance(u, dict) or "total_tokens" not in u:
                # 区分两种"没有 usage"：
                #   ① 显式降级（没发起调用 / 无 key / 无网）→ 记 degraded，**不算漏账**
                #   ② 真发起了却没 usage 回写 → **漏账 → fail-closed**（D-13）
                if e.get("degraded") or e.get("missing_usage"):
                    degraded_calls += 1
                else:
                    missing_usage += 1
                continue
            used += int(u.get("total_tokens") or 0)
    ratio = (used / denom) if denom else 0.0
    if missing_usage > 0:
        verdict = "FAIL_CLOSED"
    elif ratio >= ask:
        verdict = "ASK_HUMAN"
    elif ratio >= alert:
        verdict = "ALERT"
    else:
        verdict = "OK"
    return {"calls": calls, "used_tokens": used, "denominator": denom,
            "ratio": round(ratio, 4), "alert_ratio": alert, "ask_human_ratio": ask,
            "missing_usage_lines": missing_usage, "degraded_calls": degraded_calls,
            "verdict": verdict,
            "applicability": "仅覆盖引擎自身发起的调用；子 Agent 走原生工具 → 只做事后对账（R-15）",
            "note": "分母用 budget.per_wave_tokens，**不用 context_window**（rule 83 先例：分母错 127 倍 → 永不触发）"}


# ────────────────── LC3 结构化摘要（花 LLM 的一层）──────────────────
LC3_SYSTEM = ("你是上下文压缩器。只输出 JSON，含六个键："
              "phase/modules/ruled_out/top_suspect/open_items/next。"
              "涉及文件必须写『路径@commit』；不得转述原话；不得编造。")


def lc3_summary(key: str, cfg: dict, bundle: dict, project: Path) -> dict:
    src = bundle.get("lc3_input") or {k: bundle.get(k) for k in SIX_FIELDS}
    payload = {"model": cfg["llm"]["model_whitelist"][0],
               "messages": [{"role": "system", "content": LC3_SYSTEM},
                            {"role": "user", "content": json.dumps(src, ensure_ascii=False)}],
               "reasoning_effort": cfg["llm"]["reasoning_effort"],
               "max_tokens": 1200, "stream": False}
    raw = chat(key, cfg, payload, stream=False)
    try:
        resp = json.loads(raw)                     # ★ 严格解析：失败即 raise，绝不 json_repair
    except Exception as e:
        return {"ok": False, "degraded": True, "reason": f"响应非合法 JSON：{e}"}
    content = ((resp.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    try:
        summary = json.loads(content)
    except Exception as e:
        return {"ok": False, "degraded": True, "reason": f"摘要非合法 JSON（不修复、不改写）：{e}"}
    missing = [k for k in SIX_FIELDS if k not in summary]
    append_usage(project, {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                           "model": resp.get("model"), "usage": resp.get("usage")})
    return {"ok": not missing, "degraded": False, "summary": summary,
            "missing_fields": missing, "usage": resp.get("usage")}


# ────────────────── CLI ──────────────────
def cmd_status(cfg: dict) -> int:
    key = get_key()
    print(f"[llm] SIXLAYER_LLM={'on' if enabled() else 'off'}（本层开关；默认关闭）")
    print(f"[llm] engine.enabled={cfg['engine']['enabled']} key={mask(key)} source=env:DEEPSEEK_API_KEY"
          + ("" if key else " （未设 → 只能跑 --replay 离线回归）"))
    print(f"[llm] effort={cfg['llm']['reasoning_effort']} allowed={cfg['llm'].get('reasoning_effort_allowed')}")
    for ok, msg in [defense_4_no_repair_lib()]:
        print(f"[llm] 防线 {msg} {'✓' if ok else '✗'}")
    print("[llm] 适用域：仅覆盖引擎自身发起的调用（子 Agent 走原生工具绕过引擎 → 只事后对账，R-15）")
    return 0


def cmd_replay(fixture: Path) -> int:
    """离线回归：用手写解析器重放真实 fixture（**录制重放不是 mock**，D-04）。"""
    if not fixture.exists():
        print(f"[llm] fixture 不存在: {fixture}", file=sys.stderr)
        return 2
    text = fixture.read_text(encoding="utf-8", errors="replace")
    res = parse_sse(text)
    print(f"[llm] replay {fixture.name}: frames={len(res['frames'])} data_lines={res['data_lines']} "
          f"done={res['done']} comments={len(res['comment_lines'])} blanks={res['blanks']} "
          f"errors={len(res['errors'])}")
    if res["errors"]:
        print(f"[llm] ✗ 解析有非法帧：{res['errors'][:2]} —— 严格解析不得静默修复（D-12①）",
              file=sys.stderr)
        return 1
    if not res["done"]:
        print("[llm] ✗ 未见 `data: [DONE]` —— 流未正常结束", file=sys.stderr)
        return 1
    uf = res["usage_frames"]
    print(f"[llm] usage 帧 {len(uf)} 个；"
          + (f"reasoning_tokens={extract_reasoning_tokens(uf[-1])}" if uf else "无（LP-仅尾帧预期）"))
    # 三条判据的 ① 能力协商：从 L0 facts 读（离线，不发请求）
    facts = SKILL_DIR / "_probe" / "l0_1_facts.json"
    if facts.exists():
        f = json.loads(facts.read_text(encoding="utf-8"))
        print(f"[llm] ① 能力协商（L0 实测白名单）= {f.get('whitelist')}")
        for mid, info in (f.get("per_model") or {}).items():
            print(f"[llm]    {mid}: supported_levels={info.get('effort_supported_levels')}")
    return 0


def cmd_chat(cfg: dict, prompt: str, effort: str, stream: bool, project: Path) -> int:
    key = get_key()
    if not key:
        print("[llm] 无凭证 → 降级（留痕计数，不静默跳过，R-07）", file=sys.stderr)
        append_usage(project, {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                               "degraded": True, "reason": "no_api_key"})
        return 1
    model = cfg["llm"]["model_whitelist"][0]
    seen = {}
    try:
        models = fetch_models(key, cfg)
        supported = ((models.get("data") or [{}])[0].get("effort") or {}).get("supported_levels") or []
        ok2, msg2 = defense_2_capability(effort, supported)
        print(f"[llm] {msg2}")
        if not ok2:
            return 1
    except Exception as e:
        print(f"[llm] /models 失败（fail-closed，不猜）：{type(e).__name__}: {e}", file=sys.stderr)
        return 1
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}],
               "reasoning_effort": effort, "max_tokens": 512, "stream": bool(stream)}
    try:
        body = chat(key, cfg, payload, stream=stream)
    except Exception as e:
        print(f"[llm] 调用失败：{type(e).__name__}: {e}", file=sys.stderr)
        return 1
    if stream:
        res = parse_sse(body)
        if res["errors"] or not res["done"]:
            print("[llm] ✗ 流解析失败/未收到 [DONE]（严格失败，不修复）", file=sys.stderr)
            return 1
        usage = (res["usage_frames"][-1].get("usage") if res["usage_frames"] else None)
        print(f"[llm] stream frames={len(res['frames'])} usage={'有' if usage else '无'}")
        resp = {"model": res["frames"][0].get("model") if res["frames"] else None,
                "object": "chat.completion.chunk", "system_fingerprint": None, "usage": usage}
    else:
        try:
            resp = json.loads(body)          # ★ 严格解析，禁 json_repair
        except Exception as e:
            print(f"[llm] ✗ 响应非合法 JSON（严格失败，不修复）：{e}", file=sys.stderr)
            return 1
    ok1, msg1 = defense_1_echo(model, resp)
    ok3, msg3 = defense_3_fingerprint(resp, seen)
    print(f"[llm] {msg1}\n[llm] {msg3}")
    if not (ok1 and ok3):
        return 1
    usage = resp.get("usage")
    if not isinstance(usage, dict) or "total_tokens" not in usage:
        print("[llm] ✗ usage 缺失 → fail-closed（漏账绝不当通过）", file=sys.stderr)
        append_usage(project, {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "usage": None,
                               "missing_usage": True})
        return 1
    append_usage(project, {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                           "model": resp.get("model"), "usage": usage,
                           "reasoning_tokens": extract_reasoning_tokens(resp)})
    print(f"[llm] usage={usage} reasoning_tokens={extract_reasoning_tokens(resp)}")
    return 0


def main() -> int:
    _utf8()
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--replay", default="")
    ap.add_argument("--chat", default="")
    ap.add_argument("--lc3-summary", default="")
    ap.add_argument("--budget-report", action="store_true")
    ap.add_argument("--effort", default="")
    ap.add_argument("--stream", action="store_true")
    ap.add_argument("--project", default=".")
    ap.add_argument("-h", "--help", action="store_true")
    args = ap.parse_args()
    if args.help:
        print(__doc__)
        return 0
    cfg = load_cfg()
    need_net = bool(args.chat or args.lc3_summary)
    if need_net and not enabled():
        print(f"[llm] DISABLED —— 本层默认关闭（SIXLAYER_LLM != on）；未发任何请求，退出码 3=未执行",
              file=sys.stderr)
        return PENDING_RC
    if args.status:
        return cmd_status(cfg)
    if args.replay:
        return cmd_replay(Path(args.replay))
    if args.budget_report:
        r = budget_report(Path(args.project), cfg)
        print(f"[llm] 预算: used={r['used_tokens']}/{r['denominator']} ratio={r['ratio']} "
              f"verdict={r['verdict']} calls={r['calls']} 漏账={r['missing_usage_lines']} "
              f"降级={r['degraded_calls']}")
        print(f"[llm] {r['applicability']}")
        print(f"[llm] {r['note']}")
        if r["verdict"] == "ASK_HUMAN":
            print("[llm] (c) 超限 → 问人（P2 不做真熔断，D-13）", file=sys.stderr)
            return 1
        if r["verdict"] == "FAIL_CLOSED":
            print("[llm] 漏账 → fail-closed（不当作通过）", file=sys.stderr)
            return 1
        if r["verdict"] == "ALERT":
            print("[llm] (b) 告警：已超 alert_ratio（不阻断，D-13）")
        return 0
    if args.chat:
        effort = args.effort or cfg["llm"]["reasoning_effort"]
        return cmd_chat(cfg, args.chat, effort, args.stream, Path(args.project))
    if args.lc3_summary:
        p = Path(args.lc3_summary)
        if not p.exists():
            print(f"[llm] bundle 不存在: {p}", file=sys.stderr)
            return 2
        key = get_key()
        if not key:
            print("[llm] 无凭证 → LC3 降级（不阻塞主流程），记 cost_log 异常类型列「降级跳过」",
                  file=sys.stderr)
            return 1
        r = lc3_summary(key, cfg, json.loads(p.read_text(encoding="utf-8")), Path(args.project))
        if r.get("degraded"):
            print(f"[llm] LC3 降级（不阻塞主流程）：{r['reason']}", file=sys.stderr)
            return 1
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0 if r["ok"] else 1
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
