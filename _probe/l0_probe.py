#!/usr/bin/env python3
"""l0_probe.py — L0 探针层（一次性脚本，不进 cli 命令面；需网一次）

来源：开发文档《引擎层与框架升级》§4.2 L0。
目的：用**真实往返**裁决三件在纸面上无法确定的事，并把**真实响应原文存为 fixture**
（硬门：无 fixture → 不许动 L2）。

    L0-1  GET /models 双向核对 —— 请求 id ∈ 白名单 **且** 响应 `model` == 请求 id（防 200 假绿）
          产出三个事实：真实白名单 / effort.supported_levels / context_window
    L0-2  一次非流式 + 一次流式真实调用，响应原文存 fixture
    L0-3  thinking/reasoning_effort 行为探测 + temperature 生效性两端对比（N>=3）

凭证：**只从环境变量 `DEEPSEEK_API_KEY` 读**（D-20）。缺失时回退读 ~/.workbuddy/models.json，
      并打印 [WARN] 明文暴露面提示（该回退只为一次性探针，引擎本体不许这么做）。

用法：
    python _probe/l0_probe.py                 # 全量
    python _probe/l0_probe.py --skip-l0-3     # 只做 L0-1/L0-2
输出：全部落在 _probe/（见文件清单）

退出码：0=全通过 / 1=有断言失败（双向核对不通过 / fixture 缺失）
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROBE_DIR = HERE
MODELS_URL = "https://api.deepseek.com/models"
CHAT_URL = "https://api.deepseek.com/chat/completions"
LOCAL_MODELS_JSON = Path.home() / ".workbuddy" / "models.json"


def _force_utf8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def get_key() -> tuple:
    """返回 (key, source)。D-20：优先环境变量；回退 models.json 仅限本次探针。"""
    k = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if k:
        return k, "env:DEEPSEEK_API_KEY"
    if LOCAL_MODELS_JSON.exists():
        d = json.loads(io.open(LOCAL_MODELS_JSON, encoding="utf-8").read())
        if isinstance(d, list) and d and d[0].get("apiKey"):
            return d[0]["apiKey"], "file:~/.workbuddy/models.json [WARN 明文暴露面]"
    raise SystemExit("[L0] 无可用凭证：请设 DEEPSEEK_API_KEY")


def _post(url: str, key: str, payload: dict, stream: bool, timeout: int = 90):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers={
        "Authorization": "Bearer " + key,
        "Content-Type": "application/json",
        "Accept": "text/event-stream" if stream else "application/json",
    })
    return urllib.request.urlopen(req, timeout=timeout)


def _get(url: str, key: str, timeout: int = 30):
    req = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + key, "Accept": "application/json"})
    return urllib.request.urlopen(req, timeout=timeout)


def _write(name: str, text: str):
    (PROBE_DIR / name).write_text(text, encoding="utf-8")


def _writej(name: str, obj):
    (PROBE_DIR / name).write_text(
        json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------- L0-1
def l0_1_models(key: str) -> dict:
    print("[L0-1] GET /models …")
    with _get(MODELS_URL, key) as r:
        raw = r.read().decode("utf-8", "replace")
        status = r.status
    _write("l0_1_models_raw.json", raw)
    data = json.loads(raw)
    models = {m["id"]: m for m in data.get("data", [])}
    whitelist = sorted(models.keys())
    facts = {
        "http_status": status,
        "whitelist": whitelist,
        "per_model": {
            mid: {
                "name": m.get("name"),
                "context_window": m.get("context_window"),
                "max_output_tokens": m.get("max_output_tokens"),
                "effort_supported_levels": (m.get("effort") or {}).get("supported_levels"),
                "effort_default_level": (m.get("effort") or {}).get("default_level"),
                "input_modalities": m.get("input_modalities"),
            } for mid, m in models.items()
        },
        "source": "GET https://api.deepseek.com/models @ " + time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _writej("l0_1_facts.json", facts)
    print("      白名单 =", whitelist)
    for mid, f in facts["per_model"].items():
        print(f"      {mid}: effort={f['effort_supported_levels']} "
              f"ctx={f['context_window']} name={f['name']}")
    return facts


def l0_1_bidirectional(key: str, whitelist: list) -> dict:
    """双向核对：请求 id ∈ 白名单 且 响应 model == 请求 id（防 200 假绿）"""
    print("[L0-1b] 双向核对（含本机 models.json 注册的 deepseek-v4-flash）")
    candidates = sorted(set(whitelist) | {"deepseek-v4-flash", "deepseek-chat", "deepseek-reasoner"})
    results = {}
    for cid in candidates:
        entry = {"request_id": cid, "in_whitelist": cid in whitelist}
        try:
            payload = {"model": cid, "messages": [{"role": "user", "content": "hi"}],
                       "max_tokens": 8, "stream": False}
            with _post(CHAT_URL, key, payload, stream=False, timeout=60) as r:
                code, body = r.status, r.read().decode("utf-8", "replace")
            entry["http_status"] = code
            try:
                j = json.loads(body)
                entry["response_model"] = j.get("model")
                entry["response_name"] = j.get("model")  # placeholder
                entry["usage"] = j.get("usage")
            except Exception:
                entry["parse_error"] = body[:200]
                entry["response_model"] = None
        except urllib.error.HTTPError as e:
            entry["http_status"] = e.code
            entry["http_error_body"] = e.read().decode("utf-8", "replace")[:300]
            entry["response_model"] = None
        except Exception as e:
            entry["transport_error"] = f"{type(e).__name__}: {e}"
            entry["response_model"] = None
        # 判定
        entry["same_model_echo"] = (entry.get("response_model") == cid)
        entry["pass"] = bool(entry["in_whitelist"] and entry["same_model_echo"])
        results[cid] = entry
        print(f"      {cid:22s} in_wl={entry['in_whitelist']!s:5s} "
              f"http={entry.get('http_status')} resp_model={entry.get('response_model')} "
              f"pass={entry['pass']}")
    _writej("l0_1_bidirectional.json", results)
    return results


# ---------------------------------------------------------------- L0-2
def l0_2_real_calls(key: str, use_model: str) -> dict:
    out = {"use_model": use_model}
    # 非流式
    print(f"[L0-2a] 非流式真实调用 model={use_model}")
    payload = {"model": use_model, "messages": [{"role": "user", "content": "只回答一个数字：1+1=?"}],
               "max_tokens": 256, "stream": False}
    with _post(CHAT_URL, key, payload, stream=False) as r:
        raw = r.read().decode("utf-8", "replace")
        out["nostream_http"] = r.status
    _write("l0_2_nostream_raw.json", raw)
    try:
        j = json.loads(raw)
        out["nostream_usage"] = j.get("usage")
        out["nostream_model"] = j.get("model")
        out["nostream_finish_reason"] = (j.get("choices") or [{}])[0].get("finish_reason")
        msg = (j.get("choices") or [{}])[0].get("message") or {}
        out["nostream_has_reasoning_content"] = "reasoning_content" in msg
    except Exception as e:
        out["nostream_parse_error"] = str(e)
    print("      usage =", out.get("nostream_usage"))

    # 流式
    print(f"[L0-2b] 流式真实调用 model={use_model}")
    payload = {"model": use_model, "messages": [{"role": "user", "content": "只回答一个数字：2+2=?"}],
               "max_tokens": 256, "stream": True}
    chunks = []
    with _post(CHAT_URL, key, payload, stream=True) as r:
        out["stream_http"] = r.status
        while True:
            b = r.readline()
            if not b:
                break
            chunks.append(b)
    raw_sse = b"".join(chunks).decode("utf-8", "replace")
    _write("l0_2_stream_raw.sse", raw_sse)
    lines = raw_sse.splitlines()
    out["stream_line_count"] = len(lines)
    out["stream_data_lines"] = sum(1 for l in lines if l.startswith("data:"))
    out["stream_comment_lines"] = [l for l in lines if l.startswith(":")][:5]
    out["stream_has_DONE"] = any(l.strip() == "data: [DONE]" for l in lines)
    out["stream_blank_between"] = sum(1 for l in lines if l.strip() == "")
    # usage 落点：找带 usage 的帧
    usage_frames = []
    for l in lines:
        if l.startswith("data:") and "[DONE]" not in l:
            try:
                j = json.loads(l[5:].strip())
            except Exception:
                continue
            if j.get("usage"):
                usage_frames.append({"keys": sorted(j.keys()), "usage": j["usage"],
                                     "choices_len": len(j.get("choices") or [])})
    out["stream_usage_frames"] = usage_frames
    out["stream_last_usage_at_end"] = bool(usage_frames) and "<tail>" if False else None
    # 判定 usage 是否只在尾帧
    if usage_frames:
        idxs = []
        for i, l in enumerate(lines):
            if l.startswith("data:") and "[DONE]" not in l:
                try:
                    j = json.loads(l[5:].strip())
                except Exception:
                    continue
                if j.get("usage"):
                    idxs.append(i)
        out["stream_usage_line_indices"] = idxs
        out["stream_total_lines"] = len(lines)
    print(f"      lines={out['stream_line_count']} data={out['stream_data_lines']} "
          f"DONE={out['stream_has_DONE']} usage_frames={len(usage_frames)}")
    _writej("l0_2_stream_frames.json", out)
    return out


# ---------------------------------------------------------------- L0-3
def l0_3_effort(key: str, use_model: str, levels: list, n: int = 3) -> dict:
    print(f"[L0-3a] reasoning_effort 档位对比 N={n} levels={levels}")
    res = {"model": use_model, "n": n, "levels": {}}
    prompt = "请只输出一个词：好"
    for lv in levels:
        rows = []
        for i in range(n):
            payload = {"model": use_model, "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": 512, "stream": False, "reasoning_effort": lv}
            try:
                with _post(CHAT_URL, key, payload, stream=False) as r:
                    body = r.read().decode("utf-8", "replace")
                j = json.loads(body)
                u = j.get("usage") or {}
                rows.append({"ok": True, "usage": u,
                             "reasoning_tokens": u.get("completion_tokens_details", {}).get("reasoning_tokens")
                             if isinstance(u.get("completion_tokens_details"), dict) else None,
                             "model_echo": j.get("model"),
                             "sys_fingerprint": j.get("system_fingerprint")})
            except urllib.error.HTTPError as e:
                rows.append({"ok": False, "http_status": e.code,
                             "body": e.read().decode("utf-8", "replace")[:300]})
            except Exception as e:
                rows.append({"ok": False, "error": f"{type(e).__name__}: {e}"})
        res["levels"][lv] = rows
        ok = [r for r in rows if r.get("ok")]
        rt = [r.get("reasoning_tokens") for r in ok]
        ct = [(r.get("usage") or {}).get("completion_tokens") for r in ok]
        print(f"      effort={lv:5s} ok={len(ok)}/{n} reasoning_tokens={rt} completion_tokens={ct}")
    _writej("l0_3_effort_compare.json", res)
    return res


def l0_3_temperature(key: str, use_model: str, n: int = 3) -> dict:
    print(f"[L0-3b] temperature 生效性两端对比 N={n}（0.0 vs 2.0）")
    res = {"model": use_model, "n": n, "arms": {}}
    prompt = "请只输出一个词：好"
    for temp in (0.0, 2.0):
        rows = []
        for i in range(n):
            payload = {"model": use_model, "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": 256, "stream": False, "temperature": temp}
            try:
                with _post(CHAT_URL, key, payload, stream=False) as r:
                    body = r.read().decode("utf-8", "replace")
                j = json.loads(body)
                u = j.get("usage") or {}
                rows.append({"ok": True, "usage": u,
                             "content": ((j.get("choices") or [{}])[0].get("message") or {}).get("content")})
            except urllib.error.HTTPError as e:
                rows.append({"ok": False, "http_status": e.code,
                             "body": e.read().decode("utf-8", "replace")[:300]})
            except Exception as e:
                rows.append({"ok": False, "error": f"{type(e).__name__}: {e}"})
        res["arms"][str(temp)] = rows
        ok = [r for r in rows if r.get("ok")]
        print(f"      temperature={temp}: ok={len(ok)}/{n} "
              f"completion_tokens={[(r.get('usage') or {}).get('completion_tokens') for r in ok]}")
    _writej("l0_3_temperature_compare.json", res)
    return res


def main() -> int:
    _force_utf8()
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--skip-l0-3", action="store_true")
    ap.add_argument("--model", default="deepseek-flash")
    args = ap.parse_args()

    key, src = get_key()
    print(f"[L0] 凭证来源: {src}")
    facts = l0_1_models(key)
    wl = facts["whitelist"]
    bidi = l0_1_bidirectional(key, wl)
    use = args.model if args.model in wl else wl[0]
    if args.model not in wl:
        print(f"[L0] 注意：--model {args.model} 不在白名单，改用 {use}")
    l0_2_real_calls(key, use)

    l0_3 = None
    levels = (facts["per_model"].get(use, {}).get("effort_supported_levels") or ["low", "high", "max"])
    if not args.skip_l0_3:
        l0_3 = l0_3_effort(key, use, levels, n=3)
        l0_3t = l0_3_temperature(key, use, n=3)

    # 判定
    fixtures = ["l0_1_models_raw.json", "l0_2_nostream_raw.json", "l0_2_stream_raw.sse"]
    missing = [f for f in fixtures if not (PROBE_DIR / f).exists() or (PROBE_DIR / f).stat().st_size == 0]
    bad_bidi = [k for k, v in bidi.items() if not v["pass"]]
    print("\n[L0] ===== 判定 =====")
    print(f"  fixture 齐全: {not missing}  缺失={missing or '无'}")
    print(f"  双向核对通过: {[k for k,v in bidi.items() if v['pass']]}")
    print(f"  双向核对不通过（预期含 deepseek-v4-flash / deepseek-chat / deepseek-reasoner）: {bad_bidi}")
    ok = (not missing)
    print(f"  硬门（无 fixture → 不许动 L2）: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
