# quant-qmt

`quant-qmt` 是一个独立的 QMT 开源项目，专门把 `QMT 网关`、`QMT 数据`、`QMT 交易` 抽成一个可单独安装、单独部署、单独维护的工具链。

它的核心价值很简单：

- 适合 A 股量化：股票池、交易日、历史数据、实时数据、交易接口都在一个体系里
- 策略更安全：很多别的方案本质上是在别人的服务器上跑，你的策略代码要交给别人；QMT 这套更适合跑在你自己的环境里，策略代码和执行边界都在自己手上
- 部署更灵活：可以本机直接调用，也可以把 Windows 网关放到局域网、云主机、Tailscale 或 VPN 里，让其他环境自由调用
- 数据更省事：对已开通 QMT 的用户，很多常用数据可以直接通过 `xtdata` 使用，不用先接一套额外的数据 SaaS；更高阶权限如部分 VIP / Level2 仍取决于券商和权限

`quant-qmt` is a standalone QMT gateway, data, and trading toolkit for A-share workflows.  
It keeps MiniQMT on Windows while letting other environments call the gateway over HTTP.

这里特别说明一下：本项目里说的“本地运行 QMT”，默认指的是 `MiniQMT` 这条链路，不是完整版 QMT 投研端。`quant-qmt` 的网关、`xtdata`、`xttrader` 集成都以 `MiniQMT / userdata_mini` 为运行前提。

## 为什么适合这个项目

- `QMT` 本身就贴近 A 股交易语义
- `xtdata + xttrader` 可以把数据、交易、查询和回调串起来
- 官方资料明确提到数据和策略计算都在本地运行
- 官方 XtQuant 文档明确写的是“基于 MiniQMT”，并要求先启动 `MiniQMT` 客户端
- 对开源项目来说，这很适合做成“Windows 执行边界 + 跨平台调用层”

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

## 许可证

当前仓库使用 [MIT License](./LICENSE)。
