# Windows 从零部署

这份文档按“小白第一次上手”的思路来写，目标是：

- 按顺序照着做
- 不需要先懂 QMT 内部细节
- 跑完就能把网关起起来

先强调一个容易混淆的点：

- 本项目这里说的 QMT，本质上指 `MiniQMT` 运行链路
- 也就是官方 XtQuant 文档里要求的 `MiniQMT + userdata_mini`
- 不是完整版 QMT 投研端按同样方式直接替代

## 0. 你需要先准备什么

- Windows 10/11
- 已安装并可登录的 MiniQMT
- 已在券商侧开通 `MiniQMT / QMT` 权限
- 资金门槛很多券商常见是 `10 万左右起`，也有券商要求更高，实际以券商和客户经理口径为准
- MiniQMT 的 `userdata_mini` 路径
- [Miniconda](https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html) 或现成 Python 3.11

示例路径：

```text
C:\broker\MiniQMT\userdata_mini
```

## 1. 获取项目

```powershell
cd C:\workspace
git clone https://github.com/pppppppw/quant-qmt.git quant-qmt
cd .\quant-qmt
```

## 2. 推荐的一条命令

本机模式：

```powershell
.\scripts\windows\bootstrap.ps1 -QmtPath "C:\broker\MiniQMT\userdata_mini" -StartGateway
```

远程网关模式：

```powershell
.\scripts\windows\bootstrap.ps1 -QmtPath "C:\broker\MiniQMT\userdata_mini" -StartGateway -GatewayHost 0.0.0.0
```

如果你只想先装环境，不立刻启动，再看下面的“分步模式”。

## 3. 分步模式

推荐直接运行：

```powershell
.\scripts\windows\bootstrap.ps1
```

这个脚本会：

- 创建 `quant-qmt311` conda 环境
- 安装项目本身
- 尝试直接 `pip install xtquant`
- 打印下一步命令

现在这是唯一推荐的安装主脚本。  
`bootstrap.bat` 只是为了兼容双击或 `cmd`，内部仍然转调这个 PowerShell 脚本。

如果你不用 PowerShell，也可以：

```bat
.\scripts\windows\bootstrap.bat
```

## 4. 设置最少环境变量

```powershell
$env:QMT_PATH = "C:\broker\MiniQMT\userdata_mini"
$env:QMT_SESSION_ID = "123456"
```

通常你不需要手工设置 `QMT_XTQUANT_PATH`。  
只有下面两种情况才需要：

- `pip install xtquant` 失败
- 你明确想复用券商 / QMT 自带的 `xtquant`

这时再补：

```powershell
$env:QMT_XTQUANT_PATH = "C:\path\to\site-packages"
```

## 5. 做一次检查

```powershell
.\scripts\windows\qmt.ps1 doctor
```

## 6. 启动网关

### 6.1 本机安全模式

```powershell
.\scripts\windows\start_gateway.ps1
```

这适合：

- 网关和调用方在同一台机器
- 你先想把本机链路跑通

### 6.2 远程网关模式

```powershell
.\scripts\windows\start_gateway.ps1 -GatewayHost 0.0.0.0
```

这适合：

- 网关放在 Windows
- 其他模块放在 Linux / macOS / Docker
- 通过局域网、Tailscale、VPN、云主机内网去调用

这恰恰是本项目最想强调的便利性。

补充：

- 现在 `start_gateway.ps1` 是唯一推荐的启动主脚本
- `start_gateway.bat` 只是兼容入口
- 脚本内部优先直接调用目标环境里的 `python.exe`
- 这样可以尽量避开 `conda run + 中文路径 + GBK` 导致的编码报错

## 7. 验证

```powershell
.\scripts\windows\qmt.ps1 smoke --stock-code 600000.SH
```

如果你已经知道模拟盘账号，也可以：

```powershell
.\scripts\windows\qmt.ps1 smoke --account-id 1234567890 --stock-code 600000.SH
```

## 8. 跑示例策略

先只跑计划单：

```powershell
.\scripts\windows\qmt.ps1 demo small-cap-enhanced `
  --plan-output .\var\demo\small-cap-plan.json `
  --orders-output .\var\demo\small-cap-orders.csv
```

如果你已经手动 `conda activate quant-qmt311`，也可以直接用 `quant-qmt ...`。

## 9. 关于数据为什么省事

对已开通 QMT 的用户，很多常用数据可以直接通过 `xtdata` 使用：

- 交易日
- 股票池
- 合约信息
- 历史 K 线
- 实时快照

这意味着很多时候你不用一上来就再接一套第三方数据 SaaS。  
但也要注意：

- 更长历史范围
- 一些更高阶数据
- 部分 Level2 / VIP 行情

仍然取决于券商和权限。

## 10. 为什么安全性主要体现在“自己的环境里跑”

这点要讲清楚：

- 很多别的方案，本质上是把策略代码放到别人的服务器上跑
- QMT 这套更适合把数据、策略和执行边界留在你自己的环境里
- `quant-qmt` 又把这件事进一步做成了“Windows 网关 + 其他环境调用”的模式

所以这里强调的安全性，最核心就是：

- 策略代码不必交给第三方托管环境
- 券商终端不必暴露给所有调用方
- 交易入口可以收口成一个可控网关
