# New MinerU Service Evaluation Notes

Date: 2026-06-09

## Service Routing

The faster MinerU service is running on the new worker and listens on
`127.0.0.1:8000` inside that worker. It did not receive requests sent to the old
Table-Agent config endpoint `http://100.103.11.28:20000/v1/chat/completions`.
For this evaluation, a temporary config was used:

```text
/tmp/table_agent_newmineru_local.yaml
mineru.endpoint: http://127.0.0.1:8000/v1/chat/completions
```

## Runner Fix

The first successful requests exposed a separate runner bug: completed workers
could hang while returning very large JSON rows through `multiprocessing.Queue`,
so the parent process did not write the row even after raw MinerU responses had
been saved. The runner now writes each worker row to `raw_responses/e2e_rows/`
and sends only the row path/status through the queue.

Commit: `192ac0c Write e2e worker rows through files`.

## Smoke Results

Baseline-only smoke on samples 12-14 succeeded quickly:

- sample 12: success, OTSL length 6300
- sample 13: success, OTSL length 12274
- sample 14: success, OTSL length 9908

End-to-end smoke after the row-file fix:

```text
outputs/e2e_newmineru_local_smoke3_rowfile.summary.json
count: 3
success_count: 3
failure_count: 0
baseline_avg_teds: 0.8340070694768965
agent_avg_teds: 0.8831227302526795
absolute_improvement: 0.049115660775783
```

## 10-Sample Result

```text
outputs/e2e_newmineru_local_10.summary.json
count: 10
success_count: 10
failure_count: 0
baseline_avg_teds: 0.8423279467486602
agent_avg_teds: 0.8636176388810446
absolute_improvement: 0.021289692132384408
relative_improvement: 0.025274825814056694
```

Largest improvement in the 10-sample run:

- `layout-PM0hLuYsE--Fna-V.block-PM0hLuYsE--Fna-W.jpg`: +0.4494079068848338 TEDS.

Largest regression in the 10-sample run:

- `layout-PM2BfTXPZk-HzvOH.block-PM2BfiXPZk-HzvPo.jpg`: -0.22605363984674332 TEDS.

## Interpretation

With the faster local MinerU service and the row-file runner fix, the pipeline
can produce successful end-to-end rows. The first 10 samples show a positive
average TEDS improvement, but some samples regress, so the full 48-record run is
needed before updating the final conclusion.


## Full 48-Record Result

The configured benchmark has 48 non-empty records. The first full run wrote 47
rows and the final missing record was rerun separately, then combined into a
clean 48-row file:

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

Largest improvements:

- `layout-PM0hLuYsE--Fna-V.block-PM0hLuYsE--Fna-W.jpg`: +0.4489005607592953 TEDS.
- `layout-PM9pCn_T---J0KCu.block-PM9pD2_T---J0KJX.jpg`: +0.3718225014186255 TEDS.
- `layout-PM8LAyXPZk-PFLhJ.block-PM8LBTXPZk-PFLn0.jpg`: +0.3457039508049349 TEDS.

Largest regressions:

- `layout-PM2BfTXPZk-HzvOH.block-PM2BfiXPZk-HzvPo.jpg`: -0.22605363984674332 TEDS.
- `layout-PMBhPTXPZk-D4CyR.block-PMBhPyXPZk-D4D0Q.jpg`: -0.18936737468561105 TEDS.
- `layout-PM2aGJmPE--9OlhN.block-PM2aGZmPE--9Olib.jpg`: -0.14605263157894732 TEDS.

Final interpretation for this rerun: with the faster local MinerU service and
the row-file runner fix, Table Agent improves average TEDS on the available
48-record large-table benchmark by about 0.029 absolute, or 3.38% relative. The
method is not uniformly better: regressions still happen, especially when split
chunks have inconsistent column counts or when a single-chunk result differs
from the baseline rerun.
