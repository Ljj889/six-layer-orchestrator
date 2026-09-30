# engine_config.md · 引擎参数单一来源（canonical source）

> **版本**：v1.0 · 2026-09-30 · 来源：引擎层研讨 D-18 / R-08 / R-14 收敛
> **定位**：**温度 / 推理档位 / 预算 / 超时 / 模型白名单 / 校准窗口**六类参数**只在本文件定义一次**；他处一律引用（canonical source 指针），**禁止硬编码第二份**。
> **机读镜像**：`scripts/engine_config.json`（由本文件同步；两者不一致 → **FAIL**）。
> **关联**：SKILL.md「引擎参数单一来源」节（rule 号映射表在此）；rule 56 / rule 83 / rule 84。

---

## 一、参数表（每键 schema + 合法域）

| 键 | 类型 | 合法域 | 默认值 | 非法处置 | 依据 |
|---|---|---|---|---|---|
| `llm.model_whitelist` | array[string] | **实测白名单**（L0-1 · 2026-09-30）`["deepseek-flash","deepseek-v4-pro"]` | 同左 | **FAIL** | L0 实测：`deepseek-chat` / `deepseek-reasoner` / `deepseek-v4-flash` **返回 HTTP 200 但响应 `model` 被静默改回 `deepseek-flash`**（**不是 404**）→ 只看状态码 100% 漏判，必须双向核对 |
| `llm.reasoning_effort` | enum | **`low` / `high` / `max`**（L0-1 实测 `effort.supported_levels`，**无 `none`**） | `high` | **FAIL** | L0-3 实测档位**确实生效**（`high` 三次 reasoning_tokens 完全一致=18，`low`/`max` 显著不同）；`none` 未在 supported_levels → **非法** |
| `llm.temperature` | number | `0.0`–`2.0` | `0.0` | **FAIL** | **thinking mode 下无效** —— L0-3b 实测组内方差 > 组间差，**不能证明有效**；仅登记备案，**不得用作档位手段** |
| `llm.request_timeout_sec` | integer | `1`–`600` | `120` | **FAIL** | 连接层超时（自建，D-11） |
| `llm.max_retries` | integer | `0`–`5` | `2` | **FAIL** | 连接层退避（自建，先手写不用 tenacity） |
| `budget.window_tokens` | integer > 0 | > 0 | **校准窗口值**（**≠ 模型上限 1048576**） | **FAIL** | **禁用 API 上限做分母** —— rule 83 先例：分母错 127 倍 → 压缩永不触发。L0-1 实测 `context_window=1048576`，仅作**上限参考** |
| `budget.per_wave_tokens` | integer > 0 | > 0 | `200000` | **FAIL** | Wave 级预算 |
| `budget.alert_ratio` | number | `0.0`–`1.0` | `0.8` | **FAIL** | D-13 (b) 告警线 |
| `budget.ask_human_ratio` | number | `0.0`–`1.0` | `1.0` | **FAIL** | D-13 (c) 超限问人线 |
| `timeout.dispatch_sec` | integer > 0 | > 0 | `1800` | **FAIL** | 子 Agent 派发超时 |
| `calibration.window_days` | integer > 0 | > 0 | `30` | **FAIL** | 校准窗口（token 账本分母来源） |
| `engine.enabled` | bool | `true`/`false` | `true`（env `SIXLAYER_ENGINE=off` 可覆盖） | **FAIL** | R-01 总开关 |

**兼容映射（显式登记为已知等价类 · 防静默语义变更）**：

| 外部写法 | 映射到 | 说明 |
|---|---|---|
| `minimal` | `low` | 官方兼容映射 —— **登记在此，不得靠猜** |
| `medium` | `high` | 第三方 SDK 常见别名 |
| `none` | **（无映射 → FAIL）** | L0-1 实测 `supported_levels` **不含 `none`** → 不许静默降级到 `low`，**必须显式报错** |
| `max` | `max` | 直通 |

> 未登记的值 → **FAIL**（不许静默取默认）。这就是 R-14 的解药：参数漂移**必须有 Traceback**。

---

## 二、校验实现（零依赖优先）

```python
# 手写约 20 行，零依赖（推荐）
SCHEMA = {
    "llm.reasoning_effort": {"type": "enum", "values": ["low", "high", "max"]},  # L0-1 实测域
    "budget.window_tokens": {"type": "int", "min": 1},
    "budget.alert_ratio":   {"type": "float", "min": 0.0, "max": 1.0},
    # ...
}

def _check(key, value):
    spec = SCHEMA.get(key)
    if spec is None:
        raise ConfigError(f"未知键 {key!r}（engine_config 里没有定义 = FAIL）")
    t = spec["type"]
    if t == "enum" and value not in spec["values"]:
        raise ConfigError(f"{key}={value!r} 不在合法域 {spec['values']} —— 不许静默取默认")
    if t == "int" and (not isinstance(value, int) or isinstance(value, bool)):
        raise ConfigError(f"{key} 必须是整数，实际 {type(value).__name__}")
    if t == "int" and value < spec.get("min", -(10**18)):
        raise ConfigError(f"{key}={value} 越下界 {spec['min']}")
    if t == "float" and not (spec.get("min", float("-inf")) <= value <= spec.get("max", float("inf"))):
        raise ConfigError(f"{key}={value} 越界 [{spec.get('min')},{spec.get('max')}]")
    return value
```

**唯一允许的库**：`fastjsonschema`（纯 Python、闭包 1、BSD-3，26.8 KB）。
**禁用**：`pydantic`（`pydantic-core` Rust 二进制 1.99 MB）、`jsonschema`（`rpds-py` Rust 编译产物）—— 与"零依赖可移植"冲突（D-20 / K-6）。

---

## 三、启动打印（可 grep）

```
[engine_config] reasoning_effort=high source=references/engine_config.md
[engine_config] window_tokens=192000 (calibrated, window_days=30)
[engine] version=3.21.0 addressed=C:\Users\one\.workbuddy\skills\六层编排框架 repo_version=3.21.0 match=true
[engine] bypass (SIXLAYER_ENGINE=off)          # 仅当总开关关闭
```

**D-09 运行时寻址（R-06）**：运行时**寻址 = 当前平台副本所在目录**；启动打印版本号并与仓库版本核对，**不一致 → 警告 + 记 `cost_log` 异常类型列**。

---

## 四、与 `cost_log` 的关系

- `cost_log.md` 的**第 6 列「异常类型」**是唯一记录"参数/寻址/降级告警"的落点（如 `异常类型: 参数非法` / `降级跳过` / `版本漂移`）。
- **参数值本身不进 cost_log**（那是定长行，插词破契约）—— 值只在启动行打印 + 本文件定义。

---

## 附：本文件自身的未验证声明

- 白名单、`supported_levels`、`context_window` 已由 **L0 探针真实往返实测**（`_probe/l0_report.md` + `_probe/l0_1_facts.json`），标 `[事实]`（2026-09-30）。
- `reasoning_effort` 合法域以 **L0-1 实测 `supported_levels`** 为准（`low/high/max`）；**模型换代后必须重跑 `python _probe/l0_probe.py`**，本文件的数字一律以最近一次 L0 fixture 为准。
- 数值默认值（超时/重试/预算/告警比）仍为**工程默认**（`[假设]`），出现实测数据后按 R-13 由脚本自报更新。
