# 保守策略 Smoke 记录

日期：2026-06-09

对应验收项：`PERFORMANCE_IMPROVEMENT_SPEC.zh.md` 验收项 4。

## 1. 运行环境

在 MinerU 服务节点执行：

```text
root@shaw-9dc9r-259705-worker-0
```

本次重新启动了本地 MinerU vLLM 服务：

```bash
tmux new-session -d -s mineru_8000 'cd /mnt/shared-storage-user/mineru2-shared/xiaojutao && conda run -n mineru bash utils/mineru_server.sh'
```

验证 endpoint：

```bash
curl http://127.0.0.1:8000/v1/models
```

返回模型：`MinerU-Pro`。

本次使用临时配置：

```text
/tmp/table_agent_newmineru_local.yaml
mineru.endpoint: http://127.0.0.1:8000/v1/chat/completions
```

该临时配置不提交。

## 2. 运行命令

端到端 smoke：

```bash
conda run -n mineru python -m table_agent.cli run   --config /tmp/table_agent_newmineru_local.yaml   --start 7   --end 12   --output-jsonl outputs/e2e_conservative_smoke_7_12.jsonl   --sample-timeout 600
```

评分：

```bash
python /mnt/shared-storage-user/mineru2-shared/xiaojutao/utils/score_teds_jsonl.py   --input-jsonl outputs/e2e_conservative_smoke_7_12.jsonl   --output-jsonl outputs/e2e_conservative_smoke_7_12.baseline.scored.jsonl   --pred-field baseline_parse_result   --gt-field solution

python /mnt/shared-storage-user/mineru2-shared/xiaojutao/utils/score_teds_jsonl.py   --input-jsonl outputs/e2e_conservative_smoke_7_12.jsonl   --output-jsonl outputs/e2e_conservative_smoke_7_12.agent.scored.jsonl   --pred-field agent_parse_result   --gt-field solution

python -m table_agent.cli summarize   --run-jsonl outputs/e2e_conservative_smoke_7_12.jsonl   --baseline-scored-jsonl outputs/e2e_conservative_smoke_7_12.baseline.scored.jsonl   --agent-scored-jsonl outputs/e2e_conservative_smoke_7_12.agent.scored.jsonl   --output-json outputs/e2e_conservative_smoke_7_12.summary.json   --top-k 5
```

## 3. 结果

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
baseline_avg_teds: 0.8850028278680522
agent_avg_teds: 0.8101394181017858
absolute_improvement: -0.07486340976626638
relative_improvement: -0.08459115316796252
avg_chunk_count: 1.6
avg_split_iterations: 1.4
```

Per-case 摘要：

| smoke line | image | chunks | Qwen should_split | delta_teds | warnings |
|---:|---|---:|---|---:|---|
| 0 | `layout-PM2BfTXPZk-HzvOH.block-PM2BfiXPZk-HzvPo.jpg` | 1 | false | -0.22605363984674332 | none |
| 1 | `layout-PM2C40exw--WU3Ty.block-PM2C40exw--WU3UW.jpg` | 1 | false | -0.09533730498613735 | none |
| 2 | `layout-PM2Dm0exw--Qupj2.block-PM2Dm0exw--QupjA.jpg` | 2 | true | -0.0005592841163311046 | none |
| 3 | `layout-PM2QwkCoZF-F4asv.block-PM2QwkCoZF-F4at0.jpg` | 2 | true | 0.09368581169682666 | none |
| 4 | `layout-PM2aGJmPE--9OlhN.block-PM2aGZmPE--9Olib.jpg` | 2 | true | -0.14605263157894732 | `illegal_otsl_tokens`, `column_count_inconsistent` |

## 4. 解释

本次保守策略 smoke 跑通了，但没有改善这组 targeted regression：

- 对 single-chunk regression case 7 和 8，Qwen 正确选择 `should_split=false`，但 agent 仍需要独立调用一次整图 MinerU。由于运行时不能使用 baseline fallback，这类 case 仍暴露为 MinerU rerun 波动。
- 对 case 11，Qwen 判断可以切，但 crop 识别后仍出现 `column_count_inconsistent` 和非法 OTSL token，说明该问题更接近 crop 识别或 OTSL 后处理问题。
- case 10 有明显提升，说明保守 split/no-split 决策并非完全无效，但还不足以作为最终策略。

## 5. 结论

验收项 4 的 smoke 运行通过，但结果不应作为最终策略采用：在 indices 7-11 上 agent 平均 TEDS 低于 baseline。

下一步建议：

1. 针对 single-chunk rerun 波动，研究是否可以在不使用 baseline fallback 的前提下减少无意义的二次路径扰动，或增加运行时自检信号。
2. 针对 `column_count_inconsistent` 和非法 token，进入验收项 6 的 OTSL/crop 后处理实验会更直接。
3. 在验收项 5 的积极策略中，不应简单增加切分；需要先避免 case 11 这种列数不一致风险。
