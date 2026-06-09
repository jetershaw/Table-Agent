# Table Agent 性能提升规格说明

## 1. 项目目标

提升 `/mnt/shared-storage-user/mineru2-shared/xiaojutao/Table-Agent` 在 48 条
large-table benchmark 上的 `agent_avg_teds`，同时系统性分析并减少现有
regression case。

本轮工作不以盲目调参为主，而是先对已有 48 条结果做离线诊断，识别主要错误
pattern，再针对最大错误簇逐步引入可验证的策略改动。

## 2. 项目范围

本轮工作包括：

1. 对已有 48 条评估结果做 case-level 统计分析。
2. 归因 regression pattern，包括但不限于：
   - 切分后列数不一致。
   - 不该切却切了。
   - 应该切但切分不足。
   - crop 边界切穿内容。
   - crop 识别 OTSL 异常。
   - 合并阶段造成结构损坏。
   - single-chunk agent 结果相对 baseline rerun 波动。
3. 新增离线诊断报告或脚本，辅助后续实验复现。
4. 在真实 pipeline 中引入不依赖 GT 的策略：
   - Qwen 判断 `split / no-split`。
   - Qwen 说明复杂度类型和切分风险。
   - 必要时调整切分策略。
   - 必要时增加 crop 级 OTSL 后处理。
   - 必要时比较保守策略和积极策略。
5. 在固定当前评估环境下跑 smoke 或 48 条 benchmark，对比改动效果。

## 3. 不做什么

1. 运行时不读取 GT `solution`。
2. 运行时不使用 TEDS 分数做决策。
3. 运行时不把 baseline 结果作为 agent fallback 输入。
4. 不做为了 benchmark 泄漏答案的样本特化逻辑。
5. 不以单个 case 的提升作为最终成功标准。
6. 不一次性大改多个模块后再统一验证。
7. 不在没有诊断证据的情况下随意增加高成本多轮调用。
8. 不更换 MinerU 调用架构；默认继续使用
   `mineru_vl_utils.MinerUClient`，除非另立验收项并明确确认。

## 4. 允许的运行时输入

Agent 策略运行时可以使用：

- 原始表格图片。
- CV 生成的候选切点。
- Qwen 对图片和候选切点的判断。
- MinerU 对整图或 crop 的识别输出。
- OTSL/HTML 自身结构信号。
- crop 数量、图片尺寸、行列估计、warning 等元信息。

Agent 策略运行时不可以使用：

- GT HTML。
- TEDS 分数。
- baseline parse result 作为 fallback 输入。
- 离线诊断中得到的样本 ID 白名单或黑名单。

## 5. 总体验收标准

最终希望至少满足以下之一，优先级从高到低：

1. 48 条 benchmark 的 `agent_avg_teds` 高于当前基线
   `0.8926355322939662`。
2. 在不明显降低 `agent_avg_teds` 的前提下，减少大幅 regression case。
3. 如果保守策略和积极策略方向冲突，需要分别给出结果，并说明推荐采用哪一版。

最终报告需要包含：

- 改动前后 `baseline_avg_teds`、`agent_avg_teds`、absolute improvement、
  relative improvement。
- regression 数量变化。
- worst regression 变化。
- most improved / most regressed case 列表。
- 新增策略的运行时依赖说明，确认没有 GT/TEDS 泄漏。

## 6. 分阶段验收项

### 验收项 1：离线诊断统计

目标：新增或生成一份诊断能力，读取已有 48 条 run/scored artifacts，输出
case-level 统计。

验收标准：

- 能列出每条 case 的：
  - index/image
  - baseline_teds
  - agent_teds
  - delta_teds
  - chunk_count
  - split_iterations
  - warnings
  - crop row/col estimates
  - agent status
- 能按主要信号分组统计 regression。
- 不修改主流程。
- 跑通后 git commit。

### 验收项 2：错误 pattern 归因报告

目标：基于验收项 1 的结果，形成可读报告，明确优先处理的错误簇。

验收标准：

- 列出 `delta_teds < 0` 的主要类别。
- 标出最大错误 pattern。
- 区分切分问题、识别问题、合并问题、single-chunk rerun 波动等。
- 给出下一步策略选择建议。
- 不修改主流程。
- 跑通后 git commit。

### 验收项 3：Qwen split/no-split 决策设计

目标：设计并实现低成本 Qwen 决策，让 agent 在切分前判断是否应该切。

验收标准：

- Qwen 只看图像、图片尺寸、候选切点等无 GT 信息。
- 输出结构化 JSON，例如：
  - `should_split`
  - `complexity`
  - `risk_factors`
  - `cuts`
  - `reason`
- 解析失败时有安全降级策略。
- 通过 smoke case。
- 跑通后 git commit。

### 验收项 4：保守策略实验

目标：优先减少 regression。倾向于不确定就少切或不切。

验收标准：

- 运行时不使用 GT/TEDS/baseline fallback。
- 对一组 smoke 或完整 48 条跑通。
- 和当前 48 条结果对比：
  - regression 数量是否下降。
  - worst regression 是否改善。
  - agent_avg_teds 是否可接受。
- 跑通后 git commit。

### 验收项 5：积极策略实验

目标：尝试进一步提高平均 TEDS。允许在 Qwen 判断复杂表格时更积极切分，但成本
不能太高。

验收标准：

- 额外模型调用数量受控。
- 对一组 smoke 或完整 48 条跑通。
- 和保守策略、当前基线对比：
  - agent_avg_teds 是否提升。
  - 新增 regression 是否可接受。
- 跑通后 git commit。

### 验收项 6：OTSL/crop 后处理实验

目标：如果诊断显示主要问题来自 crop 识别或合并，则加入不依赖 GT 的结构修正。

验收标准：

- 后处理只基于 OTSL 自身结构和 crop 元信息。
- 能处理至少一种明确 pattern，例如列数不一致、空 crop、非法 token、重复边界行等。
- 对 smoke 或完整 48 条跑通。
- 有对比结果。
- 跑通后 git commit。

### 验收项 7：最终策略选择与清理

目标：在保守、积极、后处理实验中选择推荐方案，清理临时实验代码或明确保留实验
入口。

验收标准：

- 给出最终推荐策略。
- 48 条 benchmark 有完整结果。
- 文档记录复现命令、环境、artifact 路径。
- 确认运行时无 GT/TEDS 泄漏。
- 最终 git commit。

## 7. 版本控制要求

编码阶段规则：

1. 一次只做一个验收项。
2. 每个验收项开始前先说明要改什么。
3. 每个验收项完成后必须跑通对应验证。
4. 验证通过后立即 `git commit`。
5. 后续如果改坏，只回退最近一个小 commit，不大面积回滚。
6. 不混入无关重构。
7. 不覆盖用户已有未提交改动。
