# Table Agent Session Handoff

Date: 2026-06-09
Workspace: `/mnt/shared-storage-user/mineru2-shared/xiaojutao`
Repo: `/mnt/shared-storage-user/mineru2-shared/xiaojutao/Table-Agent`

## Current Status

- Staged acceptance items in `SPEC.md` / `SPEC.zh.md` are complete.
- Latest useful evaluation is documented in `NEW_MINERU_EVAL_NOTES.md`.
- The faster MinerU service was tested from the worker where it listens on `127.0.0.1:8000`.
- The old configured endpoint `http://100.103.11.28:20000/v1/chat/completions` did not hit that faster local service during the rerun.

## Important Decisions

- MinerU recognition uses `mineru_vl_utils.MinerUClient`; do not replace it with raw OpenAI HTTP unless intentionally changing the architecture.
- Qwen split review uses the OpenAI-compatible HTTP client.
- MinerU-related runs should use `conda run -n mineru ...`.
- TEDS scoring currently works in the base Python environment because the `mineru` env lacks `lxml`.
- End-to-end workers now write large rows through `raw_responses/e2e_rows/` and send only row paths through multiprocessing. This avoids hangs when returning large JSON rows.

## Key Commits

- `76988fe` project skeleton and config CLI.
- `fe1aa55` vision client smoke test.
- `7b4f5f0` full-image baseline collection.
- `6233b57` vertical split candidate generation.
- `fd68f4e` Qwen split review iteration.
- `f6a6799` crop recognition workflow.
- `4e38051` OTSL merge and agent parse result.
- `4e3309e` end-to-end smoke runner.
- `52fd969` subprocess sample timeout hardening.
- `f441b26` full evaluation summary tooling.
- `bf0705c` conservative split-review prompt tuning.
- `192ac0c` row-file worker result handoff fix.
- `7e39a1b` new MinerU evaluation notes.

## Latest Results

Clean 48-row rerun artifacts:

- `outputs/e2e_newmineru_local_48_combined.jsonl`
- `outputs/e2e_newmineru_local_48_combined.baseline.scored.jsonl`
- `outputs/e2e_newmineru_local_48_combined.agent.scored.jsonl`
- `outputs/e2e_newmineru_local_48_combined.summary.json`

Summary:

```text
count: 48
success_count: 48
partial_success_count: 0
failure_count: 0
baseline_avg_teds: 0.8634187595356039
agent_avg_teds: 0.8926355322939662
absolute_improvement: 0.02921677275836232
relative_improvement: 0.03383847343562094
avg_chunk_count: 1.4583333333333333
avg_split_iterations: 1.0
```

Interpretation: with the faster local MinerU service and the row-file runner fix,
Table Agent improves average TEDS on the available 48-record large-table benchmark
by about 0.029 absolute, or 3.38% relative. Some regressions remain, especially
where split chunks have inconsistent column counts.

## Next Useful Work

1. Decide whether to make the faster MinerU endpoint configurable as a checked-in config variant, or keep it as an operator-local temporary config.
2. Investigate regressions listed in `NEW_MINERU_EVAL_NOTES.md`, especially column-count inconsistency cases.
3. Consider a fallback policy: if review produces one chunk, reuse baseline result instead of rerunning the same image through the agent path.
