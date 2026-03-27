from __future__ import annotations

from quant_qmt.sdk import QmtGatewayClient


def main() -> None:
    client = QmtGatewayClient("http://127.0.0.1:9527", timeout=15)
    print("health:", client.health())
    print("data_health:", client.data_health())
    print("sector count:", client.sector_stocks("沪深A股").get("count"))


if __name__ == "__main__":
    main()
