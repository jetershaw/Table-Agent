# Table Agent Project Map

Last updated: 2026-06-11

This is a navigation map for future coding agents. It is not a requirements document. Use it to understand the project layers, entry points, retained artifacts, and which files to read before starting the next SPEC task.

## 1. Read First

Start here, in this order:

1. `PROJECT_MAP.md`
   - Orientation for the next agent; keep this concise and model-facing.
2. `SPEC.zh.md`
   - Canonical project spec, current strategy, stage history, retained artifacts, and next optimization guidance.
3. `NEW_MINERU_EVAL_NOTES.md`
   - Current REPORT: service notes, final metrics, artifacts, interpretation, and known risks.
4. `configs/default.yaml`
   - Default service/path/agent parameters.
5. `../utils/CLAUDE.md`
   - Local engineering rules for this workspace.

Do not start by scanning every file. The files above are enough to understand the current state and choose the next task.

## 2. Current Best Result

Recommended runtime strategy:

- Aggressive split review.
- OTSL stray angle repair.
- Agent full-image fallback when merge emits `column_count_inconsistent` and crop estimated column count spread is `>= 3`.

Current best 48-case result:

| metric | value |
| --- | ---: |
| baseline_avg_teds | 0.8614947094362552 |
| agent_avg_teds | 0.9127643569708148 |
| absolute_improvement | 0.05126964753455965 |
| relative_improvement | 0.05951243457793197 |
| success_count | 48 |
| failure_count | 0 |
| fallback_trigger_count | 4 |
| extra_mineru_calls | 4 |

Primary artifacts:

- `outputs/cost_tiers/high.jsonl`
- `outputs/cost_tiers/high.agent.scored.jsonl`
- `outputs/cost_tiers/high.summary.json`
- `outputs/e2e_aggressive_48.baseline.scored.jsonl`

Previous aggressive full-run artifacts retained for comparison:

- `outputs/e2e_aggressive_48.jsonl`
- `outputs/e2e_aggressive_48.agent.scored.jsonl`
- `outputs/e2e_aggressive_48.summary.json`

## 3. System Layers

Pipeline flow:

```text
benchmark row
  -> baseline full-image MinerU recognition
  -> CV vertical split proposal
  -> Qwen split/no-split review
  -> crop image saving
  -> MinerU crop recognition
  -> OTSL repair/merge
  -> optional agent full-image fallback on severe column spread
  -> HTML conversion
  -> agent_parse_result + metadata
  -> offline TEDS scoring and summary
```

Runtime boundary:

- Runtime must not use GT `solution`, TEDS/TEDS-S, case-id white/blacklists, or baseline parse result fallback.
- Offline diagnostics/evaluation may use GT/TEDS.
- Fallback is an agent-owned extra MinerU full-image call, not reuse of `baseline_parse_result`.

## 4. Entry Points

Main CLI: `table_agent/cli.py`

Useful commands:

- `python -m table_agent.cli config`
- `python -m table_agent.cli smoke`
- `python -m table_agent.cli baseline`
- `python -m table_agent.cli split`
- `python -m table_agent.cli split-review`
- `python -m table_agent.cli crop-recognize`
- `python -m table_agent.cli merge`
- `python -m table_agent.cli run`
- `python -m table_agent.cli summarize`
- `python -m table_agent.cli diagnose`
- `python -m table_agent.cli resplit-smoke`
- `python -m table_agent.cli fallback-smoke`

## 5. Module Map

Configuration and data:

- `table_agent/config.py`: service/path/agent config dataclasses and validation.
- `table_agent/benchmark.py`: benchmark JSONL iteration and image path resolution.
- `table_agent/image_io.py`: image loading/encoding helpers.

Service clients:

- `table_agent/client.py`: OpenAI-compatible vision client for Qwen.
- `table_agent/mineru_client.py`: MinerU table-recognition client.
- `table_agent/baseline.py`: full-image MinerU baseline collection and JSON write helper.

Agent pipeline:

- `table_agent/splitter.py`: CV vertical split proposal.
- `table_agent/split_review.py`: Qwen split/no-split review; supports `conservative` and `aggressive`.
- `table_agent/recognition.py`: crop recognition.
- `table_agent/otsl.py`: OTSL validation, repair, merge, and HTML conversion.
- `table_agent/merge.py`: CLI merge wrapper.
- `table_agent/runner.py`: end-to-end runner and final runtime fallback protection.

Offline analysis/experiments:

- `table_agent/evaluation.py`: summary from run + scored JSONL files.
- `table_agent/diagnostics.py`: case-level diagnostics.
- `table_agent/resplit_experiment.py`: retained re-split smoke experiment tool; current strategies were net negative.
- `table_agent/fallback_experiment.py`: retained fallback counterfactual experiment tool.

## 6. Retained Artifacts

Keep these unless a future SPEC explicitly replaces them:

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

Generated directories are git-ignored; they are retained for manual inspection and reproducibility.

## 7. Next SPEC Guidance

Best next direction:

- Improve crop merge column alignment and column-count consistency.
- Evaluate changes with runtime-observable signals only.
- Keep high fallback protection unless a new full 48-case evaluation proves a better strategy.

Avoid:

- Reintroducing the tried re-split strategies as runtime retry; they were net negative.
- Using GT/TEDS/case ID at runtime.
- Reusing baseline parse result as fallback.
- Cleaning retained artifacts blindly.

## 8. Service Notes

Latest MinerU service used for full evaluation:

```text
endpoint: http://127.0.0.1:8000/v1/chat/completions
model: MinerU-Pro
tmux session: mineru_8000
```

Temporary config used in prior runs:

```text
/tmp/table_agent_newmineru_aggressive.yaml
```

See `NEW_MINERU_EVAL_NOTES.md` for report-level details.
