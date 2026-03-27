# 部署方案

## 1. 物理机 Windows

最简单，也是推荐方案：

- Windows 物理机安装 MiniQMT
- 同机启动 `quant-qmt gateway`
- 本机或远程客户端访问该网关

适合：

- 个人开发
- 本机模拟盘
- 局域网多端共用

## 2. Windows 虚拟机

适合：

- 主开发机是 Linux / macOS
- 但必须要一个独立 Windows 交易节点

建议结构：

- Windows VM：MiniQMT + `quant-qmt gateway`
- 主开发机：SDK / CLI / 策略运行

注意：

- 需要确保虚拟机网络与宿主机互通
- 需要固定 IP 或固定主机名

## 3. Windows 云主机

适合：

- 远程托管
- 多地访问
- 需要常驻网关

建议结构：

- 云主机：MiniQMT + `quant-qmt gateway`
- 本地开发机：通过 `QMT_GATEWAY_URL` 访问

务必注意：

- 9527 不建议直接公网裸露
- 建议加白名单、VPN 或内网访问策略

## 4. Docker 客户端方案

本轮不在本机强制验证，只提供文档参考。  
原则是：

- Docker 容器不运行 MiniQMT
- Docker 容器只装 `quant-qmt`
- 容器通过 `QMT_GATEWAY_URL` 访问 Windows 网关

## 5. 推荐拓扑

### 5.1 单机开发

- Windows
  - MiniQMT
  - quant-qmt gateway
  - quant-qmt CLI / demo

### 5.2 异构双机

- Windows
  - MiniQMT
  - gateway
- Linux/macOS
  - quant-qmt CLI
  - 策略任务

### 5.3 云上托管

- Windows 云主机
  - MiniQMT
  - gateway
- 本地机器
  - SDK / CLI / 自动化脚本
