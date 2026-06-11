# 第三阶段验收项 1：离线诊断与候选统计

日期：2026-06-11

## 目标

基于当前最新 48 条 aggressive run，输出每条 case 的离线诊断字段，并用无 GT 运行时可观测信号标注 retry/fallback 候选。

## 运行命令

```bash
python -m table_agent.cli diagnose \
  --run-jsonl outputs/e2e_aggressive_48.jsonl \
  --baseline-scored-jsonl outputs/e2e_aggressive_48.baseline.scored.jsonl \
  --agent-scored-jsonl outputs/e2e_aggressive_48.agent.scored.jsonl \
  --output-json outputs/third_stage_diagnostics_48.json \
  --top-k 8
```

## 输出 artifact

- `outputs/third_stage_diagnostics_48.json`

该 JSON 已包含每条 case 的 `index/image`、`baseline_teds`、`agent_teds`、`delta_teds`、`warnings`、`chunk_count`、`split_decision`、`crop_estimates`、`retry_candidate`、`fallback_candidate` 和候选原因。

## 候选规则

候选标签只使用运行时可观测 metadata：warning tag、agent/crop status、chunk count、crop 行列估计 spread、Qwen split decision/risk factors。

TEDS/GT 派生分数只用于本离线报告归因，不进入候选标签判定，也未修改 runtime 主流程。

## 结果摘要

| metric | value |
| --- | ---: |
| count | 48 |
| baseline_avg_teds | 0.8614947094362552 |
| agent_avg_teds | 0.9038593040110346 |
| regression_count | 21 |
| retry_candidate_count | 9 |
| retry_candidate_regression_count | 6 |
| fallback_candidate_count | 3 |
| fallback_candidate_regression_count | 3 |

Retry 候选 indices：`[11, 16, 19, 21, 33, 39, 41, 44, 46]`

Fallback 候选 indices：`[11, 39, 46]`

最强 fallback 信号是 severe column-count spread，对应三个明显 regression：

| index | delta_teds | reason |
| ---: | ---: | --- |
| 11 | -0.14605263157894732 | severe_col_count_spread:4 |
| 39 | -0.0609994756985105 | severe_col_count_spread:10 |
| 46 | -0.18792228798040866 | severe_col_count_spread:7 |

## 验证

- `python -m py_compile table_agent/diagnostics.py`
- 上述 `python -m table_agent.cli diagnose ...` 完整跑通并生成报告。
