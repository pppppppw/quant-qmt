# Validation Report

Validation date:

- `2026-03-27`
- `2026-03-28`

Validation goal:

- verify `quant-qmt` as a standalone repository
- verify the native Windows path end to end
- keep Docker as documentation-only for this round

Sensitive local values such as account identifiers, asset values, and live order ids are intentionally redacted in this public report.

## Environment Summary

- Project root: a standalone `quant-qmt` sibling repository
- QMT path: validated with a real `userdata_mini` directory on Windows
- Python runtime: isolated `3.11.x` environment
- `xtquant`: loaded through `QMT_XTQUANT_PATH`

## Installation Result

Validated successfully:

```powershell
conda create -n quant-qmt311 python=3.11 -y
pip install -e .[dev]
```

Validated again on `2026-03-28` with the current simplified Windows path:

```powershell
.\scripts\windows\bootstrap.ps1 -QmtPath "D:\...\userdata_mini"
```

Result:

- bootstrap completed successfully
- target conda environment was resolved correctly
- `xtquant` was installed/imported successfully in the gateway environment

## Doctor Result

Validated successfully:

- `QMT_PATH` exists
- `xtquant` import succeeds
- `xtdata` import succeeds
- `xtdata.get_stock_list_in_sector("沪深A股")` succeeds

Validated again on `2026-03-28` through the Windows wrapper entrypoint:

```powershell
.\scripts\windows\qmt.ps1 doctor --qmt-path "D:\...\userdata_mini"
```

Result:

- wrapper resolved the target environment correctly
- doctor completed successfully without requiring manual `conda activate`

## Gateway Result

Validated successfully:

- gateway starts on `127.0.0.1:9527`
- XTTrader connection is established
- callback JSONL persistence is enabled

Validated again on `2026-03-28` with both simplified startup modes:

```powershell
.\scripts\windows\bootstrap.ps1 -QmtPath "D:\...\userdata_mini" -StartGateway
.\scripts\windows\start_gateway.ps1 -QmtPath "D:\...\userdata_mini" -GatewayHost 0.0.0.0
```

Result:

- local mode started successfully on `127.0.0.1:9527`
- remote mode started successfully on `0.0.0.0:9527`
- local health probe remained successful after remote-mode binding

## Read-Only Smoke Result

Validated successfully:

- `/health`
- `/api/v1/data/health`
- `/api/v1/data/kline_rows`
- `/api/v1/data/full_tick`
- `/api/v1/data/realtime/cache`
- account discovery
- account subscribe
- asset query
- positions query
- orders query
- trades query
- callbacks query

Validated again on `2026-03-28` via the Windows wrapper entrypoint:

```powershell
.\scripts\windows\qmt.ps1 smoke --base-url http://127.0.0.1:9527 --stock-code 600000.SH
```

Result:

- wrapper execution succeeded
- health/data/kline/full-tick/realtime-cache checks succeeded
- account discovery and readonly query flow succeeded

Artifacts generated during validation:

- `var/validation/smoke-readonly.json`

These runtime artifacts are intentionally gitignored and should not be committed into a public repository.

## Live Order / Cancel Result

Validated successfully on a test account with a minimal fixed-price order:

- order placement succeeded
- immediate follow-up order query succeeded
- cancel request succeeded
- final order state showed `filled_volume = 0`

This confirms the minimal live path:

- place order
- observe order record
- cancel unfilled order

## Demo Strategy Result

Validated successfully in dry-run mode:

- `small_cap_enhanced` QMT-only proxy demo
- universe fetch
- daily kline fetch
- signal generation
- planned order output

Artifacts generated during validation:

- `var/demo/small-cap-plan.json`
- `var/demo/small-cap-orders.csv`

These runtime artifacts are intentionally gitignored and should not be committed into a public repository.

## Docker Result

This round delivered:

- Docker documentation
- `docker/Dockerfile.client`

This round did not include:

- local Docker validation on the current machine

## Final Status

The standalone `quant-qmt` repository has been validated on the native Windows path for:

- isolated installation
- gateway startup
- QMT data access
- account discovery and subscribe
- query flows
- minimal live order and cancel flow
- demo strategy dry-run
