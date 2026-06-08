# Table Agent Session Handoff

Date: 2026-06-08
Workspace: `/mnt/shared-storage-user/mineru2-shared/xiaojutao`
Repo: `/mnt/shared-storage-user/mineru2-shared/xiaojutao/Table-Agent`

## Key Decisions

- MinerU table recognition must use `mineru_vl_utils.MinerUClient`, matching `Agent_test/TableAgent/tools/ocr_table.py`; do not use raw OpenAI HTTP for MinerU table recognition.
- Qwen split review still uses the OpenAI-compatible HTTP client.
- MinerU endpoint in config remains `http://100.103.11.28:20000/v1/chat/completions`, but `MinerUTableClient` converts it to server URL `http://100.103.11.28:20000/` for `mineru_vl_utils`.
- Run MinerU-related recognition in `conda run -n mineru ...`.
- TEDS scoring currently works in the base Python environment because the `mineru` env lacks `lxml`.
- End-to-end runs use per-sample subprocess isolation. If a sample hangs in MinerU or network code, the parent process terminates that sample worker and writes a failed row instead of blocking the batch.

## Services

- MinerU-Pro: `100.103.11.28:20000`
- Qwen35-397B: `10.102.214.86:20000`
- Both service ports are `20000`.

## Completed Acceptance Items And Commits

- Item 1, project skeleton/config CLI: `76988fe Add project skeleton and config CLI`
- Item 2, vision client smoke: `fe1aa55 Add vision client smoke test`
- Item 3, full-image baseline collection: `7b4f5f0 Add full-image baseline collection`
- Item 4, vertical split candidate generation: `6233b57 Add vertical split candidate generation`
- Item 5, Qwen split review iteration: `fd68f4e Add Qwen split review iteration`
- Item 6, crop recognition workflow: `f6a6799 Add crop recognition workflow`
- Item 7, OTSL merge and agent parse result: `4e38051 Add OTSL merge and agent parse result`
- Item 8, end-to-end smoke runner: `4e3309e Add end-to-end smoke runner`
- Item 8 hardening, subprocess sample timeout: `52fd969 Harden end-to-end sample timeouts`

## Item 9 Status

Item 9 has now been run against the available large-table benchmark. The spec says 50 samples, but the configured benchmark file contains 48 non-empty records:

```bash
wc -l /mnt/shared-storage-user/mineru2-shared/xiaojutao/bench/fine_grained_bench/fine_grained_bench-large_table.jsonl
# 48
```

Clean Item 9 outputs:

- `outputs/e2e_50_eval.jsonl`: 48 run rows
- `outputs/e2e_50_eval.baseline.scored.jsonl`: 1 summary row + 48 scored rows
- `outputs/e2e_50_eval.agent.scored.jsonl`: 1 summary row + 48 scored rows
- `outputs/e2e_50_eval.summary.json`: aggregate summary

Summary values from `outputs/e2e_50_eval.summary.json`:

- count: 48
- baseline average TEDS: 0.059270436493675326
- agent average TEDS: 0.059270436493675326
- absolute improvement: 0.0
- relative improvement: 0.0
- success count: 3
- partial success count: 0
- failure count: 45
- average chunk count: 0.0625
- average split iterations: 0.1875

Interpretation: during this run, MinerU service calls mostly timed out. The experiment pipeline is reproducible and diagnosable, but the measured TEDS is dominated by service timeouts rather than algorithm quality.

## Reproduction Commands

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

## Current Code Changes Pending Commit

These changes belong to Item 9 and should be committed after final verification:

- `table_agent/evaluation.py`: summary helper for scored baseline/agent outputs.
- `table_agent/cli.py`: adds `summarize` CLI command.
- `README.md`: documents the full evaluation commands and notes the benchmark currently has 48 records.
- `SESSION_HANDOFF.md`: this handoff note.

## Important Run Artifacts

Ignored artifacts under `outputs/`, `raw_responses/`, and `crops/` are intentionally not committed.

Avoid using `outputs/e2e_50.jsonl` as the final result from this session. Earlier overlapping runs wrote to that file concurrently, leaving partial/corrupted lines. The clean final run is `outputs/e2e_50_eval.jsonl`.

## Next Todo

1. Run final code checks after this file is created.
2. Commit Item 9 code/docs with a message like `Add full evaluation summary`.
3. If better service availability is needed, rerun Item 9 with a longer `--sample-timeout` and a fresh output filename.
4. Consider adding resume/append mode later, but do not do that before committing Item 9 unless explicitly requested.
