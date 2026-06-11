# 第三阶段验收项 4：fallback 反事实实验

日期：2026-06-11

## 目标

对验收项 1 标出的 fallback 候选 case，额外跑 agent 自己的 full-image MinerU 识别，并离线比较：

- 当前保存的 split+merge agent 结果
- 验收项 2 中 re-split smoke 的 best retry 结果
- 本轮 fallback full-image 结果

baseline 只作为离线参考，不参与运行时选择；本实验重新调用 MinerU 整图识别，不复用 `baseline_parse_result`。

## 实验入口

新增 CLI：

```bash
python -m table_agent.cli fallback-smoke \
  --config configs/default.yaml \
  --diagnostics-json outputs/third_stage_diagnostics_48.json \
  --indices 11,39,46 \
  --output-jsonl outputs/fallback_smoke_acceptance4/fallback.jsonl
```

评分命令：

```bash
python /mnt/shared-storage-user/mineru2-shared/xiaojutao/utils/score_teds_jsonl.py \
  --input-jsonl outputs/fallback_smoke_acceptance4/fallback.jsonl \
  --output-jsonl outputs/fallback_smoke_acceptance4/fallback.scored.jsonl \
  --pred-field agent_parse_result \
  --gt-field solution
```

## 候选样本

使用验收项 1 的 fallback regression candidates：`[11, 39, 46]`。

触发信号均为运行时可观测信号：`warning:column_count_inconsistent` 且 `severe_col_count_spread >= 4`。

## 结果摘要

| metric | value |
| --- | ---: |
| current_agent_avg_teds_on_3 | 0.7628511487571495 |
| best_retry_avg_teds_on_3 | 0.5992455655607557 |
| fallback_avg_teds_on_3 | 0.8945092805097716 |
| fallback_avg_change_vs_current_agent | 0.1316581317526221 |
| fallback_avg_change_vs_best_retry | 0.29526371494901593 |
| improved_cases_vs_current_agent | 3 |
| mistaken_kill_cases_vs_current_agent | 0 |
| worst_change_vs_current_agent | 0.0609994756985105 |
| worst_delta_vs_baseline | 0.0 |
| extra_mineru_calls | 3 |
| extra_qwen_calls | 0 |
| avg_seconds | 6.3863335972030955 |

若仅对这三条触发 fallback，48 条反事实 `agent_avg_teds` 约为 `0.9120879372455736`，比当前最佳 `0.9038593040110346` 高 `0.008228633234538886`。

## Per-case 对比

| index | current_agent_teds | best_retry_teds | fallback_teds | fallback_change_vs_current | baseline_teds_offline_ref |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 11 | 0.770739014536007 | 0.613473827759542 | 0.9167916461149543 | 0.14605263157894732 | 0.9167916461149543 |
| 39 | 0.8146743787489289 | 0.7593582887700535 | 0.8756738544474394 | 0.0609994756985105 | 0.8756738544474394 |
| 46 | 0.7031400529865125 | 0.42490458015267174 | 0.8910623409669212 | 0.18792228798040866 | 0.8910623409669212 |

## 结论

fallback full-image 对三条严重 column-count spread regression 全部净提升，误杀为 0，额外成本为每条 1 次 MinerU full-image 调用。

建议进入主流程的 fallback 触发条件：split/merge 后出现 `column_count_inconsistent`，且 crop estimated column count spread `>= 4`。由于验收项 2 没有任何 re-split 策略通过验证，验收项 5 接入时 retry 阶段应保持 no-op 或仅记录未启用，fallback 作为该严重异常的保护路径。

## 验证

- `python -m py_compile table_agent/fallback_experiment.py table_agent/cli.py`
- `python -m table_agent.cli fallback-smoke --help`
- fallback 反事实：`outputs/fallback_smoke_acceptance4/fallback.jsonl`
- fallback 评分：`outputs/fallback_smoke_acceptance4/fallback.scored.jsonl`
