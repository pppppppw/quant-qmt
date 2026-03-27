# Docker 参考文档

本轮 Docker 只提供参考方案，不作为本机强制验收项。

核心原则：

- Docker 容器不运行 MiniQMT
- Docker 容器只运行 `quant-qmt` 客户端
- 容器通过 `QMT_GATEWAY_URL` 访问 Windows 网关

## 1. 为什么不把 QMT 放进容器

MiniQMT / xtquant 的网关链路本质上是 Windows 依赖。

所以推荐拓扑永远是：

- Windows：MiniQMT + `quant-qmt gateway`
- Docker：SDK / CLI / demo client

## 2. 参考 Dockerfile

项目里提供了一个客户端用的参考 Dockerfile：

- `docker/Dockerfile.client`

用途：

- 让 Linux 容器里运行 `quant-qmt doctor`
- 运行 `data` / `trade` / `demo` 命令

## 3. 构建镜像

```bash
docker build -f docker/Dockerfile.client -t quant-qmt-client .
```

## 4. 运行容器

Windows Docker Desktop 常用：

```bash
docker run --rm -it \
  -e QMT_GATEWAY_URL=http://host.docker.internal:9527 \
  quant-qmt-client \
  quant-qmt data sector
```

如果 `host.docker.internal` 不可用，替换为 Windows 主机 IP：

```bash
docker run --rm -it \
  -e QMT_GATEWAY_URL=http://192.168.1.10:9527 \
  quant-qmt-client \
  quant-qmt smoke
```

## 5. 运行 small-cap demo

```bash
docker run --rm -it \
  -e QMT_GATEWAY_URL=http://host.docker.internal:9527 \
  -v $PWD/out:/app/out \
  quant-qmt-client \
  quant-qmt demo small-cap-enhanced \
    --plan-output /app/out/small-cap-plan.json \
    --orders-output /app/out/small-cap-orders.csv
```

## 6. 限制说明

- 容器里不需要 `xtquant`
- 容器里也不需要 `QMT_PATH`
- 所有 QMT 相关依赖都只在 Windows 网关侧存在
- Docker 路线本轮没有在当前机器上做强制实测
