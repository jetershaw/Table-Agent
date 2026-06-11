# 第三阶段验收项 2：re-split 策略 A/B smoke

日期：2026-06-11

## 目标

在验收项 1 标出的候选 regression case 上，对四类 re-split 方法做 smoke，对比当前保存的 aggressive agent 结果，并记录收益、回退与额外调用成本。

## 实验入口

新增 CLI：

```bash
python -m table_agent.cli resplit-smoke \
  --config configs/default.yaml \
  --run-jsonl outputs/e2e_aggressive_48.jsonl \
  --diagnostics-json outputs/third_stage_diagnostics_48.json \
  --indices 11,39,46 \
  --strategies shift_cuts,chunk_count,header_overlap,qwen_header \
  --output-dir outputs/resplit_smoke_acceptance2 \
  --shift-px 48 \
  --header-overlap-px 96
```

评分命令示例：

```bash
python /mnt/shared-storage-user/mineru2-shared/xiaojutao/utils/score_teds_jsonl.py \
  --input-jsonl outputs/resplit_smoke_acceptance2/<strategy>.jsonl \
  --output-jsonl outputs/resplit_smoke_acceptance2/<strategy>.scored.jsonl \
  --pred-field agent_parse_result \
  --gt-field solution
```

## 候选样本

使用验收项 1 的 fallback regression candidates：`[11, 39, 46]`。

当前保存的 aggressive agent 在这 3 条上的均值：`0.7628511487571495`。

当前保存的 worst delta vs baseline：`-0.18792228798040866`。

## 策略定义

| label | SPEC 对应 | 实验定义 |
| --- | --- | --- |
| `shift_cuts` | A：改切点位置 | 将原切点整体下移 48px，越界时反向移动 |
| `chunk_count` | B：改切分段数 | 在原 chunk 数基础上增加 1 段，并重新按 CV safety score 选 cut |
| `header_overlap` | C：header-aware 切分 | 保留原切点，但让后续 crop 向上 overlap 96px 以保留切点附近上下文 |
| `qwen_header` | D：Qwen header 判断辅助切分 | 额外调用 Qwen，以 header/section/total/footnote 风险为重点复审切点 |

## Smoke 结果

| strategy | agent_avg_teds | avg_change_vs_current_agent | improved_cases | regressed_cases | worst_change_vs_current_agent | worst_delta_vs_baseline | extra_mineru_calls | extra_qwen_calls | avg_seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `shift_cuts` | 0.5992455655607557 | -0.16360558319639384 | 0 | 3 | -0.27823547283384076 | -0.4661577608142494 | 6 | 0 | 6.314387024690707 |
| `chunk_count` | 0.2566523140489348 | -0.5061988347082147 | 0 | 3 | -0.5644950148185736 | -0.7524173027989822 | 9 | 0 | 6.4903155857076245 |
| `header_overlap` | 0.5576220735209572 | -0.20522907523619238 | 0 | 3 | -0.31594221583638527 | -0.5038645038167939 | 6 | 0 | 7.13254714384675 |
| `qwen_header` | 0.5576220735209572 | -0.20522907523619238 | 0 | 3 | -0.31594221583638527 | -0.5038645038167939 | 6 | 3 | 8.376732176790634 |

## 结论

四个 re-split smoke 策略在 `[11, 39, 46]` 上均为净负收益，且没有任何 case 相比当前保存的 aggressive agent 得分提升。

`qwen_header` 在三条样本上均保留原切点，没有提出更好的 header-aware 切点；在本轮 smoke 结果下，不值得进入主流程。

暂不推荐将 A/B/C/D 任一 re-split 策略接入 runtime。下一步应按 SPEC 继续做 fallback 反事实实验，因为验收项 1 的 fallback 候选三条均为明显 regression，而本验收项的 re-split 变体未能修复它们。

## 验证

- `python -m py_compile table_agent/resplit_experiment.py table_agent/cli.py`
- `python -m table_agent.cli resplit-smoke --help`
- 单样本探针：`outputs/resplit_smoke_probe/shift_cuts.jsonl`
- 四策略 smoke：`outputs/resplit_smoke_acceptance2/*.jsonl`
- 四策略评分：`outputs/resplit_smoke_acceptance2/*.scored.jsonl`

## 修正补充：完整 header-repeat 策略

前述 `header_overlap` 只是 header-aware 的简化 proxy，不能代表完整 header-aware。根据复核意见，补做了完整 `header_repeat` smoke：

- 用 CV row-density 在表格顶部定位 `header_band`。
- 额外保存并识别 header probe crop，用于估计 `header_row_count`。
- 对每个非首段构造 synthetic crop：`header_band + body chunk`。
- MinerU 识别 synthetic crop 后，在 merge 前尝试从非首段 OTSL 删除重复 header rows。
- metadata 记录 `header_band`、`header_probe`、`header_row_count`、`synthetic_header_repeated`、`removed_header_rows` 和额外调用成本。

运行命令：

```bash
python -m table_agent.cli resplit-smoke \
  --config configs/default.yaml \
  --run-jsonl outputs/e2e_aggressive_48.jsonl \
  --diagnostics-json outputs/third_stage_diagnostics_48.json \
  --indices 11,19,21,39,41,46 \
  --strategies header_repeat \
  --output-dir outputs/resplit_header_repeat_acceptance2_fix
```

评分命令：

```bash
python /mnt/shared-storage-user/mineru2-shared/xiaojutao/utils/score_teds_jsonl.py \
  --input-jsonl outputs/resplit_header_repeat_acceptance2_fix/header_repeat.jsonl \
  --output-jsonl outputs/resplit_header_repeat_acceptance2_fix/header_repeat.scored.jsonl \
  --pred-field agent_parse_result \
  --gt-field solution
```

完整 header-repeat 结果：

| metric | value |
| --- | ---: |
| candidate_count | 6 |
| current_agent_avg_teds_on_6 | 0.8328558964967744 |
| header_repeat_avg_teds_on_6 | 0.5059809358846135 |
| avg_change_vs_current_agent | -0.3268749606121609 |
| improved_cases | 0 |
| regressed_cases | 6 |
| worst_change_vs_current_agent | -0.7368415983665765 |
| extra_mineru_calls | 20 |
| extra_qwen_calls | 0 |
| avg_seconds | 9.541090127080679 |

Per-case：

| index | current_agent_teds | header_repeat_teds | change |
| ---: | ---: | ---: | ---: |
| 11 | 0.770739014536007 | 0.5583956561400171 | -0.21234335839598995 |
| 19 | 0.9054413876919677 | 0.5100677100677101 | -0.39537367762425757 |
| 21 | 0.9754601226993865 | 0.23861852433281006 | -0.7368415983665765 |
| 39 | 0.8146743787489289 | 0.7272727272727273 | -0.0874016514762016 |
| 41 | 0.8276804223178437 | 0.6143331603442892 | -0.21334726197355447 |
| 46 | 0.7031400529865125 | 0.38719783715012723 | -0.31594221583638527 |

补充结论：完整 `header_repeat` 也不值得进入 runtime。主要失败模式是 synthetic crop 后 MinerU 输出结构较弱，crop estimated column count 多数为 0；重复表头没有稳定列语义，反而降低了整体识别质量。因此验收项 2 的最终结论保持不变：当前 re-split/retry 策略不进入主流程，fallback 仍是更可靠的保护路径。
