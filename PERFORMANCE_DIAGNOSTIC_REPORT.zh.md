# Table Agent 48-Case 诊断报告

日期：2026-06-09

对应验收项：`PERFORMANCE_IMPROVEMENT_SPEC.zh.md` 验收项 2。

## 1. 输入 artifacts

本报告基于验收项 1 的离线诊断输出：

- `outputs/e2e_newmineru_local_48_combined.jsonl`
- `outputs/e2e_newmineru_local_48_combined.baseline.scored.jsonl`
- `outputs/e2e_newmineru_local_48_combined.agent.scored.jsonl`
- `outputs/e2e_newmineru_local_48_combined.diagnostics.json`

离线诊断命令：

```bash
python -m table_agent.cli diagnose \
  --run-jsonl outputs/e2e_newmineru_local_48_combined.jsonl \
  --baseline-scored-jsonl outputs/e2e_newmineru_local_48_combined.baseline.scored.jsonl \
  --agent-scored-jsonl outputs/e2e_newmineru_local_48_combined.agent.scored.jsonl \
  --output-json outputs/e2e_newmineru_local_48_combined.diagnostics.json \
  --top-k 8
```

说明：本报告使用 TEDS 和 GT-derived scored artifacts 做离线归因；后续运行时策略不能读取 GT、TEDS、样本 ID 白名单/黑名单，也不能把 baseline parse result 作为 agent fallback 输入。

## 2. 总体统计

- 样本数：48
- baseline avg TEDS：0.8634187595356039
- agent avg TEDS：0.8926355322939662
- agent improvement case：15
- unchanged case：21
- regression case：12

Regression case 的平均 `delta_teds` 为 -0.06569526009473835。

## 3. Regression 分组

按 chunk 数：

| group | count | avg delta | worst delta | indices |
|---|---:|---:|---:|---|
| single chunk | 4 | -0.08475470153755257 | -0.22605363984674332 | 7, 8, 31, 38 |
| multi chunk | 8 | -0.05616553937333123 | -0.18936737468561105 | 1, 4, 6, 11, 25, 29, 30, 46 |

按 warning：

| group | count | avg delta | worst delta | indices |
|---|---:|---:|---:|---|
| no warning | 10 | -0.045292311487230175 | -0.22605363984674332 | 1, 4, 6, 7, 8, 25, 29, 30, 31, 38 |
| column_count_inconsistent | 2 | -0.16771000313227918 | -0.18936737468561105 | 11, 46 |
| illegal_otsl_tokens | 1 | -0.14605263157894732 | -0.14605263157894732 | 11 |

所有 regression 的 `agent_status` 都是 `success`，说明当前失败不是简单的识别失败，而是结构质量下降或重新识别波动。

## 4. Worst Regression Cases

| index | delta | chunks | warnings | image |
|---:|---:|---:|---|---|
| 7 | -0.22605363984674332 | 1 | none | `layout-PM2BfTXPZk-HzvOH.block-PM2BfiXPZk-HzvPo.jpg` |
| 46 | -0.18936737468561105 | 2 | column_count_inconsistent | `layout-PMBhPTXPZk-D4CyR.block-PMBhPyXPZk-D4D0Q.jpg` |
| 11 | -0.14605263157894732 | 2 | illegal_otsl_tokens, column_count_inconsistent | `layout-PM2aGJmPE--9OlhN.block-PM2aGZmPE--9Olib.jpg` |
| 8 | -0.09533730498613735 | 1 | none | `layout-PM2C40exw--WU3Ty.block-PM2C40exw--WU3UW.jpg` |
| 1 | -0.07522720743653699 | 2 | none | `layout-PM0dhn_T---F8KJm.block-PM0din_T---F8KND.jpg` |

## 5. 初步归因

### Pattern A：single-chunk rerun 波动

代表 case：7、8、38，另有轻微 case 31。

这些 case 的 agent 路径最终只有 1 个 chunk。运行时没有使用 baseline fallback，但 agent single-chunk 本质上会再次调用 MinerU 整图识别。因此 regression 可能来自同一张图在两次 MinerU 调用之间的不稳定输出，而不是切分或合并。

这类问题当前没有 warning，且 worst regression index 7 属于此类。后续策略应让 Qwen 显式判断是否需要切；如果不切，仍然可以作为 agent 正常输出跑整图 MinerU，但需要考虑减少无意义的 split-review/crop 路径扰动，并记录 single-chunk 决策原因。

### Pattern B：列数不一致的 multi-chunk 合并

代表 case：46、11。

这两个 case 数量少，但平均损失最大：avg delta -0.16771000313227918。它们都有 `column_count_inconsistent`，index 11 还出现 `illegal_otsl_tokens`。

这类问题是最清晰、最可检测的结构错误簇。可能原因包括：切点位置导致 crop 中列结构识别不一致、下半部分缺列、OTSL token 被污染，或合并时直接拼接不适合列数变化较大的 crop。

### Pattern C：无 warning 的 multi-chunk 轻中度 regression

代表 case：1、4、6、25、29、30。

这类 case 没有明显结构 warning，多数 delta 较小，但 index 1 有 -0.07522720743653699。可能原因包括边界行重复/遗漏、表头或合并单元格跨 chunk 被破坏、切点附近上下文不足，或者 crop 识别虽列数接近但内容质量下降。

当前诊断还不足以区分切分问题和识别问题，需要下一步结合图片/crop 可视检查或新增更多无 GT 结构信号。

## 6. 优先处理顺序

1. 优先处理 Pattern B：`column_count_inconsistent` 和 `illegal_otsl_tokens`。理由：信号明确、平均损失大、适合做不依赖 GT 的运行时 guard 或后处理。
2. 并行设计 Pattern A 的 Qwen split/no-split 决策。理由：worst regression 是 single-chunk rerun 波动，且用户明确希望由 Qwen 判断该不该切。
3. 再处理 Pattern C：无 warning 的 multi-chunk regression。理由：数量较多但信号弱，需要更细的 case study 或新增诊断特征。

## 7. 下一步策略建议

验收项 3 应先新增 Qwen split/no-split 决策，输出结构化 JSON：

- `should_split`
- `complexity`
- `risk_factors`
- `cuts`
- `reason`

保守策略候选：

- Qwen 判断低复杂度或切分风险高时，不切。
- Qwen 判断切点不安全时，减少切点而不是新增切点。
- 对 multi-chunk 结果出现列数强不一致时，标记高风险，供后续验收项 6 做结构处理。

积极策略候选：

- Qwen 判断复杂表格且存在安全 whitespace band 时才切。
- 对高度较大、当前 MinerU baseline 容易退化的长表格保留 2-chunk 路径。
- 成本控制在现有 Qwen split review 附近，不引入多候选大规模重跑。

## 8. 当前结论

当前 agent 平均表现已经优于 baseline，但 regression 不是单一原因：

- 最大单点回归来自 single-chunk 重新识别波动。
- 最强可检测错误簇是列数不一致和非法 OTSL token。
- 数量最多的 regression 没有 warning，需要 Qwen 决策和更细粒度结构诊断来降低风险。

因此下一步不应直接做 OTSL 后处理或大规模重写切分逻辑；更稳妥的入口是验收项 3：引入 Qwen split/no-split 决策，并保留后续对列数不一致的 guard/后处理空间。
