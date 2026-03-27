# API 文档

所有网关接口统一返回：

```json
{
  "code": 0,
  "message": "optional",
  "data": {}
}
```

非 0 `code` 或 HTTP 4xx/5xx 表示失败。

## 1. 健康检查

### `GET /health`

返回：

```json
{
  "status": "ok",
  "qmt_connected": true,
  "timestamp": "2026-03-27T10:00:00"
}
```

### `POST /api/v1/trader/reconnect`

作用：

- 显式触发 QMT 重连

### `GET /api/v1/callbacks/recent?limit=20`

作用：

- 获取最近回调事件

## 2. 数据接口

### `GET /api/v1/data/health`

作用：

- 检查 xtdata 是否可用

### `POST /api/v1/data/download`

请求：

```json
{
  "stock_list": ["600000.SH"],
  "period": "1d",
  "start_time": "20250101",
  "end_time": "20250327"
}
```

### `POST /api/v1/data/sector/stocks`

请求：

```json
{
  "sector_name": "沪深A股"
}
```

返回：

```json
{
  "code": 0,
  "data": {
    "sector_name": "沪深A股",
    "items": ["600000.SH", "000001.SZ"],
    "count": 2
  }
}
```

### `POST /api/v1/data/kline_rows`

请求：

```json
{
  "stock_list": ["600000.SH", "000001.SZ"],
  "period": "1d",
  "start_time": "20250101",
  "end_time": "20250327",
  "count": -1,
  "dividend_type": "none",
  "fill_data": true,
  "download": true
}
```

返回 `rows`：

```json
{
  "code": 0,
  "data": {
    "rows": [
      {
        "ts_code": "600000.SH",
        "trade_date": "20250327",
        "open": 10.1,
        "high": 10.3,
        "low": 10.0,
        "close": 10.2,
        "volume": 123456,
        "amount": 123456789
      }
    ],
    "count": 1,
    "period": "1d"
  }
}
```

### `POST /api/v1/data/cb_info`

请求：

```json
{
  "stock_list": ["113066.SH"],
  "refresh": true
}
```

说明：

- 优先 `download_cb_data + get_cb_info`
- 若 `get_cb_info` 为空，会回退 `get_instrument_detail`

### `POST /api/v1/data/market`

请求：

```json
{
  "stock_list": ["600000.SH"],
  "field_list": ["close", "amount"],
  "period": "1d",
  "count": 10
}
```

### `POST /api/v1/data/full_tick`

请求：

```json
{
  "stock_list": ["600000.SH"],
  "subscribe": true
}
```

### `POST /api/v1/data/realtime/cache`

请求：

```json
{
  "stock_list": ["600000.SH"],
  "subscribe": true,
  "fill_missing": true
}
```

## 3. 账户接口

### `POST /api/v1/account/subscribe`

```json
{
  "account_id": "1234567890",
  "account_type": "STOCK"
}
```

### `POST /api/v1/account/unsubscribe`

### `GET /api/v1/account/subscriptions`

## 4. 交易接口

### `POST /api/v1/order/stock`

```json
{
  "account_id": "1234567890",
  "account_type": "STOCK",
  "stock_code": "600000.SH",
  "order_type": "buy",
  "volume": 100,
  "price_type": "fix",
  "price": 10.2,
  "strategy_name": "demo",
  "order_remark": "demo-order"
}
```

### `POST /api/v1/order/stock/async`

与同步接口相同，只是返回异步 `seq`。

### `POST /api/v1/order/cancel`

按 `order_id`：

```json
{
  "account_id": "1234567890",
  "account_type": "STOCK",
  "order_id": 10001
}
```

按 `order_sysid`：

```json
{
  "account_id": "1234567890",
  "account_type": "STOCK",
  "order_sysid": "A123456",
  "market": "SH"
}
```

### `POST /api/v1/order/cancel/async`

与同步撤单接口相同，只是返回异步 `seq`。

## 5. 查询接口

### `GET /api/v1/query/asset`

参数：

- `account_id`
- `account_type`

### `GET /api/v1/query/positions`

### `GET /api/v1/query/position`

参数：

- `account_id`
- `account_type`
- `stock_code`

### `GET /api/v1/query/orders`

可选参数：

- `cancelable_only=true`

### `GET /api/v1/query/order`

参数：

- `order_id`

### `GET /api/v1/query/trades`

### `GET /api/v1/query/account_infos`

## 6. CLI 与 API 对照

- `quant-qmt smoke` 对应健康检查、数据检查、账户订阅、查询接口
- `quant-qmt data sector` 对应 `/api/v1/data/sector/stocks`
- `quant-qmt data kline` 对应 `/api/v1/data/kline_rows`
- `quant-qmt trade order` 对应 `/api/v1/order/stock`
- `quant-qmt demo small-cap-enhanced` 组合调用 universe、kline 与交易接口
