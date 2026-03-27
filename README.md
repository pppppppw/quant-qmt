# quant-qmt

> 开箱即用的 A 股量化交易开源工具链：基于 `MiniQMT` 一键拉起数据与交易网关，让研究、选股、信号生成、下单执行和远程调用尽快跑起来。

如果你想开始做 A 股量化，但不想一上来就被 `Windows 环境`、`QMT 接入`、`编码问题`、`网关部署`、`远程调用` 这些细节绊住，`quant-qmt` 就是在解决这段最麻烦的基础设施。

- 开箱即用：按 Quick Start 执行，一条命令就能初始化环境并启动网关
- 适合 A 股量化：股票池、交易日、历史数据、实时数据、交易接口都在一个体系里
- 安全可控：很多别的方案本质上跑在别人的服务器上，而这套更适合跑在你自己的环境里，策略代码和执行边界都留在自己手上
- 部署灵活：可以本机直接调用，也可以把 Windows 网关放到局域网、云主机、Tailscale 或 VPN 里，让其他环境自由调用
- 数据省事：对已开通 QMT 的用户，很多常用数据可以直接通过 `xtdata` 使用，不用先接一套额外的数据 SaaS

一句话理解这个项目：

> 用 `MiniQMT` 解决 A 股数据和交易入口，用独立 Windows 网关隔离执行边界，用跨平台 SDK / CLI / HTTP 接口把量化研究到实盘执行这条链路尽快跑通。

`quant-qmt` is a standalone MiniQMT gateway, data, and trading toolkit for A-share quant workflows.

这里特别说明一下：本项目里说的“本地运行 QMT”，默认指的是 `MiniQMT` 这条链路，不是完整版 QMT 投研端。`quant-qmt` 的网关、`xtdata`、`xttrader` 集成都以 `MiniQMT / userdata_mini` 为运行前提。

## 适合谁

- 想从 0 到 1 开始做 A 股量化交易的个人投资者
- 想把策略代码留在自己机器或自己服务器里的开发者
- 想把 Windows 交易执行边界和 Linux / macOS 研究环境拆开的团队
- 已经开通 QMT，希望先用一套简单、透明、可控的方式跑通数据到交易闭环的人

## 如何开始做 A 股量化

最实用的起步方式其实很简单：

1. 先开通 `MiniQMT / QMT` 权限，准备一个可登录的 Windows 环境。
2. 用 `quant-qmt` 把 `MiniQMT` 起成一个独立网关，先把数据、查询、下单、撤单这些基础链路跑通。
3. 先跑仓库自带的 `small_cap_enhanced` 示例策略，再逐步替换成你自己的策略逻辑。

更详细的背景说明见 [QMT 背景与价值](./docs/qmt-background.md)。

## 快速开始

目标是让小白按 Quick Start 就能跑起来。

### 0. 前置准备

- 安装并登录 MiniQMT
- 先在券商侧开通 `MiniQMT / QMT` 权限
- 资金门槛很多券商常见是 `10 万左右起`，也有更高要求，实际以券商和客户经理口径为准
- 安装 [Miniconda](https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html) 或已有 Python 3.11

### 1. 获取项目

```powershell
cd C:\workspace
git clone https://github.com/pppppppw/quant-qmt.git quant-qmt
cd .\quant-qmt
```

### 2. 一条命令初始化并启动

本机模式：

```powershell
.\scripts\windows\bootstrap.ps1 -QmtPath "C:\broker\MiniQMT\userdata_mini" -StartGateway
```

远程网关模式：

```powershell
.\scripts\windows\bootstrap.ps1 -QmtPath "C:\broker\MiniQMT\userdata_mini" -StartGateway -GatewayHost 0.0.0.0
```

如果你只想先初始化环境，不立刻起网关，再运行：

```powershell
.\scripts\windows\bootstrap.ps1
```

如果你更习惯双击或 `cmd`：

```bat
.\scripts\windows\bootstrap.bat
```

这个脚本会：

- 创建 `quant-qmt311` conda 环境
- 安装项目本身
- 尝试 `pip install xtquant`
- 可选地直接执行 `doctor + gateway start`
- 打印下一步命令

现在真正的主脚本是 `bootstrap.ps1` 和 `start_gateway.ps1`。  
`.bat` 文件只是兼容入口，不再单独维护另一套逻辑。

### 3. 做一次检查

```powershell
.\scripts\windows\qmt.ps1 doctor
```

### 4. 启动网关

本机安全模式：

```powershell
.\scripts\windows\start_gateway.ps1
```

远程网关模式：

```powershell
.\scripts\windows\start_gateway.ps1 -GatewayHost 0.0.0.0
```

### 5. 验证

```powershell
.\scripts\windows\qmt.ps1 smoke --stock-code 600000.SH
```

### 6. 跑示例策略

```powershell
.\scripts\windows\qmt.ps1 demo small-cap-enhanced `
  --plan-output .\var\demo\small-cap-plan.json `
  --orders-output .\var\demo\small-cap-orders.csv
```

如果你已经手动 `conda activate quant-qmt311`，再直接用 `quant-qmt ...` 也可以。

## 两种典型用法

### 1. 同环境直接调用

- MiniQMT、网关、策略都在同一台 Windows 上
- 最简单，最适合本机验证和个人使用

### 2. Windows 网关 + 其他环境调用

- 网关部署在 Windows
- 策略、调度、研究、服务可以在 Linux / macOS / Docker
- 通过局域网、Tailscale、VPN、云主机内网等访问网关

这是 `quant-qmt` 最强调的便利性：  
交易执行边界留在 Windows，其他模块想放哪就放哪。

## 关于 127.0.0.1 和 0.0.0.0

- 默认推荐 `127.0.0.1`，因为这是最安全的本机模式
- 如果你要让别的环境调用网关，就改成 `0.0.0.0`
- 远程模式下推荐配合 Tailscale、VPN、内网、安全组或 ACL 使用，不建议直接裸露公网

## 关于 xtquant

现在的推荐顺序是：

1. 先让 bootstrap 或你自己直接 `pip install xtquant`
2. 如果你想沿用券商自带的 `xtquant`，再使用 `QMT_XTQUANT_PATH`
3. 如果只设置了 `QMT_PATH`，`quant-qmt` 也会优先探测常见 MiniQMT 安装路径

之所以不把 `xtquant` 直接放到基础依赖里，是因为：

- 这个项目的客户端支持 Windows / Linux / macOS
- 但真正需要 `xtquant` 的只有 Windows 网关侧
- 非 Windows 调用方只需要 HTTP / SDK / CLI，不需要把券商运行时也装进去

另外，旧项目里常见的 `GBK / 中文路径 / conda run` 报错，核心是编码和包装层问题。  
现在安装脚本和启动脚本都优先直接调用目标环境里的 `python.exe`，尽量绕开这条坑链路。

## CLI 概览

- `quant-qmt doctor`
- `quant-qmt gateway start`
- `quant-qmt smoke`
- `quant-qmt data sector`
- `quant-qmt data kline`
- `quant-qmt data cb-info`
- `quant-qmt data full-tick`
- `quant-qmt data realtime-cache`
- `quant-qmt trade account-infos`
- `quant-qmt trade asset`
- `quant-qmt trade position`
- `quant-qmt trade positions`
- `quant-qmt trade order-info`
- `quant-qmt trade orders`
- `quant-qmt trade trades`
- `quant-qmt trade order`
- `quant-qmt trade cancel`
- `quant-qmt demo small-cap-enhanced`

## 文档

- [QMT 背景与价值](./docs/qmt-background.md)
- [Windows 从零部署](./docs/windows-setup.md)
- [远程调用说明](./docs/remote-usage.md)
- [架构说明](./docs/architecture.md)
- [API 文档](./docs/api.md)
- [小市值示例策略](./docs/small-cap-demo.md)
- [常见问题排查](./docs/troubleshooting.md)
- [Docker 参考文档](./docs/docker.md)
- [验证报告](./docs/validation-report.md)

## 联系方式

有问题欢迎交流，可以加我微信。

![微信二维码](./docs/assets/wechat-qr.jpg)

## 许可证

当前仓库使用 [MIT License](./LICENSE)。
