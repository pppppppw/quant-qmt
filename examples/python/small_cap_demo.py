from __future__ import annotations

from quant_qmt.sdk import QmtGatewayClient
from quant_qmt.strategy.small_cap_proxy import run_small_cap_enhanced_proxy_demo


def main() -> None:
    client = QmtGatewayClient("http://127.0.0.1:9527", timeout=30)
    result = run_small_cap_enhanced_proxy_demo(
        client,
        stock_limit=100,
        top_n=5,
        submit=False,
    )
    print(result["proxy_notice"])
    print("planned orders:", len(result["planned_orders"]))


if __name__ == "__main__":
    main()
