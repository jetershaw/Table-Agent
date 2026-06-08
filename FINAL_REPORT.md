# Table Agent Final Report

Date: 2026-06-08

## Acceptance Status

All staged acceptance items in `SPEC.md` and `SPEC.zh.md` are complete. The
spec has 14 workflow steps, while the commit-by-commit staged acceptance list is
Section 13 and contains Acceptance Items 1-9.

| Item | Commit | Summary |
| --- | --- | --- |
| 1 | `76988fe` | Project skeleton and config CLI |
| 2 | `fe1aa55` | Vision client smoke test |
| 3 | `7b4f5f0` | Full-image baseline collection |
| 4 | `6233b57` | Vertical split candidate generation |
| 5 | `fd68f4e` | Qwen split review iteration |
| 6 | `f6a6799` | Crop recognition workflow |
| 7 | `4e38051` | OTSL merge and agent parse result |
| 8 | `4e3309e` | End-to-end smoke runner |
| 8 hardening | `52fd969` | Per-sample timeout isolation |
| 9 | `f441b26` | Full evaluation summary |

The benchmark file currently contains 48 non-empty records, so the `--limit 50`
evaluation covers all available large-table samples.

## Evaluation Artifacts

Clean evaluation outputs:

- `outputs/e2e_50_eval.jsonl`: 48 run rows.
- `outputs/e2e_50_eval.baseline.scored.jsonl`: 1 summary row plus 48 scored rows.
- `outputs/e2e_50_eval.agent.scored.jsonl`: 1 summary row plus 48 scored rows.
- `outputs/e2e_50_eval.summary.json`: aggregate summary.

These files are ignored run artifacts and are intentionally not committed.

## Results

From `outputs/e2e_50_eval.summary.json`:

| Metric | Value |
| --- | ---: |
| sample count | 48 |
| baseline average TEDS | 0.059270436493675326 |
| agent average TEDS | 0.059270436493675326 |
| absolute improvement | 0.0 |
| relative improvement | 0.0 |
| success count | 3 |
| partial success count | 0 |
| failure count | 45 |
| average chunk count | 0.0625 |
| average split iterations | 0.1875 |

The measured Table Agent result did not improve over the full-image MinerU
baseline in this run. The result is dominated by MinerU service timeouts: most
samples failed with `sample timed out after 60s`, so this run is best treated as
a reproducibility and diagnostics validation rather than an algorithm-quality
measurement.

## Reproduction

```bash
cd /mnt/shared-storage-user/mineru2-shared/xiaojutao/Table-Agent

conda run -n mineru python -m table_agent.cli run \
  --config configs/default.yaml \
  --limit 50 \
  --output-jsonl outputs/e2e_50_eval.jsonl \
  --sample-timeout 60

python /mnt/shared-storage-user/mineru2-shared/xiaojutao/utils/score_teds_jsonl.py \
  --input-jsonl outputs/e2e_50_eval.jsonl \
  --output-jsonl outputs/e2e_50_eval.baseline.scored.jsonl \
  --pred-field baseline_parse_result \
  --gt-field solution

python /mnt/shared-storage-user/mineru2-shared/xiaojutao/utils/score_teds_jsonl.py \
  --input-jsonl outputs/e2e_50_eval.jsonl \
  --output-jsonl outputs/e2e_50_eval.agent.scored.jsonl \
  --pred-field agent_parse_result \
  --gt-field solution

python -m table_agent.cli summarize \
  --run-jsonl outputs/e2e_50_eval.jsonl \
  --baseline-scored-jsonl outputs/e2e_50_eval.baseline.scored.jsonl \
  --agent-scored-jsonl outputs/e2e_50_eval.agent.scored.jsonl \
  --output-json outputs/e2e_50_eval.summary.json
```

For a cleaner algorithm-quality run, rerun with better MinerU service
availability and a fresh output filename, optionally with a longer
`--sample-timeout`.
