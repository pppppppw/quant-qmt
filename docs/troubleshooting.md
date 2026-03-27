# 常见问题排查

## 1. `xtquant import failed`

表现：

- `quant-qmt doctor` 报 `xtquant import failed`
- 启动脚本在检查 `xtquant` 时失败

排查：

1. 先直接尝试：

```powershell
pip install xtquant
```

2. 如果还是不行，再确认这台 Windows 机器本身确实有 `xtquant`
3. 如果你是复用券商 / QMT 自带版本，找到它所在的 `site-packages`
4. 再设置：

```powershell
$env:QMT_XTQUANT_PATH = "C:\path\to\site-packages"
```

5. 重新执行：

```powershell
quant-qmt doctor
```

补充：

- 如果你已经正确设置了 `QMT_PATH`，`quant-qmt` 也会优先探测常见 MiniQMT 安装路径
- 所以现在 `QMT_XTQUANT_PATH` 是 fallback，不再是默认必填项

## 2. `QMT_PATH does not exist`

表现：

- 启动脚本提示 `QMT_PATH does not exist`

排查：

- 你传入的路径必须是 MiniQMT 的 `userdata_mini`
- 不是交易端根目录
- 不是安装目录

正确示例：

```text
C:\broker\MiniQMT\userdata_mini
```

## 3. `/health` 返回 `qmt_connected=false`

表现：

- 网关进程启动了
- 但是 `health` 不健康

优先排查：

1. MiniQMT 是否已启动并登录
2. `QMT_PATH` 是否指向正在使用的账号目录
3. `QMT_SESSION_ID` 是否与其他策略进程冲突
4. 当前 Python 进程是否真的导入了正确版本的 `xtquant`

## 4. `/api/v1/data/health` 失败

表现：

- 交易连接也许正常
- 但 xtdata 相关接口不可用

排查：

- 当前 `xtquant` 版本是否带 `xtdata`
- `xtdata.get_stock_list_in_sector("沪深A股")` 是否能正常执行

## 5. `account_id is required and no default account could be detected`

表现：

- 查询资产 / 持仓 / 订单时报错

排查：

- 先执行：

```powershell
quant-qmt trade account-infos
```

- 如果返回为空，说明 QMT 当前没有可识别账号
- 先确保 QMT 登录状态正常
- 或在命令里显式传 `--account-id`

## 6. `price must be > 0 for limit orders`

表现：

- 使用 `price_type=fix` 下单失败

原因：

- 限价单必须传正数 `price`

## 7. `xtdata.get_full_tick is not available in this build`

表现：

- `full_tick` / `realtime cache` 能力报不可用

原因：

- 当前 `xtquant` 构建缺少该接口

建议：

- 升级或更换可用 xtquant 版本
- 或在业务上降级为只使用日线 / 历史数据

## 8. `subscribe_whole_quote failed`

表现：

- 实时缓存接口返回订阅失败

排查：

- 当前时间是否非交易时段
- 当前 `xtdata` 版本是否支持 `subscribe_whole_quote`
- 代码列表是否格式正确，例如 `600000.SH`

## 9. smoke 通过了只读，但下单/撤单失败

常见原因：

- 当前不是交易时段
- 模拟盘权限不可用
- 账号未订阅成功
- 价格或数量不满足交易所规则

建议：

1. 先只跑只读 smoke
2. 再显式 `trade subscribe`
3. 再做最小订单验证

## 10. `small_cap_enhanced` demo 输出为空

排查：

- `stock_limit` 太小
- `lookback_days` 不足
- `min_history_days` 太高
- 市场状态过滤让当天信号被全部过滤

可以先放宽参数验证：

```powershell
quant-qmt demo small-cap-enhanced `
  --stock-limit 100 `
  --lookback-days 180 `
  --top-n 5 `
  --min-history-days 60
```

## 11. Linux / macOS 调不到 Windows 网关

排查：

1. Windows 启动时是否监听了 `0.0.0.0`
2. 防火墙是否开放 `9527`
3. 对方机器是否能 `curl http://windows-ip:9527/health`

## 12. Docker 容器里调不到宿主机

排查：

- Windows Docker Desktop 下优先尝试：

```text
http://host.docker.internal:9527
```

- 如果不可用，再改成宿主机实际 IP

## 13. `conda run` 在中文路径下报 `UnicodeEncodeError`

表现：

- `conda run -n quant-qmt311 ...` 自身报错
- 报错里出现 `gbk codec can't encode character`

原因：

- 当前机器的某些路径含中文
- Conda 包装层在 Windows GBK 输出时可能炸掉

解决：

- 直接调用目标环境里的 `python.exe`
- 使用项目自带的 `bootstrap.ps1` / `start_gateway.ps1`
- 尽量不要自己手写 `conda run -n ...` 去执行安装或启动

示例：

```powershell
C:\Users\<you>\miniconda3\envs\quant-qmt311\python.exe -m quant_qmt doctor
```

这是本机 `2026-03-27` 实测有效的绕过方式。
