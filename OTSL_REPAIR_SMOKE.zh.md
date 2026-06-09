# OTSL 后处理 Smoke 记录

日期：2026-06-09

对应验收项：`PERFORMANCE_IMPROVEMENT_SPEC.zh.md` 验收项 6。

## 1. 改动范围

本验收项新增一个轻量 OTSL 修复：`repair_stray_otsl_angles`。

目标 pattern：单元格文本中包含裸 `<`，例如 case 11 的表头文本：

```text
% FINES <#200 (%)
```

在 OTSL 中这会被原有 `validate_otsl_tokens` 误识别成非法 token：

```text
illegal_otsl_tokens: ['<#200 (%)<fcel>']
```

修复策略：

- 只在文本看起来像 OTSL 时运行。
- 合法 OTSL token 保持不变：`<fcel>`、`<ecel>`、`<lcel>`、`<ucel>`、`<xcel>`、`<nl>`。
- 其他裸 `<` 转义为 `&lt;`。
- 如果发生修复，新增 warning：`repaired_stray_otsl_angle:<crop_index>`。

该修复不读取 GT/TEDS，也不使用 baseline fallback。

## 2. 验证命令

单元级验证：

```bash
python -c 'from table_agent.otsl import repair_stray_otsl_angles, validate_otsl_tokens; s="<fcel>% FINES <#200 (%)<fcel>PLAST<nl>"; fixed=repair_stray_otsl_angles(s); print(fixed); print(validate_otsl_tokens(fixed))'
```

输出：

```text
<fcel>% FINES &lt;#200 (%)<fcel>PLAST<nl>
[]
```

端到端 smoke：

```bash
conda run -n mineru python -m table_agent.cli run   --config /tmp/table_agent_newmineru_aggressive.yaml   --start 11   --limit 1   --output-jsonl outputs/e2e_otsl_repair_smoke_11.jsonl   --sample-timeout 600
```

评分与汇总：

```bash
python /mnt/shared-storage-user/mineru2-shared/xiaojutao/utils/score_teds_jsonl.py   --input-jsonl outputs/e2e_otsl_repair_smoke_11.jsonl   --output-jsonl outputs/e2e_otsl_repair_smoke_11.baseline.scored.jsonl   --pred-field baseline_parse_result   --gt-field solution

python /mnt/shared-storage-user/mineru2-shared/xiaojutao/utils/score_teds_jsonl.py   --input-jsonl outputs/e2e_otsl_repair_smoke_11.jsonl   --output-jsonl outputs/e2e_otsl_repair_smoke_11.agent.scored.jsonl   --pred-field agent_parse_result   --gt-field solution

python -m table_agent.cli summarize   --run-jsonl outputs/e2e_otsl_repair_smoke_11.jsonl   --baseline-scored-jsonl outputs/e2e_otsl_repair_smoke_11.baseline.scored.jsonl   --agent-scored-jsonl outputs/e2e_otsl_repair_smoke_11.agent.scored.jsonl   --output-json outputs/e2e_otsl_repair_smoke_11.summary.json   --top-k 1
```

## 3. 结果

Smoke case：benchmark index 11，`layout-PM2aGJmPE--9OlhN.block-PM2aGZmPE--9Olib.jpg`。

端到端运行结果：

```text
total: 1
success: 1
partial_success: 0
failed: 0
```

TEDS 汇总：

```text
baseline_avg_teds: 0.9167916461149543
agent_avg_teds: 0.770739014536007
absolute_improvement: -0.14605263157894732
```

Warnings 变化：

| before | after |
|---|---|
| `illegal_otsl_tokens: ['<#200 (%)<fcel>']` | `repaired_stray_otsl_angle:0` |
| `column_count_inconsistent:[21, 17]` | `column_count_inconsistent:[21, 17]` |

## 4. 解释

本次后处理成功处理了一个明确 pattern：单元格文本中的裸 `<` 不再污染 OTSL token 校验。

但是 case 11 的 TEDS 没有变化，说明该 case 的主要损失不是非法 `<` 本身，而是仍然存在的列数不一致：`column_count_inconsistent:[21, 17]`。

这符合验收项 2 的归因：非法 token 是可检测的结构卫生问题，但 case 11 的主要质量问题更可能来自 crop 识别列缺失、切分上下文不足，或需要更强的列结构对齐策略。

## 5. 结论

验收项 6 smoke 跑通，并处理了至少一种明确 pattern：非法 OTSL token。

该修复应保留，因为它降低了 OTSL 结构噪声且不增加模型调用成本；但它不是 case 11 的充分修复。后续如果继续优化，应针对 `column_count_inconsistent` 设计更强的 guard 或列结构修正策略。
