# Table Agent Evaluation Report

Date: 2026-06-11

This is the current project REPORT. Older third-stage stage reports were merged into `SPEC.zh.md` and removed; this file summarizes service routing, evaluation artifacts, final metrics, and interpretation.

## 1. Executive Summary

Current best strategy:

- `split_review_policy: aggressive`
- OTSL stray angle repair
- agent full-image fallback when `column_count_inconsistent` and crop estimated column count spread `>= 3`

Final 48-record large-table result:

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

Interpretation: the final strategy improves average TEDS by about 0.0513 absolute over the full-image MinerU baseline, with four extra MinerU calls from runtime-observable fallback triggers. It is still not uniformly better; remaining regressions should guide the next optimization round.

## 2. Service Routing

The faster MinerU service runs on the worker and listens on:

```text
http://127.0.0.1:8000/v1/chat/completions
```

Worker access used in the latest full evaluation:

```bash
cd /
ssh -CAXY ws-15667b3f02c1236f-worker-v6gjp.xiaojutao+root.ailab-sciversealign.pod@h.pjlab.org.cn -i id_rsa
```

Service notes:

- worker node: `root@shaw-9dc9r-259705-worker-0`
- tmux session: `mineru_8000`
- model: `MinerU-Pro`
- temporary config: `/tmp/table_agent_newmineru_aggressive.yaml`

Earlier requests to the old config endpoint `http://100.103.11.28:20000/v1/chat/completions` did not hit this faster service.

## 3. Runner Fix

The first successful new-service requests exposed a runner bug: completed workers could hang while returning very large JSON rows through `multiprocessing.Queue`, so the parent process did not write the row even after raw MinerU responses had been saved.

The runner now writes each worker row to `raw_responses/e2e_rows/` and sends only the row path/status through the queue.

Commit: `192ac0c Write e2e worker rows through files`.

## 4. Evaluation Timeline

### New MinerU 10-sample smoke

```text
count: 10
success_count: 10
failure_count: 0
baseline_avg_teds: 0.8423279467486602
agent_avg_teds: 0.8636176388810446
absolute_improvement: 0.021289692132384408
relative_improvement: 0.025274825814056694
```

Conclusion: the pipeline could produce successful end-to-end rows, but full 48-record evaluation was needed.

### Stage 1 full 48-record run

Artifacts:

- `outputs/e2e_newmineru_local_48_combined.jsonl`
- `outputs/e2e_newmineru_local_48_combined.baseline.scored.jsonl`
- `outputs/e2e_newmineru_local_48_combined.agent.scored.jsonl`
- `outputs/e2e_newmineru_local_48_combined.summary.json`

Summary:

```text
count: 48
success_count: 48
failure_count: 0
baseline_avg_teds: 0.8634187595356039
agent_avg_teds: 0.8926355322939662
absolute_improvement: 0.02921677275836232
relative_improvement: 0.03383847343562094
```

Main regressions came from single-chunk rerun variance, inconsistent crop column counts, illegal OTSL tokens, and some structure drift without warnings.

### Stage 2 aggressive split full run

Artifacts:

- `outputs/e2e_aggressive_48.jsonl`
- `outputs/e2e_aggressive_48.baseline.scored.jsonl`
- `outputs/e2e_aggressive_48.agent.scored.jsonl`
- `outputs/e2e_aggressive_48.summary.json`

Summary:

```text
count: 48
success_count: 48
failure_count: 0
baseline_avg_teds: 0.8614947094362552
agent_avg_teds: 0.9038593040110346
absolute_improvement: 0.04236459457477948
relative_improvement: 0.04917568745431068
avg_chunk_count: 1.9166666666666667
avg_split_iterations: 1.4583333333333333
```

Conclusion: aggressive split review improved average TEDS over the previous full run, but `column_count_inconsistent` remained the main high-confidence failure signal.

### Stage 3 re-split and fallback evaluation

Re-split strategies tested:

- `shift_cuts`
- `chunk_count`
- `header_overlap`
- `qwen_header`
- full `header_repeat`

Result: all re-split strategies were net negative in smoke experiments, so no retry-first strategy was connected to runtime.

Fallback experiments:

- Full-image fallback on severe `column_count_inconsistent` candidates improved the key fallback cases.
- Cost tiers `low/medium/high/xhigh` were compared.
- `high` was selected: trigger fallback when `column_count_inconsistent` and nonzero crop estimated column count spread `>= 3`.

Final artifacts:

- `outputs/cost_tiers/high.jsonl`
- `outputs/cost_tiers/high.agent.scored.jsonl`
- `outputs/cost_tiers/high.summary.json`

Final summary:

```text
count: 48
baseline_avg_teds: 0.8614947094362552
previous_best_agent_avg_teds: 0.9038593040110346
final_agent_avg_teds: 0.9127643569708148
gain_vs_previous_best: 0.008905052959780195
absolute_improvement_vs_baseline: 0.05126964753455965
relative_improvement_vs_baseline: 0.05951243457793197
success_count: 48
failure_count: 0
fallback_trigger_count: 4
extra_mineru_calls: 4
regression_count: 17
worst_regression: -0.09373351148293152
```

Note: this is a 48-record counterfactual evaluation built from the aggressive full run plus agent-owned full-image fallback rows. It does not reuse baseline parse results.

## 5. Reproduction Commands

Summarize final high fallback artifacts:

```bash
cd /mnt/shared-storage-user/mineru2-shared/xiaojutao/Table-Agent
python -m table_agent.cli summarize \
  --run-jsonl outputs/cost_tiers/high.jsonl \
  --baseline-scored-jsonl outputs/e2e_aggressive_48.baseline.scored.jsonl \
  --agent-scored-jsonl outputs/cost_tiers/high.agent.scored.jsonl \
  --output-json outputs/cost_tiers/high.summary.json \
  --top-k 8
```

TEDS scoring pattern:

```bash
python /mnt/shared-storage-user/mineru2-shared/xiaojutao/utils/score_teds_jsonl.py \
  --input-jsonl outputs/<run>.jsonl \
  --output-jsonl outputs/<run>.agent.scored.jsonl \
  --pred-field agent_parse_result \
  --gt-field solution
```

Large-table TEDS scoring can be slow. A previous full-batch scoring attempt failed without writing output because the scoring script accumulates rows in memory and writes at the end; per-row scoring and merge is safer when needed.

## 6. Known Risks

- Remaining regressions still exist; final regression count is 17 and worst regression is `-0.09373351148293152`.
- Current re-split strategies should not be enabled in runtime because all tested variants were net negative.
- The next likely improvement area is crop merge column alignment and column-count consistency.
- Runtime must not use GT/TEDS/case ID or baseline parse result fallback.
- Retained artifacts under `outputs/`, `crops/`, and `raw_responses/` are useful for inspection and should not be cleaned blindly.
