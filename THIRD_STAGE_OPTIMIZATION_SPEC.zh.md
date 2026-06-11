# Table Agent 第三阶段性能提升 SPEC：Regression-aware Re-split 与 Fallback

## 1. 项目目标

在当前 48 条 large-table benchmark 上，进一步提升 `agent_avg_teds`。

当前最好结果：

| metric | value |
| --- | ---: |
| count | 48 |
| baseline_avg_teds | 0.8614947094362552 |
| agent_avg_teds | 0.9038593040110346 |
| absolute_improvement | 0.04236459457477948 |

第三阶段目标优先级：

1. **首要目标**：提升 48 条 `agent_avg_teds`，目标高于当前 `0.9038593040110346`。
2. **次要目标**：减少明显 regression，尤其是由切分/合并异常导致的坏例。
3. **成本目标**：增加的 MinerU/Qwen 调用要可统计、可解释，不能无上限重试。

## 2. 项目范围

本阶段聚焦以下方向：

1. 分析当前最新 48 条 aggressive run 中的 regression case。
2. 识别可由无 GT 信号触发的异常模式，例如：
   - `column_count_inconsistent`
   - illegal OTSL token
   - empty crop / failed crop
   - crop 行列估计差异过大
   - 合并后结构明显异常
   - Qwen 判断 split risk high
3. 先实验验证不同 **re-split/retry 策略** 是否有效：
   - 改切点位置。
   - 改切分段数。
   - header-aware 策略。
   - Qwen header 判断辅助切分。
4. 在验证 re-split 有效性之后，再定义成本档位：
   - `low`
   - `medium`
   - `high`
   - `xhigh`
5. 引入 fallback 策略：
   - 只在 retry/re-split 后仍异常时触发。
   - fallback 由 agent 自己重新调用一次 MinerU 整图识别。
   - 不复用 baseline parse result。
6. 在 metadata 中记录：
   - 是否触发 retry。
   - retry 类型。
   - 是否触发 fallback。
   - fallback 原因。
   - 最终选择的结果来源。
   - 额外 MinerU/Qwen 调用次数。
   - 运行耗时。

## 3. 不做什么

1. 运行时不读取 GT `solution`。
2. 运行时不读取 TEDS/TEDS-S 分数。
3. 运行时不复用 baseline parse result 作为 fallback。
4. 不基于 case ID 做白名单/黑名单特化。
5. 不为了单个 case 牺牲整体 `agent_avg_teds`。
6. 不一开始就固定 `high/xhigh` 策略；必须先通过实验验证 re-split 方法。
7. 不做无限重试。
8. 不在未记录成本的情况下增加额外模型调用。
9. 不把离线诊断规则直接当成运行时规则，除非实验验证净收益为正。

## 4. 运行时允许输入

运行时可以使用：

- 原始表格图片。
- CV 候选切点。
- Qwen 对原图、候选切点、crop/预览的判断。
- MinerU 对整图或 crop 的真实 PPL 输出。
- OTSL token 合法性。
- crop 行列估计。
- 合并后的 OTSL/HTML 结构信息。
- 当前 agent metadata。

运行时不可以使用：

- GT HTML。
- TEDS/TEDS-S。
- baseline parse result。
- 离线 case ID 标签。

## 5. 实验原则

### 5.1 先 retry，再 fallback

默认顺序：

1. 正常 aggressive split + merge。
2. 如果出现高置信异常，先尝试 re-split/retry。
3. 如果 retry 后仍异常，再调用一次 MinerU 整图 fallback。
4. fallback 结果可以直接作为最终 `agent_parse_result`。

原因：

- 目标仍然是提升 agent 能力，不希望过早抹掉 split 带来的收益。
- fallback 是下限保护，不是主要增益策略。

### 5.2 先验证 re-split 方法，再定义成本档位

不要一开始就假设 `high/xhigh` 怎么做。先单独实验：

1. 改切点位置是否有效。
2. 改切分段数是否有效。
3. header-aware 是否有效。
4. Qwen header 判断是否有效。
5. 混合策略是否优于单策略。

实验完成后，再决定：

- `medium` 用什么。
- `high` 用什么。
- `xhigh` 用什么。

### 5.3 fallback 触发条件必须验证

候选触发条件不能直接进入主流程。需要离线验证：

- 触发后 fallback/retry 是否提升这些 case。
- 是否误杀原本 agent 已经优于整图识别的 case。
- 净收益是否为正。
- 额外成本是否可接受。

## 6. 初始成本约束草案

最终档位待 re-split 实验后确定。初步上限：

- 默认路径：最多 1 次 Qwen split review + N 次 MinerU crop 识别。
- retry 路径：最多额外 1-2 轮 re-split 实验，具体次数由验证结果决定。
- fallback 路径：最多额外 1 次 MinerU 整图识别。
- crop 数：默认 1-2 个，实验可放宽到最多 3 个。
- 单样本超时：默认 600 秒，极端实验可放宽到 900 秒。
- 所有额外调用必须写入 metadata 和最终报告。

## 7. 验收项

### 验收项 1：第三阶段离线诊断与 retry 候选 case 统计

目标：基于当前最新 48 条 aggressive run，找出适合 retry/fallback 的候选 case。

验收标准：

- 输出每条 case 的：
  - index/image
  - baseline_teds
  - agent_teds
  - delta_teds
  - warnings
  - chunk_count
  - split_decision
  - crop 行列估计
  - 是否属于 retry 候选
  - 是否属于 fallback 候选
- 候选条件必须是无 GT 运行时可观测信号。
- 离线报告可以使用 TEDS/GT 做归因，但明确不能进入运行时。
- 不修改主流程。
- 跑通后 git commit。

### 验收项 2：re-split 策略 A/B 实验设计与 smoke

目标：分别验证不同 re-split 方法是否能改善 regression case。

候选策略：

- A：改切点位置。
- B：改切分段数。
- C：header-aware 切分。
- D：Qwen header 判断辅助切分。

验收标准：

- 每种策略至少在候选 regression case 上跑 smoke。
- 记录每种策略的：
  - agent_avg_teds
  - improvement/regression case 数
  - worst regression 变化
  - 额外 MinerU 调用数
  - 额外 Qwen 调用数
  - 平均耗时
- 给出哪种 re-split 策略值得进入主流程的结论。
- 跑通后 git commit。

### 验收项 3：实现 retry-first 策略

目标：把通过验证的 re-split 方法接入 agent 主流程，但暂不默认启用所有高成本策略。

验收标准：

- retry 只由无 GT 信号触发。
- retry 次数有上限。
- metadata 记录：
  - `retry_triggered`
  - `retry_reason`
  - `retry_strategy`
  - `retry_attempts`
  - `extra_mineru_calls`
  - `extra_qwen_calls`
  - `selected_result_source`
- smoke 跑通。
- 不复用 baseline。
- 跑通后 git commit。

### 验收项 4：fallback 反事实实验

目标：验证 fallback 到 agent 自己重新调用 MinerU 整图识别是否真正提升。

验收标准：

- 对候选 fallback case 额外跑 full-image MinerU。
- 比较：
  - 原 split+merge agent 结果
  - retry 后结果
  - fallback full-image 结果
- baseline 只作为离线参考，不参与运行时选择。
- 统计 fallback 是否净提升：
  - 提升 case 数
  - 误杀 case 数
  - agent_avg_teds 变化
  - 额外调用成本
- 给出 fallback 触发条件是否进入主流程的结论。
- 跑通后 git commit。

### 验收项 5：实现 retry-then-fallback 策略

目标：将验证有效的 fallback 策略接入 agent 主流程。

验收标准：

- 默认顺序为 retry -> fallback。
- fallback 由 agent 重新调用 MinerU 整图识别。
- 不复用 baseline。
- fallback 结果可直接作为最终 `agent_parse_result`。
- metadata 记录：
  - `fallback_triggered`
  - `fallback_reason`
  - `fallback_raw_response.path`
  - `selected_result_source`
  - 额外成本
- smoke 跑通。
- 跑通后 git commit。

### 验收项 6：成本档位实验

目标：根据前面实验结果，定义并比较 `low/medium/high/xhigh`。

验收标准：

- 档位定义必须基于已验证策略，而不是预设。
- 每个档位跑 smoke 或完整 48 条。
- 至少记录：
  - `agent_avg_teds`
  - `absolute_improvement`
  - regression 数量
  - worst regression
  - 额外 MinerU 调用数
  - 额外 Qwen 调用数
  - 平均耗时
- 说明哪个档位性价比最好。
- 跑通后 git commit。

### 验收项 7：完整 48 条评估与最终选择

目标：选择第三阶段最终推荐策略，并在 48 条 benchmark 上完整评估。

验收标准：

- 完整 48 条跑通。
- `agent_avg_teds` 高于当前最佳 `0.9038593040110346`，作为主要成功标准。
- 如果均分未提升，但 worst regression 明显改善，需要明确说明为什么不作为最终推荐。
- 文档记录：
  - 最终策略
  - 运行命令
  - artifact 路径
  - 成本统计
  - most improved / most regressed
  - 无 GT/TEDS 泄漏确认
- 跑通后 git commit。

### 验收项 8：文档清理与交付

目标：把第三阶段结果合并进文档，清理临时报告和中间产物。

验收标准：

- 新建第三阶段 SPEC/报告，或按确认后的方式整理文档。
- 保留最新有效 artifacts 供人工查看。
- 清理旧 smoke/临时中间文件。
- git 工作区干净。
- 最终 git commit。

## 8. 版本控制规则

1. 一次只做一个验收项。
2. 每个验收项开始前先说明要改什么。
3. 每个验收项完成后必须跑通对应验证。
4. 验证通过后立即 `git commit`。
5. 后续如果改坏，只回退最近一个小 commit。
6. 不混入无关重构。
7. 不覆盖用户已有未提交改动。
