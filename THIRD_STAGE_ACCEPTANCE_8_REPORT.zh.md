# 第三阶段验收项 8 报告：文档交付与清理

日期：2026-06-11

## 目标

把第三阶段最终结论沉淀到主文档和项目导航文档，保证后续接手时能直接看到当前推荐策略、关键 artifacts、运行时边界和已完成验收项。

## 更新内容

- 更新 `SPEC.zh.md`：
  - 写入第三阶段 high fallback 最终策略。
  - 记录最终 48 条 counterfactual 指标：`agent_avg_teds=0.9127643569708148`。
  - 明确第二阶段 aggressive full run 是历史最佳基础，不是当前最终推荐的完整策略。
  - 补充第三阶段 re-split/fallback 实验文件和 high fallback artifacts。
- 更新 `PROJECT_MAP.md`：
  - 将起始阅读顺序指向 `THIRD_STAGE_ACCEPTANCE_7_REPORT.zh.md` 和当前主规格。
  - 更新当前最佳结果、pipeline flow、CLI/module map、runtime fallback 边界。
  - 标注第三阶段验收项状态：1、2、4、5、6、7 完成；3 因 re-split smoke 无正收益而跳过；8 完成。

## 最终推荐

运行时策略：

1. 使用 `split_review_policy: aggressive`。
2. 保留 OTSL stray angle repair。
3. 当 merge warning 包含 `column_count_inconsistent`，且 crop estimated column count spread `>= 3` 时，触发 agent full-image fallback。

边界：

- fallback 是 agent 路径自己的额外 MinerU 整图调用。
- 不复用 `baseline_parse_result`。
- 不使用 GT、TEDS、case id 白名单或黑名单做运行时决策。

## 最终结果

第三阶段 high fallback counterfactual：

| metric | value |
| --- | ---: |
| count | 48 |
| baseline_avg_teds | 0.8614947094362552 |
| previous_best_agent_avg_teds | 0.9038593040110346 |
| final_agent_avg_teds | 0.9127643569708148 |
| gain_vs_previous_best | 0.008905052959780195 |
| absolute_improvement_vs_baseline | 0.05126964753455965 |
| fallback_trigger_count | 4 |
| extra_mineru_calls | 4 |

关键 artifacts：

- `outputs/cost_tiers/high.jsonl`
- `outputs/cost_tiers/high.agent.scored.jsonl`
- `outputs/cost_tiers/high.summary.json`
- `THIRD_STAGE_ACCEPTANCE_7_REPORT.zh.md`

## 清理记录

已清理未被验收报告引用、且已被最终 high tier artifacts 取代的临时产物：

- `outputs/resplit_header_repeat_probe/`
- `outputs/e2e_fallback_counterfactual_48.jsonl`
- `outputs/e2e_fallback_counterfactual_48.agent.scored.jsonl`
- `outputs/e2e_fallback_counterfactual_48.summary.json`

保留早期验收报告显式引用的 smoke artifacts，避免历史报告断链。

## 验收结论

验收项 8 通过。第三阶段最终策略、结果和边界已写入主文档，可作为下一轮优化的稳定基线。
