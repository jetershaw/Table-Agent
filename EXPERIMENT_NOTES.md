# Table Agent Follow-up Experiment Notes

Date: 2026-06-09

## Goal

Run two small follow-up checks after the 48-sample evaluation produced too few
successful rows:

1. Let one previously timed-out sample wait much longer to see whether MinerU can
   eventually return a result.
2. Try a conservative split-review prompt improvement and check whether it can
   improve the result on a small sample.

## Runs

### Long-wait sample

Command:

```bash
conda run -n mineru python -m table_agent.cli run \
  --config configs/default.yaml \
  --start 0 \
  --limit 1 \
  --output-jsonl outputs/e2e_longwait_sample0.jsonl \
  --sample-timeout 1800
```

Result: no JSONL row was produced after roughly 30 minutes. The run was skipped
as non-productive. This suggests the 60-second failures were not only a short
local timeout; at least this sample can remain blocked for a very long time in
MinerU/network execution.

### Prompt before/after sample

Sample index 12 was selected because the previous full evaluation had succeeded
on it. During this follow-up, both before and after runs timed out at 600 seconds:

- `outputs/e2e_prompt_before_sample12.summary.json`: baseline TEDS 0.0, agent TEDS 0.0, failed with `sample timed out after 600s`.
- `outputs/e2e_prompt_after_sample12.summary.json`: baseline TEDS 0.0, agent TEDS 0.0, failed with `sample timed out after 600s`.

A Qwen-only split-review check after the prompt change completed successfully:

```bash
python -m table_agent.cli split-review \
  --config configs/default.yaml \
  --start 12 \
  --limit 1 \
  --output-json outputs/split_review_prompt_after_sample12.json
```

For this image, the proposed cuts were already empty because the image height is
827 pixels, below the default 1200-pixel target chunk height. Qwen accepted the
single full-image chunk in one iteration.

## Prompt Change

`table_agent/split_review.py` now asks Qwen to prefer fewer, safer chunks, move
unsafe cuts only to nearby clear whitespace bands, and remove unsafe cuts when no
safe nearby band is visible. The intent is to reduce harmful over-splitting when
MinerU service availability allows a real end-to-end comparison.

## Interpretation

This follow-up did not demonstrate a TEDS improvement. The main blocker is still
MinerU service availability or very long request latency: even a previously
successful sample timed out at 600 seconds during this session. The prompt change
is conservative and low-risk, but its quality impact should be measured again
when MinerU returns stable results.
