# Linux / macOS 远程调用 Windows 网关

这份文档强调的是本项目最重要的优势之一：

- QMT 网关放在 Windows
- 其他模块放在任意环境
- 只要能连到网关，就能自由使用数据、查询和交易能力

## 1. 典型拓扑

最常见的几种方式：

- 同一局域网
- Tailscale
- VPN
- 云主机内网

推荐思路始终一样：

- Windows 上运行 MiniQMT 和 `quant-qmt gateway`
- Linux / macOS / Docker 只通过 HTTP 调用网关

## 2. Windows 端怎么开

最省事的方式是直接：

```powershell
.\scripts\windows\bootstrap.ps1 -QmtPath "C:\broker\MiniQMT\userdata_mini" -StartGateway -GatewayHost 0.0.0.0
```

如果你已经完成初始化，也可以只起网关。

只本机调用时，用：

```powershell
.\scripts\windows\start_gateway.ps1
```

如果要给其他环境调用，用：

```powershell
.\scripts\windows\start_gateway.ps1 -GatewayHost 0.0.0.0
```

同时确认：

- 防火墙已放通 9527
- 局域网、Tailscale 或安全组允许访问 9527

## 3. Linux 侧

```bash
cd /path/to/quant-qmt
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
export QMT_GATEWAY_URL=http://windows-host:9527
quant-qmt doctor --check-gateway
quant-qmt data sector
```

## 4. macOS 侧

```bash
cd /path/to/quant-qmt
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
export QMT_GATEWAY_URL=http://windows-host:9527
quant-qmt smoke
```

## 5. 如果你用的是 Tailscale

思路就是把 Windows 主机和调用方放到同一个 Tailnet。

然后在客户端侧：

```bash
export QMT_GATEWAY_URL=http://windows-tailscale-ip:9527
quant-qmt doctor --check-gateway
```

## 6. 常见调用模式

### 6.1 拉全市场 universe

```bash
quant-qmt data sector --sector-name 沪深A股 --output ./a-share.json
```

### 6.2 拉日线

```bash
quant-qmt data kline --stock-list 600000.SH,000001.SZ --count 20 --output ./kline.csv
```

### 6.3 跑策略 demo

```bash
quant-qmt demo small-cap-enhanced --plan-output ./small-cap-plan.json --orders-output ./small-cap-orders.csv
```

## 7. 这套模式为什么方便

- 交易执行边界固定在 Windows
- 策略、任务调度、研究服务可以放在你最顺手的环境
- 换机器时不需要把整套研究环境跟着搬到 Windows
- 本机模式和远程模式使用的是同一套 API / SDK / CLI

## 8. 远程交易注意事项

- 真正的下单动作仍然发生在 Windows 上的 QMT 进程
- Linux / macOS 只是通过 HTTP 发交易请求
- 建议先用计划单模式验证
- 再确认账号、时段、网络后，才打开真实提交模式

## 9. 安全建议

- 优先局域网、Tailscale、VPN 或云内网
- 不建议直接公网裸露 9527
- 如需公网中转，至少加 ACL、反向代理白名单或堡垒机
