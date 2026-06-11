# 第三阶段验收项 6：成本档位实验

日期：2026-06-11

## 目标

基于前面已验证的策略定义并比较 `low/medium/high/xhigh` 成本档位。由于 re-split/retry 策略在验收项 2 及完整 `header_repeat` 修正实验中均为净负收益，本轮档位只围绕已验证有效的 full-image fallback 扩展触发范围。

所有档位均使用当前 48 条 aggressive run 作为主体，按运行时可观测信号构造 counterfactual 48 条结果：未触发 case 保持原 agent 结果，触发 case 使用 agent 自己额外调用 MinerU full-image 的 fallback 结果。不复用 baseline parse result。

## 档位定义

| tier | trigger | fallback_indices | rationale |
| --- | --- | --- | --- |
| `low` | no extra fallback | `[]` | 当前 aggressive split+merge |
| `medium` | `column_count_inconsistent` 且 col spread `>= 4` | `[11,39,46]` | 验收项 4 已验证 3/3 提升、误杀 0 |
| `high` | `column_count_inconsistent` 且 col spread `>= 3` | `[11,39,41,46]` | 在 medium 基础上加入 index 41，补跑 fallback 后验证为提升 |
| `xhigh` | any `column_count_inconsistent` / col spread `>= 2` | `[11,16,19,33,39,41,46]` | 探索最大触发范围；会覆盖已改善样本 |

## 运行与 artifact

- cost tier JSONL：`outputs/cost_tiers/<tier>.jsonl`
- cost tier scored：`outputs/cost_tiers/<tier>.agent.scored.jsonl`
- cost tier summary：`outputs/cost_tiers/<tier>.summary.json`
- 额外 fallback smoke：`outputs/fallback_smoke_cost_tiers/fallback_extra.jsonl`
- 额外 fallback scored：`outputs/fallback_smoke_cost_tiers/fallback_extra.scored.jsonl`

标准 summary 命令：

```bash
python -m table_agent.cli summarize \
  --run-jsonl outputs/cost_tiers/<tier>.jsonl \
  --baseline-scored-jsonl outputs/e2e_aggressive_48.baseline.scored.jsonl \
  --agent-scored-jsonl outputs/cost_tiers/<tier>.agent.scored.jsonl \
  --output-json outputs/cost_tiers/<tier>.summary.json \
  --top-k 8
```

## 结果

| tier | agent_avg_teds | absolute_improvement | regression_count | worst_regression | extra_mineru_calls | extra_qwen_calls | improved_vs_low | regressed_vs_low |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `low` | 0.9038593040110346 | 0.04236459457477948 | 21 | -0.18792228798040866 | 0 | 0 | 0 | 0 |
| `medium` | 0.9120879372455736 | 0.05059322780931841 | 18 | -0.09373351148293152 | 3 | 0 | 3 | 0 |
| `high` | 0.9127643569708148 | 0.05126964753455965 | 17 | -0.09373351148293152 | 4 | 0 | 4 | 0 |
| `xhigh` | 0.9121231351208827 | 0.050628425684627554 | 16 | -0.07522720743653699 | 7 | 0 | 5 | 2 |

## 结论

`high` 的均分最高，且相对 `low` 没有误杀：4 个触发 case 全部提升。但 `high` 相对 `medium` 只多提升约 `0.0006764197`，需要多 1 次 MinerU full-image 调用。

`medium` 性价比最好：3 次额外 MinerU 调用带来 `+0.0082286332` 的 48 条均分提升，并把 worst regression 从 `-0.18792228798` 改善到 `-0.09373351148`。

`xhigh` 不推荐：虽然 regression_count 从 17/18 降到 16，但误杀了 2 个原本 agent 更好的样本，且 7 次额外 MinerU 调用的均分低于 `high`。

推荐进入最终策略的档位：`high` 作为最高分策略；若优先成本/收益比，选择 `medium`。
