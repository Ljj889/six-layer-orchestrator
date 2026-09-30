# L0 探针报告（2026-09-30 · 真实往返取证）

> **性质**：一次性探针（不进 cli 命令面），需网一次。产出 = **真实响应原文 fixture** + 三条纸面上无法确定的裁决。
> **硬门**：**无 fixture → 不许动 L2**。本报告结论 = `PASS`（fixture 齐全）。
> **凭证来源**：`DEEPSEEK_API_KEY` 未设 → 回退 `~/.workbuddy/models.json`（**该回退仅限本次探针**；引擎本体按 D-20 只从环境变量读）。
> 复跑：`python _probe/l0_probe.py`

---

## 一、L0-1 `GET /models` 双向核对（防 200 假绿）

**接口**：`GET https://api.deepseek.com/models` → HTTP 200

| 项 | 实测值 |
|---|---|
| **真实白名单** | `deepseek-flash`（DeepSeek-V4.1-Flash）、`deepseek-v4-pro`（DeepSeek-V4-Pro） |
| **`effort.supported_levels`** | **`["low","high","max"]`**（两个模型相同）· `default_level = "high"` |
| **`context_window`** | **1048576** |
| **`max_output_tokens`** | 393216 |
| `input_modalities` | flash = `["text","image"]`（**支持图像**）；pro = `["text"]` |

### 双向核对结果（请求 id ∈ 白名单 **且** 响应 `model` == 请求 id）

| 请求 id | 在白名单 | HTTP | 响应 `model` | 判定 |
|---|---|---|---|---|
| `deepseek-flash` | ✅ | 200 | `deepseek-flash` | ✅ PASS |
| `deepseek-v4-pro` | ✅ | 200 | `deepseek-v4-pro` | ✅ PASS |
| **`deepseek-v4-flash`**（本机 `models.json` 注册的 id） | ❌ | **200** | **`deepseek-flash`（被静默改回）** | ❌ **FAIL = 200 假绿** |
| `deepseek-chat` | ❌ | **200** | **`deepseek-flash`（被静默改回）** | ❌ **FAIL = 200 假绿** |
| `deepseek-reasoner` | ❌ | **200** | **`deepseek-flash`（被静默改回）** | ❌ **FAIL = 200 假绿** |

**结论（比研讨文档更强的一条）**：文档 §5.4 预测"提交后 HTTP 200 但 `model` 静默变回"，**实测完全命中**；且 R-16 的未证实项"`deepseek-chat`/`reasoner` 是否真 404"**已裁决：不是 404，而是 200 + 静默改 model** —— 即**停用模型不会报错，只会被换成 `deepseek-flash`**。这是"双向核对"必须成为硬 Gate 的直接证据（只看 HTTP 状态码 100% 漏判）。

---

## 二、L0-2 真实调用 fixture（已落盘）

| fixture | 内容 |
|---|---|
| `l0_1_models_raw.json` | `/models` 原始响应 |
| `l0_2_nostream_raw.json` | 非流式原始响应（含 usage 落点） |
| `l0_2_stream_raw.sse` | 流式原始 SSE 字节（50 行 / 25 个 `data:` 行 / 含 `[DONE]`） |
| `l0_2_stream_frames.json` | 流式帧解析事实（usage 帧位置） |

**非流式 usage 实测结构**（**校准窗口与账本的真实字段**）：
```json
{"prompt_tokens":39,"completion_tokens":22,"total_tokens":61,
 "prompt_tokens_details":{"cached_tokens":0},
 "completion_tokens_details":{"reasoning_tokens":20},
 "prompt_cache_hit_tokens":0,"prompt_cache_miss_tokens":39}
```
→ **`reasoning_tokens` 落点 = `usage.completion_tokens_details.reasoning_tokens`**（D-12③ 判据②的数据源，实测确认存在）。

**流式实测**：`lines=50`、`data:` 行 25、`[DONE]` 存在、**usage 只在 1 个帧且位于末尾**（`usage_frames=1`）→ 与 R-03 预判一致（"usage 只在尾帧"成立）。

---

## 三、L0-3 `reasoning_effort` 档位生效性（N=3）

| effort | reasoning_tokens（3 次） | completion_tokens |
|---|---|---|
| `low` | 36 / 34 / 61 | 38 / 36 / 63 |
| `high` | **18 / 18 / 18** | 20 / 20 / 20 |
| `max` | 57 / 32 / 56 | 59 / 34 / 58 |

**判定②（机器可读生效证据）通过**：`high` 三次**完全一致（18）**，而 `low`/`max` 显著不同且波动 → **参数确实到达模型并改变了行为**（不是被忽略的死参数）。
→ 与 D-12③ 一致：**`reasoning_effort` 是有效档位手段**。

## 四、L0-3b `temperature` 生效性（0.0 vs 2.0，N=3）

| temperature | completion_tokens（3 次） |
|---|---|
| 0.0 | 55 / 53 / 35 |
| 2.0 | 94 / 20 / 48 |

**判定：证据不足以证明 temperature 有效**——两组**组内方差（0.0 组极差 20；2.0 组极差 74）大于组间差**，`completion_tokens` 不是 temperature 的可靠代理指标。
→ **处置**：维持 D-12③ —— **不用 `temperature` 做档位手段**（官方原文"thinking mode 下无效" + 本测无法证伪，二者同向）；`temperature` 在 `engine_config` 中**仅登记备案**。

---

## 五、回灌（本报告对框架的直接影响）

| # | 实测发现 | 回灌动作 |
|---|---|---|
| 1 | `supported_levels = ["low","high","max"]`（**无 `none`**） | `engine_config.md` / `engine_config.json` 的 `reasoning_effort` 合法域 **从 `none/low/high/max` 收紧为 `low/high/max`**（L0 裁决取代纸面推测） |
| 2 | `context_window = 1048576` | 登记为**真实上限**；**但校准窗口 ≠ 上限**（rule 83：分母错 127 倍 → 永不触发），校准仍走 `calibration.window_days` |
| 3 | 停用/错误 id **返回 200 并静默改 model** | 双向核对升为**硬 Gate**；`engine_config` 白名单 = 实测两个 id |
| 4 | `deepseek-flash` **支持图像** | 登记（未来多模态可用性） |
| 5 | `reasoning_tokens` 落点确认 | D-12③ 判据② 的数据源可用 |

---

## 六、未验证声明（诚实边界）

- 本次仅覆盖 **`deepseek-flash` / `deepseek-v4-pro` 两个 id**；新增模型/新别名需重跑本探针（`python _probe/l0_probe.py`）。
- `temperature` 的"无效"是**官方文档 + 本测无法证伪**的合成结论，**不是**本测直接证明的（本测只证明 `completion_tokens` 不适合作代理指标）。
- 档位对比 N=3（小样本）；结论只需"有差异"即可支撑"参数生效"，不用于估计效应量。
