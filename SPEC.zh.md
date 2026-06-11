# Table Agent 规格与阶段记录

更新时间：2026-06-11

本文档是 Table Agent 的主规格文档。第三阶段阶段性 SPEC/REPORT 已合并并删除；后续以本文档、`PROJECT_MAP.md` 和 `NEW_MINERU_EVAL_NOTES.md` 为准。

## 1. 当前结论

Table Agent 用于超大尺寸、超长表格图片识别：先按纵向切分表格图片，分别调用 MinerU2.5-Pro 识别 crop，合并 OTSL 后转 HTML，再用离线 TEDS 与 GT HTML 评分，并和整图直接识别的 MinerU baseline 对比。

当前推荐策略：

```yaml
split_review_policy: aggressive
```

同时保留：

- OTSL stray angle repair。
- runtime full-image fallback：当 merge warning 包含 `column_count_inconsistent`，且非零 crop estimated column count spread `>= 3` 时，由 agent 自己额外调用一次 MinerU 整图识别并替换输出。

当前 48 条 large-table benchmark 最终结果：

| metric | value |
| --- | ---: |
| count | 48 |
| baseline_avg_teds | 0.8614947094362552 |
| agent_avg_teds | 0.9127643569708148 |
| absolute_improvement | 0.05126964753455965 |
| relative_improvement | 0.05951243457793197 |
| success_count | 48 |
| failure_count | 0 |
| fallback_trigger_count | 4 |
| extra_mineru_calls | 4 |
| regression_count | 17 |
| worst_regression | -0.09373351148293152 |

说明：最终结果是基于 `outputs/e2e_aggressive_48.*` 与 agent 自己额外跑出的 fallback rows 构造的 48 条 counterfactual 评估；fallback 不复用 baseline parse result。

## 2. 数据与环境

项目目录：

```text
/mnt/shared-storage-user/mineru2-shared/xiaojutao/Table-Agent
```

Benchmark JSONL：

```text
/mnt/shared-storage-user/mineru2-shared/xiaojutao/bench/fine_grained_bench/fine_grained_bench-large_table.jsonl
```

默认图片目录：

```text
/mnt/shared-storage-user/mineru2-shared/xiaojutao/bench/fine_grained_bench/images
```

可复用工具：

```text
/mnt/shared-storage-user/mineru2-shared/xiaojutao/utils/otsl2html.py
/mnt/shared-storage-user/mineru2-shared/xiaojutao/utils/score_teds_jsonl.py
```

最近完整评估使用的 MinerU 服务：

```text
endpoint: http://127.0.0.1:8000/v1/chat/completions
model: MinerU-Pro
tmux session: mineru_8000
```

对应 worker 连接信息保留在 `NEW_MINERU_EVAL_NOTES.md`。

## 3. 运行时边界

运行时可以使用：

- 原始表格图片。
- CV 生成的候选切点。
- Qwen 对图片、图片尺寸、候选切点的判断。
- MinerU 对整图或 crop 的真实 PPL 输出。
- OTSL/HTML 自身结构信号。
- crop 数量、图片尺寸、行列估计、warning 等元信息。

运行时不允许使用：

- GT `solution`。
- TEDS/TEDS-S 分数。
- baseline parse result 作为 agent fallback 输入。
- 离线诊断得到的 case ID 白名单或黑名单。

GT 和 TEDS 只用于离线评分、诊断报告和最终策略选择。

## 4. 系统分层

### 4.1 配置与数据

- `configs/default.yaml`：默认服务、路径、agent 参数。
- `table_agent/config.py`：配置 dataclass 与校验。
- `table_agent/benchmark.py`：读取 benchmark JSONL 并解析图片路径。
- `table_agent/image_io.py`：图片加载与编码。

### 4.2 服务客户端

- `table_agent/client.py`：OpenAI-compatible vision client，主要用于 Qwen。
- `table_agent/mineru_client.py`：MinerU 表格识别服务封装。
- `table_agent/baseline.py`：整图 MinerU baseline 收集，也提供 JSON 写入 helper。

### 4.3 切分、识别与合并

- `table_agent/splitter.py`：CV 纵向切分候选生成。
- `table_agent/split_review.py`：Qwen split/no-split 结构化决策；支持 `conservative` 和 `aggressive`。
- `table_agent/recognition.py`：crop 识别。
- `table_agent/otsl.py`：OTSL 合并、验证、HTML 转换、stray angle repair。
- `table_agent/merge.py`：CLI 用 merge wrapper。

### 4.4 端到端、诊断与实验

- `table_agent/runner.py`：端到端 batch runner；包含当前 runtime fallback 保护。
- `table_agent/evaluation.py`：汇总 scored baseline/agent JSONL。
- `table_agent/diagnostics.py`：离线 case-level 诊断。
- `table_agent/resplit_experiment.py`：第三阶段 re-split smoke 实验入口，保留作离线实验工具。
- `table_agent/fallback_experiment.py`：第三阶段 full-image fallback 反事实实验入口，保留作离线实验工具。
- `table_agent/cli.py`：所有 CLI 命令入口。

## 5. 阶段历史

### 阶段 0：项目搭建与基础流水线

目标：搭建可运行的 Table Agent 流水线，包括 baseline、split、crop recognition、OTSL merge、HTML conversion 和离线评分。

代表性提交：`76988fe`、`fe1aa55`、`7b4f5f0`、`6233b57`、`fd68f4e`、`f6a6799`、`4e38051`、`4e3309e`、`52fd969`、`f441b26`、`bf0705c`、`7e39a1b`。

结论：基础链路可跑通，但服务速度、长 JSON row 回传和 regression 诊断仍需要改进。

### 阶段 1：新 MinerU 服务与 48 条基线评估

目标：切换到更快的本地 MinerU 服务，并修复端到端 runner 在大 JSON row 上的 multiprocessing queue 卡住问题。

关键提交：`192ac0c Write e2e worker rows through files`。

48 条 large-table 结果：

| metric | value |
| --- | ---: |
| baseline_avg_teds | 0.8634187595356039 |
| agent_avg_teds | 0.8926355322939662 |
| absolute_improvement | 0.02921677275836232 |
| relative_improvement | 0.03383847343562094 |
| success_count | 48 |
| failure_count | 0 |

主要问题：仍有明显 regression，尤其是 single-chunk rerun 波动、multi-chunk 列数不一致、非法 OTSL token 和无 warning 的结构波动。

### 阶段 2：性能提升与 aggressive split 策略

目标：分析 regression pattern，加入 Qwen 结构化 split decision，比较 conservative/aggressive 策略，并修复 OTSL stray angle token 问题。

关键提交：

```text
00868a3 Add offline run diagnostics
297cce4 Document performance regression patterns
3e54d82 Add Qwen split decision metadata
b29a67b Record conservative strategy smoke
62d037d Add aggressive split review policy
b0fe9a3 Repair stray OTSL angle brackets
0a48b75 Document final strategy evaluation
```

阶段 2 最终 48 条 aggressive full run：

| metric | value |
| --- | ---: |
| baseline_avg_teds | 0.8614947094362552 |
| agent_avg_teds | 0.9038593040110346 |
| absolute_improvement | 0.04236459457477948 |
| relative_improvement | 0.04917568745431068 |
| success_count | 48 |
| failure_count | 0 |
| avg_chunk_count | 1.9166666666666667 |
| avg_split_iterations | 1.4583333333333333 |

保留 artifacts：

- `outputs/e2e_aggressive_48.jsonl`
- `outputs/e2e_aggressive_48.baseline.scored.jsonl`
- `outputs/e2e_aggressive_48.agent.scored.jsonl`
- `outputs/e2e_aggressive_48.summary.json`

结论：`aggressive` 优于前一版 `0.8926355322939662`，但列数不一致仍是主要 regression 来源。

### 阶段 3：Regression-aware re-split 与 fallback

目标：在 aggressive split+merge 基础上，验证 retry/re-split 和 fallback 是否能进一步减少坏例并提升均分。

关键提交：

```text
1dda7c4 Add third-stage offline diagnostics candidates
8285542 Add third-stage resplit smoke experiments
ca5af92 Add third-stage fallback counterfactual
05de228 Add runtime fallback protection
aa741de Add full header-repeat resplit experiment
352a39f Add third-stage cost tier report
6dd8a4f Select high fallback tier for final evaluation
b667e73 Document third-stage delivery
4f63e69 8: 收尾归档第三阶段文档
927138a 8: 删除第三阶段阶段文档
```

验收结论：

| 验收项 | 归档结论 |
| --- | --- |
| 1. 离线诊断与候选统计 | 完成，识别 retry/fallback 候选和运行时可观测信号。 |
| 2. re-split A/B smoke | 完成，`shift_cuts`、`chunk_count`、`header_overlap`、`qwen_header`、完整 `header_repeat` 均为净负收益。 |
| 3. retry-first 接入 | 跳过；没有已验证正收益 re-split 策略可接入。 |
| 4. fallback 反事实 | 完成，严重 `column_count_inconsistent` case 上 full-image fallback 净提升。 |
| 5. runtime fallback 保护 | 完成，agent 路径额外调用 MinerU 整图，不复用 baseline result。 |
| 6. 成本档位 | 完成，`high` 档位均分最高，额外 MinerU 调用 4 次。 |
| 7. 最终 48 条评估 | 完成，最终 `agent_avg_teds=0.9127643569708148`。 |
| 8. 文档交付与归档 | 完成，阶段性 SPEC/REPORT 已合并并删除。 |

最终 high fallback artifacts：

- `outputs/cost_tiers/high.jsonl`
- `outputs/cost_tiers/high.agent.scored.jsonl`
- `outputs/cost_tiers/high.summary.json`

结论：re-split/retry 暂不进入 runtime；最终推荐 aggressive split+merge + severe column spread full-image fallback。

## 6. 复现命令

完整 aggressive run 示例：

```bash
cd /mnt/shared-storage-user/mineru2-shared/xiaojutao/Table-Agent
conda run -n mineru python -m table_agent.cli run \
  --config /tmp/table_agent_newmineru_aggressive.yaml \
  --output-jsonl outputs/e2e_aggressive_48.jsonl \
  --sample-timeout 600
```

汇总 high fallback 最终 artifacts：

```bash
python -m table_agent.cli summarize \
  --run-jsonl outputs/cost_tiers/high.jsonl \
  --baseline-scored-jsonl outputs/e2e_aggressive_48.baseline.scored.jsonl \
  --agent-scored-jsonl outputs/cost_tiers/high.agent.scored.jsonl \
  --output-json outputs/cost_tiers/high.summary.json \
  --top-k 8
```

TEDS 评分命令模式：

```bash
python /mnt/shared-storage-user/mineru2-shared/xiaojutao/utils/score_teds_jsonl.py \
  --input-jsonl outputs/<run>.jsonl \
  --output-jsonl outputs/<run>.agent.scored.jsonl \
  --pred-field agent_parse_result \
  --gt-field solution
```

注意：整批 TEDS 评分在大表上曾异常退出且不落盘；必要时逐条评分后合并 scored JSONL。

## 7. 保留 artifacts

当前保留最新 full run 和第三阶段复核相关产物，便于人工检查：

- `outputs/e2e_aggressive_48.*`
- `outputs/cost_tiers/high.*`
- `outputs/fallback_smoke_acceptance4/*`
- `outputs/fallback_smoke_cost_tiers/*`
- `outputs/resplit_smoke_acceptance2/*`
- `outputs/resplit_header_repeat_acceptance2_fix/*`
- `outputs/third_stage_diagnostics_48.json`
- `crops/e2e_*.jpg`
- `crops/resplit_*`
- `raw_responses/e2e_baseline/*.json`
- `raw_responses/e2e_crops/*.json`
- `raw_responses/e2e_fallback/*.json`

已清理：

- `table_agent/__pycache__/`
- `outputs/resplit_smoke_probe/`
- 旧顶层 fallback counterfactual 三件套。
- 第三阶段阶段性 SPEC/REPORT 文件。

## 8. 下一轮优化建议

1. 优先改进 crop merge 的列对齐与列数一致性，而不是继续尝试当前 re-split 策略。
2. 保持 runtime 边界：不能使用 GT、TEDS、case ID 或 baseline parse result fallback。
3. 若重新跑完整评测，输出到独立 run 名称，避免与保留 artifacts 混淆。
4. 改 Qwen prompt 时保持 `split_decision` metadata 字段，便于诊断和复现。
5. 对高成本策略必须记录 `extra_mineru_calls`、`extra_qwen_calls`、fallback/retry metadata 和最终选择来源。
