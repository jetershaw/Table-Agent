# 最终策略选择报告

## 结论

推荐保留并使用 `split_review_policy: aggressive`，同时保留 OTSL stray angle
repair。完整 48 条 benchmark 上，aggressive 策略在不使用 GT/TEDS/baseline
fallback 的前提下，将 `agent_avg_teds` 提升到 `0.9038593040110346`。

相对本次 aggressive full run 的 baseline：

| metric | value |
| --- | ---: |
| count | 48 |
| baseline_avg_teds | 0.8614947094362552 |
| agent_avg_teds | 0.9038593040110346 |
| absolute_improvement | 0.04236459457477948 |
| relative_improvement | 0.04917568745431068 |
| success_count | 48 |
| failure_count | 0 |
| avg_chunk_count | 1.9166666666666667 |
| avg_split_iterations | 1.4583333333333333 |

相对规格书中记录的上一版目标 `agent_avg_teds=0.8926355322939662`，本次结果提升
`+0.011223771717068434`。

## 推荐方案

1. 使用 aggressive Qwen split review policy。
   - Qwen 可以在复杂表格、清晰空白带、长表场景下更积极选择切分。
   - 仍要求切点不能穿过文字或表格线，避免无安全切点时硬切。
2. 保留 `split_decision` 元数据。
   - 记录 `should_split`、`complexity`、`risk_factors`、`cuts`、`reason`。
   - 便于后续继续分析错误 pattern。
3. 保留 `repair_stray_otsl_angles`。
   - 修复 crop OTSL 中类似 `<#200 (%)` 这类文本小于号被误判为 OTSL token 的问题。
   - 该修复只依赖 OTSL 文本本身，不依赖 GT 或 TEDS。

## 完整 48 条结果

产物路径：

- run: `outputs/e2e_aggressive_48.jsonl`
- baseline scored: `outputs/e2e_aggressive_48.baseline.scored.jsonl`
- agent scored: `outputs/e2e_aggressive_48.agent.scored.jsonl`
- summary: `outputs/e2e_aggressive_48.summary.json`

`most_improved` Top 8：

| index | delta_teds | baseline | agent | chunk_count | warnings |
| ---: | ---: | ---: | ---: | ---: | --- |
| 31 | +0.6279866573114815 | 0.30991904247422075 | 0.9379056997857023 | 2 | none |
| 43 | +0.3718225014186255 | 0.5841333503098209 | 0.9559558517284464 | 2 | none |
| 34 | +0.349395710452158 | 0.5473033957239031 | 0.8966991061760611 | 2 | none |
| 22 | +0.31015619376664494 | 0.6247030878859858 | 0.9348592816526308 | 2 | none |
| 28 | +0.24075129582890287 | 0.7543649247304491 | 0.995116220559352 | 2 | none |
| 5 | +0.210545933669666 | 0.6569754338517015 | 0.8675213675213675 | 2 | none |
| 13 | +0.1474141054311212 | 0.8328073298623037 | 0.9802214352934249 | 2 | none |
| 40 | +0.11166733433256892 | 0.8572357019064125 | 0.9689030362389814 | 2 | none |

`most_regressed` Top 8：

| index | delta_teds | baseline | agent | chunk_count | warnings |
| ---: | ---: | ---: | ---: | ---: | --- |
| 46 | -0.18792228798040866 | 0.8910623409669212 | 0.7031400529865125 | 2 | `column_count_inconsistent:[36, 29]` |
| 11 | -0.14605263157894732 | 0.9167916461149543 | 0.770739014536007 | 2 | `repaired_stray_otsl_angle:0`, `column_count_inconsistent:[21, 17]` |
| 19 | -0.09373351148293152 | 0.9991748991748992 | 0.9054413876919677 | 2 | `column_count_inconsistent:[25, 23]` |
| 1 | -0.07522720743653699 | 0.9225449515905948 | 0.8473177441540578 | 2 | none |
| 39 | -0.0609994756985105 | 0.8756738544474394 | 0.8146743787489289 | 2 | `column_count_inconsistent:[21, 11]` |
| 6 | -0.0540395261531611 | 0.977227572967938 | 0.923188046814777 | 2 | none |
| 41 | -0.03246814681158283 | 0.8601485691294265 | 0.8276804223178437 | 2 | `column_count_inconsistent:[20, 17]` |
| 12 | -0.031198179524152825 | 0.914193302891933 | 0.8829951233677802 | 2 | none |

## 策略取舍

保守策略 smoke 主要减少不确定切分，但在 7-11 子集上 `agent_avg_teds=0.8101394181017858`，
低于对应 baseline `0.8850028278680522`。

积极策略 smoke 在同一子集上提升到 `agent_avg_teds=0.8624223842043918`，并且完整 48
条结果达到 `0.9038593040110346`。虽然仍有 8 个显著 regression case，主要集中在
`column_count_inconsistent` 和少数无 warning 的切分重跑波动，但复杂大表的收益更大，
因此推荐 aggressive 作为当前默认实验策略。

OTSL repair 消除了非法 OTSL token warning，但单独不能解决列数不一致。后续优先方向应是
crop 合并时的列对齐/列数一致性修复，而不是继续扩大切分激进程度。

## 复现环境

MinerU 服务节点：

```bash
cd /
ssh -CAXY ws-15667b3f02c1236f-worker-v6gjp.xiaojutao+root.ailab-sciversealign.pod@h.pjlab.org.cn -i id_rsa
```

服务信息：

- 节点：`root@shaw-9dc9r-259705-worker-0`
- MinerU endpoint: `http://127.0.0.1:8000/v1/chat/completions`
- tmux session: `mineru_8000`
- model: `MinerU-Pro`

完整运行命令：

```bash
cd /mnt/shared-storage-user/mineru2-shared/xiaojutao/Table-Agent
conda run -n mineru python -m table_agent.cli run \
  --config /tmp/table_agent_newmineru_aggressive.yaml \
  --output-jsonl outputs/e2e_aggressive_48.jsonl \
  --sample-timeout 600
```

由于整批 TEDS 评分在大表上可能异常退出且不落盘，本次评估采用逐条评分再合并的方式。
合并后的 scored 文件格式与 `score_teds_jsonl.py` 输出兼容，第一行为 `__summary__`，
后续 48 行为样本行。

最终汇总命令：

```bash
python -m table_agent.cli summarize \
  --run-jsonl outputs/e2e_aggressive_48.jsonl \
  --baseline-scored-jsonl outputs/e2e_aggressive_48.baseline.scored.jsonl \
  --agent-scored-jsonl outputs/e2e_aggressive_48.agent.scored.jsonl \
  --output-json outputs/e2e_aggressive_48.summary.json \
  --top-k 8
```

## 无泄漏确认

运行时策略只使用以下信息：

- 原始图片。
- CV 候选切点。
- Qwen 对图片、尺寸、候选切点的结构化判断。
- MinerU 对整图或 crop 的 PPL 输出。
- OTSL 文本自身的 token 合法性和 crop 元信息。

运行时没有读取：

- GT `solution`。
- TEDS/TEDS-S 分数。
- baseline parse result 作为 fallback 输入。
- 离线诊断得到的 case ID 白名单或黑名单。

TEDS 和 GT 只用于离线评估、诊断报告和最终策略选择。
