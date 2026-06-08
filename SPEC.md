# Table Agent Spec

## 1. Project Goal

Build a Table Agent for very large table images.

The agent should split long table images vertically, run MinerU2.5-Pro table recognition on each crop, merge the crop-level OTSL outputs, convert the merged OTSL to HTML, and compare TEDS against the direct full-image MinerU2.5-Pro baseline.

The core experiment is:

> Does vertical splitting plus crop recognition plus OTSL merging improve TEDS over direct full-image recognition?

## 2. Project Location

All new project files should live under:

```text
/mnt/shared-storage-user/mineru2-shared/xiaojutao/Table-Agent
```

Existing repo utilities may be reused, especially:

```text
/mnt/shared-storage-user/mineru2-shared/xiaojutao/utils/otsl2html.py
/mnt/shared-storage-user/mineru2-shared/xiaojutao/utils/score_teds_jsonl.py
```

## 3. Data

Benchmark JSONL:

```text
/mnt/shared-storage-user/mineru2-shared/xiaojutao/bench/fine_grained_bench/fine_grained_bench-large_table.jsonl
```

Default image directory:

```text
/mnt/shared-storage-user/mineru2-shared/xiaojutao/bench/fine_grained_bench/images
```

Each record contains at least:

```json
{
  "image": "xxx.jpg",
  "solution": "<table>...</table>",
  "tag": "large_table"
}
```

The `solution` field is ground truth HTML. It must only be used for final scoring. It must not be visible to the agent during splitting, recognition, retry, or merging.

## 4. Model Services

Two model services will be deployed with vLLM and exposed as OpenAI-compatible HTTP APIs:

- MinerU2.5-Pro table recognition service
- Qwen3.5-397B VLM/LLM decision service

Default API shape:

```text
POST http://<host>:<port>/v1/chat/completions
```

Request format:

```json
{
  "model": "...",
  "messages": [...]
}
```

MinerU table recognition prompt:

```text
Table Recognition: xxx
```

The table recognition output is expected to contain OTSL.

## 5. Image Input Mode

Base64 image input is confirmed to be supported and should be the default reliable mode.

The implementation should still keep image input mode configurable:

```yaml
image_input_mode: base64
```

Optional future modes:

```yaml
image_input_mode: file_url
image_input_mode: path
```

The first smoke test should verify the actual MinerU and Qwen message format once service IPs are available. If path or file URL also works, it can be enabled later for performance. First version should not depend on path support.

## 6. Output Fields

The batch output JSONL should preserve all original benchmark fields and add:

```json
{
  "baseline_parse_result": {
    "status": "success",
    "otsl": "...",
    "html": "...",
    "raw_response": {}
  },
  "agent_parse_result": {
    "status": "success",
    "otsl": "...",
    "html": "..."
  },
  "agent_metadata": {
    "image_path": "...",
    "image_size": [1000, 8000],
    "split_iterations": 1,
    "max_split_iterations": 3,
    "max_recognition_retries": 2,
    "max_chunks": 12,
    "chunks": [
      {
        "index": 0,
        "box": [0, 0, 1000, 1200],
        "crop_path": "...",
        "status": "success",
        "row_count": 20,
        "estimated_col_count": 6
      }
    ],
    "warnings": []
  }
}
```

Scoring should be possible with:

```bash
python /mnt/shared-storage-user/mineru2-shared/xiaojutao/utils/score_teds_jsonl.py \
  --input-jsonl OUTPUT.jsonl \
  --output-jsonl OUTPUT.baseline.scored.jsonl \
  --pred-field baseline_parse_result \
  --gt-field solution
```

and:

```bash
python /mnt/shared-storage-user/mineru2-shared/xiaojutao/utils/score_teds_jsonl.py \
  --input-jsonl OUTPUT.jsonl \
  --output-jsonl OUTPUT.agent.scored.jsonl \
  --pred-field agent_parse_result \
  --gt-field solution
```

## 7. Agent Workflow

The first version only supports vertical splitting.

Workflow:

1. Read benchmark records.
2. Resolve each image path.
3. Run full-image MinerU recognition to produce `baseline_parse_result`.
4. Generate vertical split candidates.
5. Use computer vision heuristics to prefer safer horizontal cut positions.
6. Ask Qwen3.5-397B VLM to inspect and revise split positions.
7. Iterate split revision up to the configured limit.
8. Crop image chunks.
9. Run MinerU recognition on each crop.
10. Parse and lightly validate each crop OTSL.
11. Merge crop OTSL in vertical order.
12. Convert merged OTSL to HTML.
13. Write output JSONL.
14. Run TEDS scoring outside the agent.

## 8. Splitting Strategy

The first implementation should use a conservative vertical split strategy:

- Keep full table width for every crop.
- Split only along the y-axis.
- Do not use overlap.
- Do not intentionally cut merged cells.
- Do not copy the table header into every crop in the first version.

The CV candidate generator should not rely only on visible table lines.

For ruled tables, it may use:

- horizontal line response
- row boundary signals
- edge density

For borderless or weak-line tables, it may use:

- blank horizontal bands
- text/pixel density valleys
- projection statistics

For light or inconsistent line colors, it should degrade gracefully to density-based candidates.

The VLM reviewer should check whether split positions visually cut through text, rows, cells, or obvious merged cells.

## 9. OTSL Handling

OTSL tokens:

- `<fcel>`: filled cell
- `<ecel>`: empty cell
- `<lcel>`: merged from left, colspan
- `<ucel>`: merged from above, rowspan
- `<xcel>`: merged from left and above, 2D span
- `<nl>`: end of row

The first version should implement tolerant vertical OTSL merging:

- Split each OTSL into rows by `<nl>`.
- Preserve crop order.
- Concatenate rows from all crops.
- Validate token legality.
- Estimate row count and column count for metadata.
- Allow mild column-count inconsistency.
- Prefer conservative cleanup over aggressive repair.

The first version does not need perfect recovery of rowspan or colspan that crosses a crop boundary.

## 10. Limits

Default limits:

```yaml
max_split_iterations: 3
max_recognition_retries: 2
max_chunks: 12
```

If a limit is reached:

- Stop further retries or split revisions.
- Use the current best available result.
- Record the condition in `agent_metadata.warnings`.

If one crop fails:

- Do not crash the whole batch.
- Mark the crop failed.
- Mark the sample as `partial_success` when possible.
- Preserve enough metadata for diagnosis.

## 11. Project Scope

In scope:

- OpenAI-compatible HTTP client for vLLM services.
- Base64 image message support.
- MinerU table recognition client.
- Qwen3.5-397B split-review client.
- Vertical split candidate generation.
- Crop generation and saving.
- OTSL parsing, validation, tolerant merging.
- OTSL to HTML conversion integration.
- Batch runner for benchmark JSONL.
- Baseline full-image recognition collection.
- Agent split-recognition result collection.
- TEDS scoring commands or wrapper script.
- Metadata and diagnostics output.
- Smoke test on 3-5 samples.
- Full run on 50 large-table samples.

## 12. Out Of Scope

The first version will not implement:

- Horizontal splitting.
- 2D grid splitting.
- Cross-page table handling.
- Table region detection.
- Header copying into every crop.
- Duplicate header removal.
- Complex rowspan/colspan recovery across crop boundaries.
- Using GT HTML during agent decisions.
- TEDS scoring as an agent tool.
- Model training or fine-tuning.
- Multi-model ensemble.
- Per-sample handcrafted fixes.
- Aggressive OTSL hallucination repair.

## 13. Acceptance Items

Development should proceed one acceptance item at a time.

After each acceptance item is implemented and verified, create a git commit before starting the next item. This keeps rollback small if a later step breaks behavior.

### Acceptance Item 1: Project Skeleton And Configuration

Pass criteria:

- `Table-Agent` has a clear project structure.
- Config file supports:
  - MinerU endpoint
  - Qwen endpoint
  - model names
  - image input mode
  - max split iterations
  - max recognition retries
  - max chunks
  - input/output paths
- No model call is required yet.
- A basic CLI can load and print validated config.

Commit after passing.

### Acceptance Item 2: OpenAI-Compatible Vision Client Smoke Test

Pass criteria:

- Client can send base64 image messages.
- Client can call MinerU service with `Table Recognition: xxx`.
- Client can call Qwen service with a simple visual inspection prompt.
- Raw responses are saved for debugging.
- If service IPs are not available, this item remains blocked rather than mocked as passed.

Commit after passing.

### Acceptance Item 3: Full-Image Baseline Collection

Pass criteria:

- Batch script reads benchmark JSONL.
- Resolves image paths.
- Calls MinerU on full images.
- Writes `baseline_parse_result`.
- Converts baseline OTSL to HTML when possible.
- Supports `--start`, `--end`, and `--limit`.
- Runs successfully on 3-5 samples.

Commit after passing.

### Acceptance Item 4: Vertical Split Candidate Generation

Pass criteria:

- Tool loads a large image and proposes vertical crop boxes.
- Number of chunks respects `max_chunks`.
- Candidate cuts use image statistics and do not depend only on table lines.
- Crop images are saved.
- Metadata records image size and crop boxes.
- Runs locally without model calls.

Commit after passing.

### Acceptance Item 5: VLM Split Review And Iteration

Pass criteria:

- Qwen reviews proposed split positions.
- Qwen can return accepted or revised y coordinates.
- Split revision stops at `max_split_iterations`.
- Invalid model responses are handled safely.
- Metadata records iteration count and warnings.
- Runs on 3-5 samples.

Commit after passing.

### Acceptance Item 6: Crop Recognition

Pass criteria:

- Each crop is sent to MinerU.
- Each crop result stores OTSL and raw response.
- Per-crop retry respects `max_recognition_retries`.
- Failed crops do not crash the full sample.
- Metadata records crop status.

Commit after passing.

### Acceptance Item 7: OTSL Merge And HTML Conversion

Pass criteria:

- Crop OTSL strings are parsed into rows.
- Rows are merged in vertical crop order.
- Token legality is checked.
- Mild column-count inconsistency is tolerated.
- Merged OTSL is converted to HTML with existing utility.
- Output writes `agent_parse_result`.

Commit after passing.

### Acceptance Item 8: End-To-End Smoke Test

Pass criteria:

- Run 3-5 benchmark samples end to end.
- Output contains:
  - `baseline_parse_result`
  - `agent_parse_result`
  - `agent_metadata`
- Agent does not read or use `solution` except when scoring is run separately.
- No sample-level failure crashes the whole run.
- TEDS scoring works for baseline and agent fields.

Commit after passing.

### Acceptance Item 9: Full 50-Sample Evaluation

Pass criteria:

- Run all 50 large-table samples.
- Produce baseline scored JSONL.
- Produce agent scored JSONL.
- Produce summary with:
  - baseline average TEDS
  - agent average TEDS
  - absolute improvement
  - relative improvement
  - success count
  - partial success count
  - failure count
  - average chunk count
  - average split iterations
- List the most improved and most regressed samples for analysis.

Commit after passing.

## 14. Overall Acceptance

The project is accepted when:

- All acceptance items are complete.
- Every item has a corresponding git commit.
- The full 50-sample evaluation is reproducible from documented commands.
- Results are stored in JSONL files.
- The final report clearly states whether Table Agent improves TEDS over the MinerU2.5-Pro full-image baseline.

First-stage success does not require a positive TEDS improvement. It requires a faithful, reproducible, diagnosable experiment. A positive improvement is the experimental result being measured.

