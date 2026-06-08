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

