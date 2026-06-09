# 积极策略 Smoke 记录

日期：2026-06-09

对应验收项：`PERFORMANCE_IMPROVEMENT_SPEC.zh.md` 验收项 5。

## 1. 改动范围

本验收项新增可选配置项：

```yaml
split_review_policy: conservative | aggressive
```

默认值是 `conservative`，因此现有 `configs/default.yaml` 不需要修改，旧配置仍保持原行为。

`aggressive` 只影响 Qwen split review prompt：

- 对高复杂度或视觉较长的表格，只要存在清晰 whitespace band，就更倾向于切分。
- 如果 CV 没有给出 cut，但 Qwen 看到明显大段 section break，可以新增一个安全 cut。
- 短表、无安全 whitespace、或所有候选都会切穿内容时仍然不切。

运行时仍不读取 GT/TEDS，也不使用 baseline fallback。

## 2. 运行环境

与保守策略 smoke 相同，在 MinerU 服务节点使用本地 vLLM：

```text
mineru.endpoint: http://127.0.0.1:8000/v1/chat/completions
```

临时配置：

```text
/tmp/table_agent_newmineru_aggressive.yaml
split_review_policy: aggressive
```

## 3. 运行命令

```bash
conda run -n mineru python -m table_agent.cli run   --config /tmp/table_agent_newmineru_aggressive.yaml   --start 7   --end 12   --output-jsonl outputs/e2e_aggressive_smoke_7_12.jsonl   --sample-timeout 600
```

评分与汇总：

```bash
python /mnt/shared-storage-user/mineru2-shared/xiaojutao/utils/score_teds_jsonl.py   --input-jsonl outputs/e2e_aggressive_smoke_7_12.jsonl   --output-jsonl outputs/e2e_aggressive_smoke_7_12.baseline.scored.jsonl   --pred-field baseline_parse_result   --gt-field solution

python /mnt/shared-storage-user/mineru2-shared/xiaojutao/utils/score_teds_jsonl.py   --input-jsonl outputs/e2e_aggressive_smoke_7_12.jsonl   --output-jsonl outputs/e2e_aggressive_smoke_7_12.agent.scored.jsonl   --pred-field agent_parse_result   --gt-field solution

python -m table_agent.cli summarize   --run-jsonl outputs/e2e_aggressive_smoke_7_12.jsonl   --baseline-scored-jsonl outputs/e2e_aggressive_smoke_7_12.baseline.scored.jsonl   --agent-scored-jsonl outputs/e2e_aggressive_smoke_7_12.agent.scored.jsonl   --output-json outputs/e2e_aggressive_smoke_7_12.summary.json   --top-k 5
```

## 4. 结果

Smoke 范围：benchmark indices 7-11，共 5 条。

端到端运行结果：

```text
total: 5
success: 5
partial_success: 0
failed: 0
sample_timeout: 600
```

TEDS 汇总：

```text
baseline_avg_teds: 0.8847791142215197
agent_avg_teds: 0.8624223842043918
absolute_improvement: -0.0223567300171279
relative_improvement: -0.025268148465279562
avg_chunk_count: 2.0
avg_split_iterations: 1.8
```

和保守策略同组结果对比：

| policy | baseline_avg_teds | agent_avg_teds | absolute_improvement | avg_chunk_count |
|---|---:|---:|---:|---:|
| conservative | 0.8850028278680522 | 0.8101394181017858 | -0.07486340976626638 | 1.6 |
| aggressive | 0.8847791142215197 | 0.8624223842043918 | -0.0223567300171279 | 2.0 |

Per-case 摘要：

| smoke line | image | chunks | Qwen should_split | delta_teds | warnings |
|---:|---|---:|---|---:|---|
| 0 | `layout-PM2BfTXPZk-HzvOH.block-PM2BfiXPZk-HzvPo.jpg` | 2 | true | 0.011332154435602648 | none |
| 1 | `layout-PM2C40exw--WU3Ty.block-PM2C40exw--WU3UW.jpg` | 2 | true | -0.07074898463912149 | none |
| 2 | `layout-PM2Dm0exw--Qupj2.block-PM2Dm0exw--QupjA.jpg` | 2 | true | 0.0 | none |
| 3 | `layout-PM2QwkCoZF-F4asv.block-PM2QwkCoZF-F4at0.jpg` | 2 | true | 0.09368581169682666 | none |
| 4 | `layout-PM2aGJmPE--9OlhN.block-PM2aGZmPE--9Olib.jpg` | 2 | true | -0.14605263157894732 | `illegal_otsl_tokens`, `column_count_inconsistent` |

## 5. 解释

积极策略相对保守策略明显改善了 targeted smoke 的平均 agent TEDS：从 0.8101394181017858 提升到 0.8624223842043918。

最重要的变化是 index 7：

- 保守策略：Qwen `should_split=false`，agent TEDS 0.7606984969053935。
- 积极策略：Qwen `should_split=true`，cut=292，agent TEDS 0.9980842911877394。

这说明原先归为 single-chunk rerun 波动的 case 中，至少一部分可以通过更积极但仍由 Qwen 判断的切分策略缓解。

不过，积极策略仍没有解决 case 11：该 case 继续出现 `column_count_inconsistent` 和非法 OTSL token，agent TEDS 仍为 0.770739014536007。这更适合验收项 6 的 OTSL/crop 后处理实验。

## 6. 结论

验收项 5 smoke 跑通。积极策略优于保守策略，但在 indices 7-11 上仍低于同批 baseline，因此还不能作为最终方案直接采用。

后续建议：

1. 保留 `split_review_policy` 作为实验开关，默认仍为 `conservative`。
2. 继续验收项 6，优先处理 `column_count_inconsistent` 和非法 OTSL token。
3. 后续完整 48 条评估应同时比较 conservative/aggressive，并重点观察 aggressive 是否引入新的切分回归。
