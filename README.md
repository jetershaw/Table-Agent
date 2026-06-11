# Table Agent

Table Agent experiments with vertical splitting for very large table images,
crop-level MinerU recognition, OTSL merging, runtime fallback protection, and
TEDS comparison against a full-image MinerU baseline.

## Project Structure

- `configs/`: YAML configuration.
- `table_agent/`: Python package for config, clients, splitting, recognition,
  merging, fallback, diagnostics, and batch execution.
- `outputs/`: ignored JSONL outputs and summaries.
- `raw_responses/`: ignored saved model responses and worker row files for debugging.
- `crops/`: ignored generated crop images.

## Important Docs

- `SPEC.zh.md`: canonical spec, stage history, current strategy, and final metrics.
- `NEW_MINERU_EVAL_NOTES.md`: current evaluation report.
- `PROJECT_MAP.md`: model-facing project guide for the next coding agent.

## Config Check

```bash
python -m table_agent.cli config --config configs/default.yaml
```

## Current Best Result

Current recommended runtime strategy:

- `split_review_policy: aggressive`
- OTSL stray angle repair enabled
- agent full-image fallback when `column_count_inconsistent` and crop estimated column count spread `>= 3`

Final 48-record large-table result:

```text
count: 48
success_count: 48
failure_count: 0
baseline_avg_teds: 0.8614947094362552
agent_avg_teds: 0.9127643569708148
absolute_improvement: 0.05126964753455965
relative_improvement: 0.05951243457793197
fallback_trigger_count: 4
extra_mineru_calls: 4
```

Primary artifacts:

```text
outputs/cost_tiers/high.jsonl
outputs/cost_tiers/high.agent.scored.jsonl
outputs/cost_tiers/high.summary.json
outputs/e2e_aggressive_48.baseline.scored.jsonl
```

See `SPEC.zh.md` for stage-by-stage history and `NEW_MINERU_EVAL_NOTES.md` for the evaluation report.
