# `small_cap_enhanced` QMT-only 代理版示例

## 1. 这是什么

这是一个为 `quant-qmt` 单独准备的示例策略。

它的特点：

- 直接从 QMT 拉 `沪深A股` universe
- 直接从 QMT 拉日线 `close/volume/amount`
- 在内存里做打分
- 输出计划单
- 可选走模拟盘下单

## 2. 这不是什么

它不是严格历史市值版 `small_cap_enhanced`。

原因：

- QMT 原生链路里不直接提供完整可靠的历史 `circ_mv / total_mv`
- 所以本 demo 用 `amount / 流动性` 代理规模

请始终把它叫做：

- `small_cap_enhanced QMT-only 代理版`

不要叫：

- 严格历史市值版
- 真实历史小市值版

## 3. 默认流程

1. 通过 `/api/v1/data/sector/stocks` 拿 `沪深A股`
2. 批量拉日线
3. 计算代理版小市值增强分数
4. 选出 Top N
5. 生成计划单
6. 可选提交模拟盘订单

## 4. 快速运行

### 4.1 只输出计划单

```powershell
quant-qmt demo small-cap-enhanced `
  --plan-output .\var\demo\small-cap-plan.json `
  --orders-output .\var\demo\small-cap-orders.csv
```

### 4.2 控制 universe 大小

```powershell
quant-qmt demo small-cap-enhanced `
  --stock-limit 200 `
  --top-n 8 `
  --plan-output .\var\demo\small-cap-plan.json
```

### 4.3 开启模拟盘提交

```powershell
quant-qmt demo small-cap-enhanced `
  --account-id 1234567890 `
  --submit `
  --plan-output .\var\demo\small-cap-submit.json
```

## 5. 常用参数

- `--sector-name`
  - 默认 `沪深A股`
- `--stock-limit`
  - 限制 universe 数量，方便快速验证
- `--lookback-days`
  - 回看窗口
- `--top-n`
  - 最终输出候选数
- `--budget-per-order`
  - 单票预算
- `--price-type`
  - `market` 或 `fix`
- `--price-offset-bps`
  - 限价模式下的偏移
- `--submit`
  - 是否真正提交到 QMT
- `--no-dedupe`
  - 是否关闭去重

## 6. 输出文件

### `--plan-output`

推荐写 JSON，包含：

- 策略标识
- 代理模式说明
- 参数
- 计划单
- 已提交结果

### `--orders-output`

推荐写 CSV 或 Parquet，只保留计划单明细，方便二次分析。

## 7. 前置条件

如果你要开启 `--submit`，至少需要：

- QMT 已连接
- 账号可识别
- 模拟盘 / 实盘权限可用
- 当前时段允许委托

## 8. 排障建议

- 先不用 `--submit`
- 先看计划单是否合理
- 再确认下单价格、数量、remark、去重逻辑
