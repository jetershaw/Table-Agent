# Table Agent Project Map

Last updated: 2026-06-11

This file is a navigation map for future coding agents. It is not a requirements document. Use it to understand the project layers, entry points, current artifacts, and which files to read before starting the next SPEC task.

## 1. Where To Start

Start here, in this order:

1. `PROJECT_MAP.md`
   - This orientation file.
2. `THIRD_STAGE_OPTIMIZATION_SPEC.zh.md`
   - The active next-round SPEC.
   - The next task starts with acceptance item 1: offline diagnostics and retry/fallback candidate statistics.
3. `SPEC.zh.md`
   - Consolidated project spec and historical performance record.
   - Contains the current best 48-case result and prior completion history.
4. `utils/CLAUDE.md`
   - Local engineering rules: think first, keep changes surgical, verify each goal.
5. `configs/default.yaml`
   - Default service/config paths and current baseline runtime knobs.

Historical context only:

- `NEW_MINERU_EVAL_NOTES.md`
  - Older new-MinerU evaluation notes from before the aggressive policy result.
  - Useful for service routing and runner-fix history, but not the latest performance conclusion.

## 2. Current Best Result

Latest retained full-run artifacts are under `outputs/`:

- `outputs/e2e_aggressive_48.jsonl`
- `outputs/e2e_aggressive_48.baseline.scored.jsonl`
- `outputs/e2e_aggressive_48.agent.scored.jsonl`
- `outputs/e2e_aggressive_48.summary.json`

Current best summary:

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

Latest retained inspection artifacts:

- `crops/e2e_*.jpg`: latest crop images referenced by `outputs/e2e_aggressive_48.jsonl`.
- `raw_responses/e2e_baseline/*.json`: baseline full-image raw MinerU responses referenced by the latest run.
- `raw_responses/e2e_crops/*.json`: crop raw MinerU responses referenced by the latest run.

These artifacts are intentionally git-ignored but retained for manual inspection.

## 3. High-Level Architecture

Pipeline flow:

```text
benchmark row
  -> baseline full-image MinerU recognition
  -> CV vertical split proposal
  -> Qwen split/no-split review
  -> crop image saving
  -> MinerU crop recognition
  -> OTSL repair/merge
  -> HTML conversion
  -> agent_parse_result + metadata
  -> offline TEDS scoring and summary
```

Important boundary:

- Runtime agent must not use GT `solution`, TEDS/TEDS-S, case-id white/blacklists, or baseline parse result fallback.
- Offline diagnostics and final evaluation may use GT/TEDS.
- Fallback in the third-stage SPEC, if implemented, must call MinerU full-image recognition again from the agent path. It must not reuse `baseline_parse_result`.

## 4. CLI Entry Points

Main CLI file:

- `table_agent/cli.py`

Commands:

- `python -m table_agent.cli config`
  - Load and print normalized config.
- `python -m table_agent.cli smoke`
  - Call MinerU/Qwen on one image.
- `python -m table_agent.cli baseline`
  - Collect full-image MinerU baseline results.
- `python -m table_agent.cli split`
  - Generate CV split candidates and save crops.
- `python -m table_agent.cli split-review`
  - Ask Qwen to review/revise split candidates.
- `python -m table_agent.cli crop-recognize`
  - Run MinerU on reviewed crops.
- `python -m table_agent.cli merge`
  - Merge crop OTSL outputs and convert to HTML.
- `python -m table_agent.cli run`
  - End-to-end baseline + agent runner.
- `python -m table_agent.cli summarize`
  - Summarize scored baseline/agent JSONL files.
- `python -m table_agent.cli diagnose`
  - Build offline case-level diagnostics.

## 5. Module Map

### Configuration

- `table_agent/config.py`
  - Dataclasses for service/path/agent config.
  - Validates `image_input_mode` and `split_review_policy`.
  - Current allowed split policies: `conservative`, `aggressive`.

### Data and image IO

- `table_agent/benchmark.py`
  - Iterates benchmark JSONL records.
  - Resolves image paths from benchmark rows.
- `table_agent/image_io.py`
  - Image encoding/loading helpers.

### Service clients

- `table_agent/client.py`
  - Generic OpenAI-compatible vision client, used for Qwen.
- `table_agent/mineru_client.py`
  - MinerU table-recognition client wrapper.
- `table_agent/baseline.py`
  - Full-image MinerU baseline collection.
  - Also exposes JSON writing helper used by runner.

### Split proposal and review

- `table_agent/splitter.py`
  - CV heuristic split proposal.
  - Chooses chunk count by image height and `max_chunks`.
  - Uses horizontal ink/gradient density to pick safer cut bands.
  - Saves crops to `config.paths.crop_dir`.
- `table_agent/split_review.py`
  - Qwen split/no-split review.
  - Builds conservative/aggressive prompts.
  - Returns `split_decision` metadata with `should_split`, `complexity`, `risk_factors`, `cuts`, `reason`.
  - Validates cuts and rejects tiny chunks.

### Recognition and merge

- `table_agent/recognition.py`
  - Runs MinerU recognition on each crop, with retry count from config.
- `table_agent/otsl.py`
  - OTSL utilities: validation, row splitting, shape estimation, conversion to HTML.
  - Contains `repair_stray_otsl_angles` for text `<` that is not an OTSL token.
  - `merge_vertical_otsl` merges crop OTSL rows and emits warnings such as `empty_crop_otsl`, `illegal_otsl_tokens`, `column_count_inconsistent`.
- `table_agent/merge.py`
  - CLI-oriented merge wrapper for crop recognition output.

### End-to-end runner

- `table_agent/runner.py`
  - Main batch runner used by `python -m table_agent.cli run`.
  - Per sample:
    1. Runs `_run_baseline`.
    2. Runs `_run_agent`.
    3. Writes row through `raw_responses/e2e_rows/` to avoid multiprocessing queue hangs on large JSON.
  - `_run_agent` is the likely integration point for third-stage retry/fallback metadata and behavior.

### Evaluation and diagnostics

- `table_agent/evaluation.py`
  - Reads run JSONL plus scored baseline/agent JSONL.
  - Produces aggregate summary with averages, status counts, most improved, most regressed.
- `table_agent/diagnostics.py`
  - Offline diagnostic report for scored runs.
  - Builds case-level rows with TEDS deltas, warnings, crop row/col estimates, chunk statuses.
  - Good starting point for third-stage acceptance item 1.

## 6. Third-Stage Task Pointers

Active SPEC:

- `THIRD_STAGE_OPTIMIZATION_SPEC.zh.md`

Next acceptance item:

- Acceptance item 1: third-stage offline diagnostics and retry/fallback candidate case statistics.

Likely files to read first for acceptance item 1:

- `table_agent/diagnostics.py`
- `table_agent/evaluation.py`
- `table_agent/runner.py`
- `table_agent/otsl.py`
- `outputs/e2e_aggressive_48.summary.json`
- `outputs/e2e_aggressive_48.jsonl`
- `outputs/e2e_aggressive_48.baseline.scored.jsonl`
- `outputs/e2e_aggressive_48.agent.scored.jsonl`

Likely first implementation path:

1. Extend or add an offline diagnostic helper. Do not touch runtime yet.
2. Use only runtime-observable signals for candidate labels:
   - warnings
   - chunk count
   - split decision
   - crop row/column estimates
   - crop statuses
   - merged OTSL/HTML structural signals
3. Use TEDS/GT-derived scores only to evaluate whether those labels are useful.
4. Write a report/artifact under `outputs/` or a small tracked `.md` report if useful.
5. Commit after the acceptance item passes.

Do not start with retry/fallback runtime code until acceptance item 1 is complete.

## 7. Service And Runtime Notes

MinerU service used for the latest full run:

```bash
cd /
ssh -CAXY ws-15667b3f02c1236f-worker-v6gjp.xiaojutao+root.ailab-sciversealign.pod@h.pjlab.org.cn -i id_rsa
```

Inside that worker, the fast MinerU endpoint was:

```text
http://127.0.0.1:8000/v1/chat/completions
```

The service was started in tmux session `mineru_8000` with `utils/mineru_server.sh`.

Local temporary config used in prior runs:

```text
/tmp/table_agent_newmineru_aggressive.yaml
```

This temp config is not checked in. It set the MinerU endpoint to local `127.0.0.1:8000` and `split_review_policy: aggressive`.

TEDS scoring command pattern:

```bash
python /mnt/shared-storage-user/mineru2-shared/xiaojutao/utils/score_teds_jsonl.py \
  --input-jsonl outputs/<run>.jsonl \
  --output-jsonl outputs/<run>.agent.scored.jsonl \
  --pred-field agent_parse_result \
  --gt-field solution
```

Large-table TEDS scoring can be slow. A previous full-batch scoring attempt failed without writing output because `score_teds_jsonl.py` accumulates rows in memory and writes at the end. For robust full scoring, score per row and merge if needed.

## 8. Git And Artifact Policy

Tracked source/spec files should be committed after each acceptance item.

Ignored/generated artifacts:

- `outputs/*`
- `crops/*`
- `raw_responses/*`

The current retained artifacts are for manual inspection. Avoid deleting them unless the user explicitly asks or a cleanup acceptance item requires it.

Current workflow rule:

- One acceptance item at a time.
- Verify it.
- Commit it.
- If later work breaks, revert at most one small commit.

## 9. Common Pitfalls

- Do not use `baseline_parse_result` as runtime fallback.
- Do not use GT/TEDS in runtime decisions.
- Do not hard-code case IDs from diagnostics into runtime logic.
- Do not assume `NEW_MINERU_EVAL_NOTES.md` is the latest result; it is older history.
- Do not clean `outputs/`, `crops/`, or `raw_responses/` blindly; latest retained artifacts are useful for inspection.
- Be careful with full 48-row TEDS scoring; per-row scoring may be safer.
- Match existing module style and keep changes surgical.
