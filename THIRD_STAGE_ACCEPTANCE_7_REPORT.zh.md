# 第三阶段验收项 7：完整 48 条评估与最终选择

日期：2026-06-11

## 最终推荐策略

选择 `high` 档位作为第三阶段最终推荐策略：

- 默认 aggressive split + merge。
- 不启用 re-split retry，因为已验证的 re-split 策略均为净负收益。
- 若 split/merge 后出现 `column_count_inconsistent`，且非零 crop estimated column count spread `>= 3`，agent 额外调用一次 MinerU full-image fallback。
- fallback 结果可作为最终 `agent_parse_result`。
- 不复用 baseline parse result。
- 不使用 GT、TEDS、case id 白名单/黑名单。

## 运行与 artifact

本验收项使用当前最新 48 条 aggressive run 加 agent 自己重跑的 full-image fallback 结果构造完整 48 条 counterfactual。触发条件只依赖该 run 的 runtime metadata。

主要 artifact：

- `outputs/cost_tiers/high.jsonl`
- `outputs/cost_tiers/high.agent.scored.jsonl`
- `outputs/cost_tiers/high.summary.json`
- `outputs/fallback_smoke_acceptance4/fallback.jsonl`
- `outputs/fallback_smoke_cost_tiers/fallback_extra.jsonl`

标准 summary 命令：

```bash
python -m table_agent.cli summarize \
  --run-jsonl outputs/cost_tiers/high.jsonl \
  --baseline-scored-jsonl outputs/e2e_aggressive_48.baseline.scored.jsonl \
  --agent-scored-jsonl outputs/cost_tiers/high.agent.scored.jsonl \
  --output-json outputs/cost_tiers/high.summary.json \
  --top-k 8
```

## 完整 48 条结果

| metric | value |
| --- | ---: |
| count | 48 |
| baseline_avg_teds | 0.8614947094362552 |
| previous_best_agent_avg_teds | 0.9038593040110346 |
| final_agent_avg_teds | 0.9127643569708148 |
| gain_vs_previous_best | 0.008905052959780195 |
| absolute_improvement_vs_baseline | 0.05126964753455965 |
| relative_improvement_vs_baseline | 0.05951243457793197 |
| success_count | 48 |
| failure_count | 0 |
| fallback_trigger_count | 4 |
| extra_mineru_calls | 4 |
| extra_qwen_calls | 0 |
| regression_count | 17 |
| worst_regression | -0.09373351148293152 |

Fallback 触发 indices：`[11, 39, 41, 46]`。

相对 previous best，这 4 条全部提升、误杀 0。

## Most Improved

与 baseline 比，top improved 保持来自 split+merge 主收益：

| index | delta_teds |
| ---: | ---: |
| 31 | 0.6279866573114815 |
| 43 | 0.3718225014186255 |
| 34 | 0.349395710452158 |
| 22 | 0.31015619376664494 |
| 28 | 0.24075129582890287 |
| 5 | 0.210545933669666 |
| 13 | 0.1474141054311212 |
| 40 | 0.11166733433256892 |

## Most Regressed

最终 worst regression 从 previous best 的 `-0.18792228798040866` 改善到 `-0.09373351148293152`。

| index | delta_teds | note |
| ---: | ---: | --- |
| 19 | -0.09373351148293152 | col spread 2；xhigh fallback 可修复但 broader trigger 会误杀其他样本 |
| 1 | -0.07522720743653699 | no high-confidence runtime anomaly |
| 6 | -0.0540395261531611 | no high-confidence runtime anomaly |
| 12 | -0.031198179524152825 | no high-confidence runtime anomaly |
| 24 | -0.031135531135531136 | no high-confidence runtime anomaly |
| 15 | -0.026573966782541536 | no high-confidence runtime anomaly |
| 35 | -0.019607843137254832 | no high-confidence runtime anomaly |
| 20 | -0.018175696357514592 | no high-confidence runtime anomaly |

## 无泄漏确认

Runtime 策略只使用：

- crop MinerU 输出 OTSL。
- merge warnings。
- crop estimated column count。
- agent metadata。

Runtime 不使用：

- GT `solution`。
- TEDS/TEDS-S。
- baseline parse result fallback。
- case id 白名单/黑名单。

## 结论

第三阶段最终推荐 `high`：`column_count_inconsistent` + col spread `>= 3` 时触发一次 agent full-image fallback。

该策略使完整 48 条 `agent_avg_teds` 从当前最佳 `0.9038593040110346` 提升到 `0.9127643569708148`，满足第三阶段首要目标。
