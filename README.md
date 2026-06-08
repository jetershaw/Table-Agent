# Table Agent

Table Agent experiments with vertical splitting for very large table images,
crop-level MinerU recognition, OTSL merging, and TEDS comparison against a
full-image MinerU baseline.

## Project Structure

- `configs/`: YAML configuration.
- `table_agent/`: Python package for config, clients, splitting, recognition,
  merging, and batch execution.
- `outputs/`: JSONL outputs and summaries.
- `raw_responses/`: saved model responses for debugging.
- `crops/`: generated crop images.

## Config Check

```bash
python -m table_agent.cli config --config configs/default.yaml
```

## Final Report

The staged acceptance work and the 50-sample evaluation result are summarized in
`FINAL_REPORT.md`.

## 50-Sample Evaluation

The current large-table benchmark file contains 48 non-empty records. The
`--limit 50` command below therefore runs the full available set.

```bash
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
