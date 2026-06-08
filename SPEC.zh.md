# Table Agent 规格说明

## 1. 项目目标

构建一个用于超大尺寸、超长表格图片识别的 Table Agent。

Agent 需要对长表格图片进行纵向切分，分别调用 MinerU2.5-Pro 表格识别服务识别每个切片，得到多个 OTSL 结果后进行拼接，再将拼接后的 OTSL 转换为 HTML，最后用 TEDS 与 GT HTML 评分，并和整图直接识别的 MinerU2.5-Pro baseline 对比。

核心实验问题是：

> 纵向切分 + 子图识别 + OTSL 拼接，是否能比 MinerU2.5-Pro 整图直接识别获得更高的 TEDS？

## 2. 项目位置

所有新项目文件放在：

```text
/mnt/shared-storage-user/mineru2-shared/xiaojutao/Table-Agent
```

可以复用现有工具，尤其是：

```text
/mnt/shared-storage-user/mineru2-shared/xiaojutao/utils/otsl2html.py
/mnt/shared-storage-user/mineru2-shared/xiaojutao/utils/score_teds_jsonl.py
```

## 3. 数据

Benchmark JSONL：

```text
/mnt/shared-storage-user/mineru2-shared/xiaojutao/bench/fine_grained_bench/fine_grained_bench-large_table.jsonl
```

默认图片目录：

```text
/mnt/shared-storage-user/mineru2-shared/xiaojutao/bench/fine_grained_bench/images
```

每条数据至少包含：

```json
{
  "image": "xxx.jpg",
  "solution": "<table>...</table>",
  "tag": "large_table"
}
```

`solution` 字段是 GT HTML。它只能用于最终评分，不能在 Agent 的切分、识别、重试、拼接过程中被读取或使用。

## 4. 模型服务

两个模型服务都通过 vLLM 部署，并以 OpenAI-compatible HTTP API 暴露：

- MinerU2.5-Pro 表格识别服务
- Qwen3.5-397B VLM/LLM 决策服务

默认 API 形式：

```text
POST http://<host>:<port>/v1/chat/completions
```

请求格式：

```json
{
  "model": "...",
  "messages": [...]
}
```

MinerU 表格识别 prompt：

```text
Table Recognition: xxx
```

MinerU 表格识别结果预期包含 OTSL。

## 5. 图片输入方式

base64 图片输入已确认支持，因此第一版默认使用 base64 作为可靠模式。

实现中仍应保留图片输入方式配置：

```yaml
image_input_mode: base64
```

未来可选模式：

```yaml
image_input_mode: file_url
image_input_mode: path
```

等服务 IP 可用后，第一个 smoke test 需要验证 MinerU 和 Qwen 实际支持的 message 格式。如果 path 或 file URL 也可用，后续可以为性能优化启用。但第一版不能依赖 path 支持。

## 6. 输出字段

批量输出 JSONL 需要保留 benchmark 原始字段，并新增：

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

baseline 评分命令：

```bash
python /mnt/shared-storage-user/mineru2-shared/xiaojutao/utils/score_teds_jsonl.py \
  --input-jsonl OUTPUT.jsonl \
  --output-jsonl OUTPUT.baseline.scored.jsonl \
  --pred-field baseline_parse_result \
  --gt-field solution
```

agent 评分命令：

```bash
python /mnt/shared-storage-user/mineru2-shared/xiaojutao/utils/score_teds_jsonl.py \
  --input-jsonl OUTPUT.jsonl \
  --output-jsonl OUTPUT.agent.scored.jsonl \
  --pred-field agent_parse_result \
  --gt-field solution
```

## 7. Agent 流程

第一版只支持纵向切分。

流程：

1. 读取 benchmark 记录。
2. 解析图片路径。
3. 对整图调用 MinerU，生成 `baseline_parse_result`。
4. 生成纵向切分候选。
5. 使用图像处理启发式方法寻找更安全的横向切点。
6. 调用 Qwen3.5-397B VLM 审核并修正切分位置。
7. 在配置限制内迭代修正切分方案。
8. 按最终切分方案裁图。
9. 对每个 crop 调用 MinerU。
10. 对每个 crop 的 OTSL 做基础解析和轻量校验。
11. 按 crop 的纵向顺序拼接 OTSL。
12. 将拼接后的 OTSL 转为 HTML。
13. 写出结果 JSONL。
14. 在 Agent 外部运行 TEDS 评分。

## 8. 切分策略

第一版采用保守纵向切分：

- 每个 crop 保持完整表格宽度。
- 只沿 y 轴切分。
- 不使用重叠。
- 不主动切碎合并单元格。
- 第一版不把表头复制到每个 crop。

CV 候选切点生成不能只依赖可见表格线。

对于有线表，可以使用：

- 横向线响应
- 行边界信号
- 边缘密度

对于无线表或弱线表，可以使用：

- 横向空白带
- 文本/像素密度低谷
- 投影统计

对于浅色线条或线条颜色不稳定的情况，应退化到基于密度和空白带的策略。

VLM 审核负责最终判断切点是否在视觉上切穿文本、行、单元格或明显合并单元格。

## 9. OTSL 处理

OTSL token：

- `<fcel>`：有内容单元格
- `<ecel>`：空单元格
- `<lcel>`：从左侧合并而来，用于 colspan
- `<ucel>`：从上方合并而来，用于 rowspan
- `<xcel>`：同时从左侧和上方合并而来，用于二维合并区域
- `<nl>`：行结束

第一版实现容错纵向 OTSL 拼接：

- 用 `<nl>` 将每个 OTSL 拆成行。
- 保持 crop 原始纵向顺序。
- 拼接所有 crop 的行。
- 检查 token 合法性。
- 估计行数和列数，并写入 metadata。
- 允许轻微列数不一致。
- 优先做保守清洗，不做激进修复。

第一版不要求完美恢复跨 crop 边界的 rowspan 或 colspan。

## 10. 调用与迭代限制

默认限制：

```yaml
max_split_iterations: 3
max_recognition_retries: 2
max_chunks: 12
```

如果达到限制：

- 停止继续重试或修正。
- 使用当前可用的最佳结果。
- 在 `agent_metadata.warnings` 中记录原因。

如果单个 crop 失败：

- 不让整个 batch 崩溃。
- 标记该 crop 失败。
- 如果可以拼出部分结果，则样本标记为 `partial_success`。
- 保留足够 metadata 方便诊断。

## 11. 项目范围

第一版包含：

- OpenAI-compatible vLLM HTTP client。
- base64 图片 message 支持。
- MinerU 表格识别 client。
- Qwen3.5-397B 切分审核 client。
- 纵向切分候选生成。
- crop 裁剪和保存。
- OTSL 解析、校验、容错拼接。
- OTSL 到 HTML 转换集成。
- benchmark JSONL 批量运行脚本。
- 整图 baseline 识别结果收集。
- Agent 切分识别结果收集。
- TEDS 评分命令或 wrapper。
- metadata 和诊断信息输出。
- 3-5 条样本 smoke test。
- 50 条 large-table 样本完整评测。

## 12. 暂不实现

第一版不做：

- 横向切分。
- 二维网格切分。
- 跨页表格处理。
- 表格区域检测。
- 将表头复制到每个 crop。
- 重复表头删除。
- 跨 crop 边界的复杂 rowspan/colspan 恢复。
- 在 Agent 决策中使用 GT HTML。
- 将 TEDS 评分作为 Agent 可调用工具。
- 模型训练或微调。
- 多模型 ensemble。
- 针对单个样本写人工特化规则。
- 激进 OTSL 幻觉修复。

## 13. 分阶段验收项

开发时一次只做一个验收项。

每个验收项实现并验证通过后，必须先创建一个 git commit，再开始下一个验收项。这样后续如果改坏，最多只需要回退一小步。

### 验收项 1：项目骨架与配置

通过标准：

- `Table-Agent` 有清晰项目结构。
- 配置文件支持：
  - MinerU endpoint
  - Qwen endpoint
  - model name
  - image input mode
  - max split iterations
  - max recognition retries
  - max chunks
  - input/output paths
- 暂不需要实际模型调用。
- 基础 CLI 可以加载并打印校验后的配置。

通过后 git commit。

### 验收项 2：OpenAI-Compatible Vision Client Smoke Test

通过标准：

- client 可以发送 base64 image message。
- client 可以用 `Table Recognition: xxx` 调用 MinerU 服务。
- client 可以调用 Qwen 服务执行简单视觉检查 prompt。
- 原始响应会保存，方便调试。
- 如果服务 IP 暂不可用，该验收项标记为 blocked，不能用 mock 假装通过。

通过后 git commit。

### 验收项 3：整图 Baseline 收集

通过标准：

- 批处理脚本可以读取 benchmark JSONL。
- 可以解析图片路径。
- 可以对整图调用 MinerU。
- 写出 `baseline_parse_result`。
- 尽可能将 baseline OTSL 转为 HTML。
- 支持 `--start`、`--end`、`--limit`。
- 可以在 3-5 条样本上跑通。

通过后 git commit。

### 验收项 4：纵向切分候选生成

通过标准：

- 工具可以加载大图并生成纵向 crop box。
- chunk 数量遵守 `max_chunks`。
- 候选切点使用图像统计，不只依赖表格线。
- crop 图片可以保存。
- metadata 记录图片尺寸和 crop box。
- 不需要模型调用即可本地跑通。

通过后 git commit。

### 验收项 5：VLM 切分审核与迭代

通过标准：

- Qwen 可以审核候选切分位置。
- Qwen 可以返回接受或修正后的 y 坐标。
- 切分修正不会超过 `max_split_iterations`。
- 非法模型响应会被安全处理。
- metadata 记录迭代次数和 warning。
- 可以在 3-5 条样本上跑通。

通过后 git commit。

### 验收项 6：Crop 识别

通过标准：

- 每个 crop 会发送给 MinerU。
- 每个 crop 结果保存 OTSL 和 raw response。
- 每个 crop 的重试次数遵守 `max_recognition_retries`。
- 单个 crop 失败不会导致整个样本崩溃。
- metadata 记录 crop 状态。

通过后 git commit。

### 验收项 7：OTSL 拼接与 HTML 转换

通过标准：

- crop OTSL 可以拆成行。
- 行按纵向 crop 顺序拼接。
- token 合法性会被检查。
- 轻微列数不一致可以容忍。
- 拼接后的 OTSL 可以通过现有工具转为 HTML。
- 输出写入 `agent_parse_result`。

通过后 git commit。

### 验收项 8：端到端 Smoke Test

通过标准：

- 3-5 条 benchmark 样本可以端到端跑通。
- 输出包含：
  - `baseline_parse_result`
  - `agent_parse_result`
  - `agent_metadata`
- Agent 不读取、不使用 `solution`，除非单独运行评分。
- 单个样本失败不会导致整个 batch 崩溃。
- baseline 和 agent 字段都可以跑 TEDS 评分。

通过后 git commit。

### 验收项 9：50 条完整评测

通过标准：

- 跑完整 50 条 large-table 样本。
- 生成 baseline scored JSONL。
- 生成 agent scored JSONL。
- 生成汇总结果，包括：
  - baseline 平均 TEDS
  - agent 平均 TEDS
  - 绝对提升
  - 相对提升
  - success 数量
  - partial success 数量
  - failure 数量
  - 平均 chunk 数
  - 平均切分迭代次数
- 列出提升最多和下降最多的样本，方便分析。

通过后 git commit。

## 14. 总体验收

项目完成标准：

- 所有验收项均完成。
- 每个验收项都有对应 git commit。
- 50 条完整评测可以通过文档命令复现。
- 结果以 JSONL 文件保存。
- 最终报告明确说明 Table Agent 相比 MinerU2.5-Pro 整图 baseline 是否提升了 TEDS。

第一阶段不强制要求 TEDS 一定提升。第一阶段的成功标准是：实验可信、可复现、可诊断。TEDS 是否提升是本项目要测量的实验结果。

