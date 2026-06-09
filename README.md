# Table Agent

Table Agent experiments with vertical splitting for very large table images,
crop-level MinerU recognition, OTSL merging, and TEDS comparison against a
full-image MinerU baseline.

## Project Structure

- `configs/`: YAML configuration.
- `table_agent/`: Python package for config, clients, splitting, recognition,
  merging, and batch execution.
- `outputs/`: ignored JSONL outputs and summaries.
- `raw_responses/`: ignored saved model responses and worker row files for debugging.
- `crops/`: ignored generated crop images.

## Important Docs

- `SPEC.md` / `SPEC.zh.md`: original staged acceptance spec.
- `NEW_MINERU_EVAL_NOTES.md`: latest reliable evaluation using the faster local MinerU service.
- `SESSION_HANDOFF.md`: current handoff summary for the next work session.

## Config Check

```bash
python -m table_agent.cli config --config configs/default.yaml
```

## Latest Evaluation

The latest useful evaluation used a faster MinerU service reachable from its
worker at `http://127.0.0.1:8000/v1/chat/completions` via a temporary config.
See `NEW_MINERU_EVAL_NOTES.md` for exact commands, artifacts, and interpretation.

Full 48-record result from that rerun:

```text
success_count: 48
failure_count: 0
baseline_avg_teds: 0.8634187595356039
agent_avg_teds: 0.8926355322939662
absolute_improvement: 0.02921677275836232
relative_improvement: 0.03383847343562094
```
