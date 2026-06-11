# 第三阶段验收项 5：runtime retry-then-fallback 接入

日期：2026-06-11

## 目标

将验收项 4 验证有效的 fallback 策略接入 agent runtime。fallback 必须由 agent 重新调用 MinerU 整图识别，不复用 baseline parse result。

验收项 2 未找到净收益为正的 re-split retry 策略，因此本次 runtime 保留 retry metadata，但 retry 不启用：`retry_triggered=false`、`retry_attempts=0`。fallback 作为严重异常保护路径接入。

## 触发条件

运行时只使用无 GT 可观测信号：

- merge warning 包含 `column_count_inconsistent`
- 非零 crop estimated column count 的 spread `>= 4`

触发原因写为：`severe_col_count_spread:<spread>`。

## Runtime metadata

新增/写入字段：

- `retry_triggered`
- `retry_reason`
- `retry_strategy`
- `retry_attempts`
- `fallback_triggered`
- `fallback_reason`
- `fallback_raw_response.path`
- `fallback_elapsed_seconds`
- `selected_result_source`
- `extra_mineru_calls`
- `extra_qwen_calls`

fallback raw response 路径：`raw_responses/e2e_fallback/<index>.json`。

## 验证命令

语法检查：

```bash
python -m py_compile table_agent/runner.py
```

真实 runtime smoke：

```bash
python -m table_agent.cli run --config configs/default.yaml --start 46 --limit 1 \
  --output-jsonl outputs/e2e_fallback_smoke_46.jsonl --sample-timeout 180
python -m table_agent.cli run --config configs/default.yaml --start 11 --limit 1 \
  --output-jsonl outputs/e2e_fallback_smoke_11.jsonl --sample-timeout 180
python -m table_agent.cli run --config configs/default.yaml --start 39 --limit 1 \
  --output-jsonl outputs/e2e_fallback_smoke_39.jsonl --sample-timeout 180
```

当前服务重跑这三条时没有复现历史 `column_count_inconsistent` severe spread，因此真实 smoke 均走正常 `split_merge`，没有误触发 fallback：

| index | status | fallback_triggered | selected_result_source | warnings | crop_col_counts |
| ---: | --- | --- | --- | --- | --- |
| 11 | success | false | split_merge | [] | [0, 0] |
| 39 | success | false | split_merge | [] | [0] |
| 46 | success | false | split_merge | [] | [0, 0] |

触发 helper 检查：

```bash
python - <<'PY'
from table_agent.runner import _fallback_reasons
assert _fallback_reasons(['column_count_inconsistent:[36, 29]'], [36, 29]) == ['severe_col_count_spread:7']
assert _fallback_reasons(['column_count_inconsistent:[25, 23]'], [25, 23]) == []
assert _fallback_reasons([], [36, 29]) == []
PY
```

runtime fallback 分支 smoke：通过 monkeypatch `_run_agent` 的 split/recognition/merge 依赖，强制 merge 输出 `column_count_inconsistent:[36, 29]`，fake MinerU full-image 返回 fallback OTSL，断言：

- `fallback_triggered is True`
- `fallback_reason == ['severe_col_count_spread:7']`
- `selected_result_source == 'fallback_full_image'`
- `extra_mineru_calls == 1`
- final `agent_parse_result` 使用 fallback OTSL
- `fallback_raw_response.path` 写入 fallback raw 路径

## 结论

runtime fallback 已接入，默认路径不增加额外调用；仅严重 column-count spread 异常触发 1 次额外 MinerU 整图识别。真实 smoke 跑通且未误触发；强制触发分支 smoke 验证了 fallback metadata 和最终结果选择。

## 验收项 6 后阈值更新

成本档位实验显示 `high` 档位均分最高，最终 runtime 阈值从 `col spread >= 4` 调整为 `col spread >= 3`。该阈值仍然只依赖运行时可观测信号：`column_count_inconsistent` warning 和 crop estimated column count spread。
