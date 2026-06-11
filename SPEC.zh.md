# Table Agent 规格与性能提升记录

更新时间：2026-06-11

本文档是 Table Agent 的主规格文档，已合并原始 SPEC、性能提升 SPEC、第三阶段 SPEC、阶段性 REPORT/SMOKE 记录和 SESSION_HANDOFF 中仍有用的信息。旧阶段文档仅作审计留存，后续以本文档为准。

## 1. 项目目标

构建一个用于超大尺寸、超长表格图片识别的 Table Agent。

Agent 对长表格图片进行纵向切分，分别调用 MinerU2.5-Pro 表格识别服务识别每个切片，得到多个 OTSL 结果后进行拼接，再将拼接后的 OTSL 转换为 HTML，最后用 TEDS 与 GT HTML 做离线评分，并和整图直接识别的 MinerU2.5-Pro baseline 对比。

核心实验问题：

> 纵向切分 + 子图识别 + OTSL 拼接，是否能比 MinerU2.5-Pro 整图直接识别获得更高的 TEDS？

本轮性能提升目标是在 48 条 large-table benchmark 上提升 `agent_avg_teds`，同时分析并减少 regression case。第二阶段 aggressive 最佳为 `agent_avg_teds=0.9038593040110346`；第三阶段最终推荐 high fallback 策略，完整 48 条 counterfactual 评估达到 `agent_avg_teds=0.9127643569708148`。

## 2. 项目位置与数据

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

## 4. 模型服务与环境

两个模型服务通过 OpenAI-compatible HTTP API 调用：

- MinerU2.5-Pro 表格识别服务。
- Qwen3.5-397B VLM/LLM 决策服务。

默认 API 形式：

```text
POST http://<host>:<port>/v1/chat/completions
```

MinerU 表格识别 prompt：

```text
Table Recognition: xxx
```

最近一次完整评估使用的 MinerU 服务节点：

```bash
cd /
ssh -CAXY ws-15667b3f02c1236f-worker-v6gjp.xiaojutao+root.ailab-sciversealign.pod@h.pjlab.org.cn -i id_rsa
```

服务信息：

- 节点：`root@shaw-9dc9r-259705-worker-0`
- MinerU endpoint：`http://127.0.0.1:8000/v1/chat/completions`
- tmux session：`mineru_8000`
- model：`MinerU-Pro`
- MinerU 相关命令建议使用 `conda run -n mineru ...`

注意：TEDS 评分在 base Python 环境可用；`mineru` env 曾缺少 `lxml`，评分时需确认环境依赖。

## 5. 当前实现文件

核心代码：

- `table_agent/cli.py`：CLI 入口，包含 `run`、`summarize`、`diagnose` 等命令。
- `table_agent/config.py`：配置结构，包含 `split_review_policy`。
- `table_agent/runner.py`：端到端 benchmark runner、agent metadata 输出和 runtime full-image fallback 保护。
- `table_agent/baseline.py`：整图 MinerU baseline。
- `table_agent/splitter.py`：CV 候选切点生成。
- `table_agent/split_review.py`：Qwen split/no-split 结构化决策。
- `table_agent/recognition.py`：crop 识别流程。
- `table_agent/otsl.py`：OTSL 合并、验证和轻量修复。
- `table_agent/evaluation.py`：baseline/agent scored JSONL 汇总。
- `table_agent/diagnostics.py`：离线 case-level 诊断。
- `table_agent/resplit_experiment.py`：第三阶段 re-split smoke 实验入口。
- `table_agent/fallback_experiment.py`：第三阶段 full-image fallback 反事实实验入口。

外部工具：

- `../utils/score_teds_jsonl.py`：TEDS/TEDS-S 评分。
- `../utils/mineru_server.sh`：MinerU 服务启动脚本。

## 6. 已完成验收项

| 验收项 | 状态 | 完成方式 | 关键文件/结果 |
| --- | --- | --- | --- |
| 1. 离线诊断统计 | 完成 | 新增 `diagnose` CLI，读取 run/scored artifacts 输出 case-level 统计 | `table_agent/diagnostics.py`, `table_agent/cli.py` |
| 2. 错误 pattern 归因 | 完成 | 诊断 48 条 regression pattern，识别 single-chunk rerun、列数不一致、非法 OTSL token 等问题 | 已合并到本文档第 7 节 |
| 3. Qwen split/no-split 决策 | 完成 | Qwen 输出 `should_split`、`complexity`、`risk_factors`、`cuts`、`reason`，解析失败有安全降级 | `table_agent/split_review.py`, `table_agent/runner.py` |
| 4. 保守策略实验 | 完成 | 在 7-11 smoke 上验证保守策略，主要用于减少不确定切分 | 结果见第 8 节 |
| 5. 积极策略实验 | 完成 | 新增 `split_review_policy: aggressive`，复杂表格更积极切分 | `table_agent/config.py`, `table_agent/split_review.py` |
| 6. OTSL/crop 后处理实验 | 完成 | 新增 `repair_stray_otsl_angles` 修复文本裸 `<` 造成的非法 token | `table_agent/otsl.py` |
| 7. 最终策略选择与清理 | 完成 | 完整 48 条评估，推荐 aggressive + OTSL repair，并清理阶段文档和旧中间产物 | 本文档、保留的最新 artifacts |

对应关键提交：

```text
0a48b75 Document final strategy evaluation
b0fe9a3 Repair stray OTSL angle brackets
62d037d Add aggressive split review policy
b29a67b Record conservative strategy smoke
3e54d82 Add Qwen split decision metadata
297cce4 Document performance regression patterns
00868a3 Add offline run diagnostics
a9f2b1b Add performance improvement spec
```

更早项目搭建阶段的重要提交包括：`76988fe`、`fe1aa55`、`7b4f5f0`、`6233b57`、`fd68f4e`、`f6a6799`、`4e38051`、`4e3309e`、`52fd969`、`f441b26`、`bf0705c`、`192ac0c`、`7e39a1b`。

## 7. 诊断结论

基于上一版 48 条结果：

```text
count: 48
baseline_avg_teds: 0.8634187595356039
agent_avg_teds: 0.8926355322939662
absolute_improvement: 0.02921677275836232
relative_improvement: 0.03383847343562094
improvement case: 15
unchanged case: 21
regression case: 12
```

主要 regression pattern：

1. single-chunk rerun 波动。
   - 代表 case：7、8、31、38。
   - agent 最终只有 1 个 chunk，本质是重新调用 MinerU 整图识别，可能出现与 baseline 不一致的随机波动。
2. multi-chunk 列数不一致。
   - 代表 case：11、46。
   - warning 包括 `column_count_inconsistent`，是大幅 regression 的主要来源。
3. crop OTSL 非法 token。
   - 代表 case：11。
   - 文本里的裸 `<`，例如 `% FINES <#200 (%)`，会被 OTSL token validator 误判。
4. 无 warning 的结构波动。
   - 部分 case 没有明显 warning，但切分或重跑后 TEDS 下降。

这些诊断只用于离线分析，运行时策略没有读取 GT、TEDS 或样本 ID。

## 8. 实验结果

### 保守策略 smoke

范围：benchmark indices 7-11，共 5 条。

```text
success: 5 / 5
baseline_avg_teds: 0.8850028278680522
agent_avg_teds: 0.8101394181017858
absolute_improvement: -0.07486340976626638
relative_improvement: -0.08459115316796252
avg_chunk_count: 1.6
avg_split_iterations: 1.4
```

结论：保守策略可以减少不确定切分，但该 smoke 子集上平均分低于 baseline。

### 积极策略 smoke

范围：benchmark indices 7-11，共 5 条。

```text
success: 5 / 5
baseline_avg_teds: 0.8847791142215197
agent_avg_teds: 0.8624223842043918
absolute_improvement: -0.0223567300171279
relative_improvement: -0.025268148465279562
avg_chunk_count: 2.0
avg_split_iterations: 1.8
```

结论：同一子集上 aggressive 明显优于 conservative，但仍未超过 baseline。

### OTSL repair smoke

范围：benchmark index 11。

```text
baseline_avg_teds: 0.9167916461149543
agent_avg_teds: 0.770739014536007
absolute_improvement: -0.14605263157894732
```

OTSL repair 将 `illegal_otsl_tokens` warning 替换为 `repaired_stray_otsl_angle:0`，但 `column_count_inconsistent:[21, 17]` 仍存在。结论：该修复能消除非法 token，但不能单独解决列数不一致。


### 第三阶段 high fallback 最终策略

第三阶段在 aggressive split+merge 基础上验证 retry/fallback：

- `shift_cuts`、`chunk_count`、`header_overlap`、`qwen_header` 和完整 `header_repeat` re-split smoke 均为净负收益，不进入 runtime。
- full-image fallback 对严重 `column_count_inconsistent` regression 有效。
- 成本档位实验中 `high` 均分最高：当 `column_count_inconsistent` 且非零 crop estimated column count spread `>= 3` 时，agent 自己额外调用 1 次 MinerU full-image fallback。
- fallback 不复用 baseline parse result，不使用 GT/TEDS/case id。

第三阶段最终 48 条 counterfactual artifacts：

- `outputs/cost_tiers/high.jsonl`
- `outputs/cost_tiers/high.agent.scored.jsonl`
- `outputs/cost_tiers/high.summary.json`

最终指标：

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
| regression_count | 17 |
| worst_regression | -0.09373351148293152 |

第三阶段验收归档：

| 验收项 | 结论 | 归档报告 |
| --- | --- | --- |
| 1. 离线诊断与候选统计 | 完成，识别 retry/fallback 候选和运行时可观测信号 | `THIRD_STAGE_ACCEPTANCE_1_REPORT.zh.md` |
| 2. re-split A/B smoke | 完成，`shift_cuts`、`chunk_count`、`header_overlap`、`qwen_header`、完整 `header_repeat` 均为净负收益 | `THIRD_STAGE_ACCEPTANCE_2_REPORT.zh.md` |
| 3. retry-first 接入 | 跳过；没有已验证正收益 re-split 策略可接入 | `THIRD_STAGE_ACCEPTANCE_8_REPORT.zh.md` |
| 4. fallback 反事实 | 完成，严重 `column_count_inconsistent` case 上 full-image fallback 净提升 | `THIRD_STAGE_ACCEPTANCE_4_REPORT.zh.md` |
| 5. runtime fallback 保护 | 完成，agent 路径额外调用 MinerU 整图，不复用 baseline result | `THIRD_STAGE_ACCEPTANCE_5_REPORT.zh.md` |
| 6. 成本档位 | 完成，`high` 档位均分最高，额外 MinerU 调用 4 次 | `THIRD_STAGE_ACCEPTANCE_6_REPORT.zh.md` |
| 7. 最终 48 条评估 | 完成，最终 `agent_avg_teds=0.9127643569708148` | `THIRD_STAGE_ACCEPTANCE_7_REPORT.zh.md` |
| 8. 文档交付与归档 | 完成，第三阶段 SPEC/REPORT 摘要合并进本文档和第 8 项总报告 | `THIRD_STAGE_ACCEPTANCE_8_REPORT.zh.md` |

`THIRD_STAGE_OPTIMIZATION_SPEC.zh.md` 和分项报告保留为审计材料；本节与 `THIRD_STAGE_ACCEPTANCE_8_REPORT.zh.md` 是第三阶段合并后的阅读入口。

### 第二阶段最终 48 条 aggressive full run

保留 artifacts：

- `outputs/e2e_aggressive_48.jsonl`
- `outputs/e2e_aggressive_48.baseline.scored.jsonl`
- `outputs/e2e_aggressive_48.agent.scored.jsonl`
- `outputs/e2e_aggressive_48.summary.json`
- `crops/e2e_*.jpg` 中被 `outputs/e2e_aggressive_48.jsonl` 引用的最新 crop 图片。
- `raw_responses/e2e_baseline/*.json` 和 `raw_responses/e2e_crops/*.json` 中被最新 run 引用的原始响应。

最终指标：

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

相对上一版目标 `agent_avg_teds=0.8926355322939662`，提升 `+0.011223771717068434`。
metric	含义
count	参与统计的样本数，这里是 48 条表格图片。
baseline_avg_teds	baseline 的平均 TEDS 分数。baseline 指整图直接送 MinerU 识别，不经过 agent 切分。
agent_avg_teds	agent 的平均 TEDS 分数。agent 指经过 Qwen 判断是否切分、crop 识别、OTSL 合并后的结果。
absolute_improvement	绝对提升量，等于 agent_avg_teds - baseline_avg_teds。这里是 0.903859 - 0.861495 = 0.042365。
relative_improvement	相对提升比例，等于 absolute_improvement / baseline_avg_teds。这里约等于 4.92%。
success_count	agent 成功产出结果的样本数。这里 48 条都成功。
failure_count	agent 失败的样本数。这里是 0。
avg_chunk_count	每张图平均被切成多少个 chunk。这里是 1.9167，说明大多数图被切成约 2 段，也有少数不切或切成更多段。
avg_split_iterations	平均每张图经历了多少轮 split review / 切分决策迭代。这里是 1.4583。
一句话总结：
baseline 整图识别平均 TEDS 是 0.8615，agent 平均是 0.9039，所以 agent 在这 48 条上平均提升了约 0.0424，相对提升约 4.92%。

Most improved Top 8：

| index | delta_teds | baseline | agent | warning |
| ---: | ---: | ---: | ---: | --- |
| 31 | +0.6279866573114815 | 0.30991904247422075 | 0.9379056997857023 | none |
| 43 | +0.3718225014186255 | 0.5841333503098209 | 0.9559558517284464 | none |
| 34 | +0.349395710452158 | 0.5473033957239031 | 0.8966991061760611 | none |
| 22 | +0.31015619376664494 | 0.6247030878859858 | 0.9348592816526308 | none |
| 28 | +0.24075129582890287 | 0.7543649247304491 | 0.995116220559352 | none |
| 5 | +0.210545933669666 | 0.6569754338517015 | 0.8675213675213675 | none |
| 13 | +0.1474141054311212 | 0.8328073298623037 | 0.9802214352934249 | none |
| 40 | +0.11166733433256892 | 0.8572357019064125 | 0.9689030362389814 | none |

Most regressed Top 8：

| index | delta_teds | baseline | agent | warning |
| ---: | ---: | ---: | ---: | --- |
| 46 | -0.18792228798040866 | 0.8910623409669212 | 0.7031400529865125 | `column_count_inconsistent:[36, 29]` |
| 11 | -0.14605263157894732 | 0.9167916461149543 | 0.770739014536007 | `repaired_stray_otsl_angle:0`, `column_count_inconsistent:[21, 17]` |
| 19 | -0.09373351148293152 | 0.9991748991748992 | 0.9054413876919677 | `column_count_inconsistent:[25, 23]` |
| 1 | -0.07522720743653699 | 0.9225449515905948 | 0.8473177441540578 | none |
| 39 | -0.0609994756985105 | 0.8756738544474394 | 0.8146743787489289 | `column_count_inconsistent:[21, 11]` |
| 6 | -0.0540395261531611 | 0.977227572967938 | 0.923188046814777 | none |
| 41 | -0.03246814681158283 | 0.8601485691294265 | 0.8276804223178437 | `column_count_inconsistent:[20, 17]` |
| 12 | -0.031198179524152825 | 0.914193302891933 | 0.8829951233677802 | none |

## 9. 推荐策略

推荐采用：

```yaml
split_review_policy: aggressive
```

并保留：

- OTSL stray angle repair。
- runtime full-image fallback：当 merge warning 包含 `column_count_inconsistent`，且 crop estimated column count spread `>= 3` 时，由 agent 自己额外调用一次 MinerU 整图识别并替换输出。

原因：

- aggressive full run 在 48 条上达到 `agent_avg_teds=0.9038593040110346`，高于上一版 `0.8926355322939662`。
- 第三阶段 high fallback counterfactual 在 48 条上达到 `agent_avg_teds=0.9127643569708148`，比 aggressive full run 再提升 `+0.008905052959780195`。
- 最显著收益来自复杂大表，尤其是 baseline 低分样本被切分后大幅改善。
- re-split retry 策略在 smoke 中均为净负收益，暂不进入 runtime。
- 代价是仍有若干 regression，需要后续继续修复合并/列对齐逻辑。

## 10. 复现命令

完整 48 条运行：

```bash
cd /mnt/shared-storage-user/mineru2-shared/xiaojutao/Table-Agent
conda run -n mineru python -m table_agent.cli run   --config /tmp/table_agent_newmineru_aggressive.yaml   --output-jsonl outputs/e2e_aggressive_48.jsonl   --sample-timeout 600
```

汇总：

```bash
python -m table_agent.cli summarize   --run-jsonl outputs/e2e_aggressive_48.jsonl   --baseline-scored-jsonl outputs/e2e_aggressive_48.baseline.scored.jsonl   --agent-scored-jsonl outputs/e2e_aggressive_48.agent.scored.jsonl   --output-json outputs/e2e_aggressive_48.summary.json   --top-k 8
```

注意：整批 TEDS 评分在大表上曾异常退出且不落盘。本次最终评估采用逐条评分后合并 scored JSONL 的方式。合并后的 scored 文件格式仍与 `score_teds_jsonl.py` 输出兼容：第一行为 `__summary__`，后续 48 行为样本行。

第三阶段 high fallback 复核 artifacts：

```text
outputs/cost_tiers/high.jsonl
outputs/cost_tiers/high.agent.scored.jsonl
outputs/cost_tiers/high.summary.json
```

## 11. 中间产物清理约定

当前保留最新 full run 和第三阶段复核相关产物，便于人工检查：

- `outputs/e2e_aggressive_48.*`
- `outputs/cost_tiers/high.*`
- `outputs/fallback_smoke_acceptance4/*`
- `outputs/fallback_smoke_cost_tiers/*`
- `outputs/resplit_smoke_acceptance2/*`
- `outputs/resplit_header_repeat_acceptance2_fix/*`
- `outputs/third_stage_diagnostics_48.json`
- 最新 run 引用的 `crops/e2e_*.jpg`
- 第三阶段 re-split 实验 JSONL 间接引用的 `crops/resplit_*` 图片。
- 最新 run 引用的 `raw_responses/e2e_baseline/*.json`
- 最新 run 引用的 `raw_responses/e2e_crops/*.json`
- fallback 运行引用的 `raw_responses/e2e_fallback/*.json`。

已清理的安全临时产物：

- Python bytecode cache：`table_agent/__pycache__/`。
- 单样本 re-split 探针目录：`outputs/resplit_smoke_probe/`。
- 已由 `outputs/cost_tiers/high.*` 取代的旧顶层 fallback counterfactual 三件套。

其它 smoke、历史 run、review、recognize、manual raw response 产物若未被报告或 JSONL 引用，可以在确认后清理。

## 12. 后续注意事项

1. 不要把 baseline parse result 作为 agent fallback 输入，除非另立规格并重新确认，因为这会改变当前实验定义。
2. `split_review_policy: aggressive` 是目前推荐策略，但不是无风险策略；后续最值得优化的是 crop 合并时的列对齐/列数一致性。
3. Qwen split review 的结构化 JSON 是诊断和复现实验的重要信息，后续改 prompt 时应保持 `split_decision` 元数据。
4. OTSL repair 只解决裸 `<` 的非法 token，不解决列数不一致。
5. 若重新跑完整评测，建议先清空旧中间产物或输出到独立 run 目录，避免 `crops/`、`outputs/`、`raw_responses/` 混入历史文件。
6. 本项目目录中的中间产物多数被 `.gitignore` 忽略；需要提交的是代码、配置和主规格文档，不提交大体积 run artifacts。
