# 模型档位路由（L0 派发依据 · v3.7 新增）

WorkBuddy 的子 Agent（Agent 工具）通过 `model` 参数规定**档位**，三档：

- `lite`：快、便宜，适合小改动 / 检索 / 机械对齐
- `default`：均衡，适合大多数写码与审查
- `reasoning`：强推理，适合架构决策、复杂分析、独立复核

本表把框架角色绑定到档位。调度器（主 Agent / 执行 Agent）派发时，**把档位填进 Agent() 的 `model` 参数**，并照 rule 38 在 cost_log.md 记录档位。

> 对应框架 rule 47（档位-复杂度匹配表）。role 12/18/19/20 已定义角色职责，本文件只补"派发时用哪档"。

---

## 角色 → 档位映射表

| 角色 | 派发档位 | 绑定理由 | 升降档规则 |
|---|---|---|---|
| **架构师 (Architect)** | `reasoning` | 拆模块 + 写 interfaces.md 契约 = 最主观、需深推理；调用极少、成本可控（rule 47：reasoning 档最贵，但默认轻量档不堆人） | 项目偏业务可行性且简单时，可降到 `default` 用 HY3 式实用推理 |
| **架构评审员 (Reviewer-Arch)** | `reasoning` | 独立第二视角挑盲区，需强推理（rule 20 轻量档） | — |
| **程序员 (Programmer)** | `default` | 代码能力 + 工具调用 + 结构化输出；高频生成代码，default 平衡成本与质量 | <50 行机械改动 → `lite`（rule 47/49）；最难模块 → 升 `reasoning` |
| **审查员 (Reviewer)** | `default` | 严查契约 / 签名漂移，需精准结构化输出与低幻觉 | 细致比对或复杂契约可升 `reasoning` |

---

## 档位判定表（rule 47 派发自查 · v3.17.0 两维起步）

> rule 47 的病根：原判据"<50 行→lite"用的是**派发前不可知的行数**（结果变量当决策输入）。v3.17.0 改为**派发前可知的两维**定档，行数降为事后校验信号。

| 维度 | 低(0) | 中(1) | 高(2) |
|---|---|---|---|
| 认知类型 | 机械对齐 / 检索 / 探针 | 标准写码 | 设计决策 / 跨模块权衡 |
| 失败代价 | 只读 / 孤岛 | 单模块返工 | 动 interfaces / 共享模块 / 数据语义 |

**判定**：
- 基线档按**认知类型**：低→`lite`、中→`default`、高→`reasoning`；
- **失败代价 = 高**（动 interfaces / 共享模块 / 数据语义）→ 基线档**升一档**；
- **行数 = 事后校验信号**：声明"机械改动"实际 >80 行 → 记「档位误判」进 cost_log 第 9 列，不回改档位，交 `audit` 事后纠偏。

**试运行规则（kill 条件已挂）**：首项目对比"判定表输出 vs 事后实际复杂度"——命中率 <60% → 加回第三维「契约面」（用二元代理：是否动 interfaces.md / 是否新增共享模块）；≥60% → 升格为 dispatch-check 强制判据。

---

## 派发示例（执行 Agent 照做）

```
# 框架师 —— 最深推理
Agent(model="reasoning", subagent_type="general-purpose", prompt="你是架构师...（注入蓝图+调研方向）")

# 程序员 —— 均衡写码（小改动改 lite）
Agent(model="default",   subagent_type="general-purpose", prompt="你是程序员...（注入 module_spec）")

# 审查员 —— 严查契约
Agent(model="default",   subagent_type="general-purpose", prompt="你是审查员...（注入 contract+产物）")
```

---

## 重要限制（派发前必读，防止文档写了不生效）

1. **`model` 参数只接受档位，不接受具体模型名。** 你写 `model="reasoning"` 即可，但**不能写 `model="DeepSeek V4 Pro"` 或 `model="HY3"`**——该档内具体调哪个模型由 WorkBuddy 平台决定，不在文档可控范围。
2. **"程序员用 DeepSeek、审查员用 HY3 跨家族独立校验"在原生 Agent 工具下无法实现。** 原生档位抽象掉了具体模型家族。若你确实需要强制"审查员换一个不同家族的模型"以获得真独立校验，必须**自行接管 API**（像 ChatCut 那样直接拿 key 调不同模型、自己写编排层），不走原生 Agent 工具。
3. **同档位也有独立性：** 审查员与程序员本就是不同 Agent 实例，已具备基础独立性；想要更强区分，可让审查员走 `reasoning` 档（与程序员 `default` 拉开），作为原生档位下"弱跨家族"替代。

---

## 与 cost_log 联动（rule 38 / 53）

每次派发在 `cost_log.md` 追加定长记录，档位列即本表派发档位：

`[时间] | [派发对象] | [档位 lite/default/reasoning] | [预估成本] | [结果 成功/失败/时长] | [异常类型]`

通过 grep 档位列即可审计"是否按本表路由"（如架构师是否真的走了 reasoning 档）。
