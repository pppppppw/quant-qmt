# Contributing

Thanks for helping improve `quant-qmt`.

## Development Setup

```powershell
conda create -n quant-qmt311 python=3.11 -y
conda activate quant-qmt311
pip install -U pip
pip install -e .[dev]
```

## Before Opening a PR

Please do these checks locally when applicable:

```powershell
pytest
python -m compileall src
quant-qmt doctor
```

If your change touches live QMT behavior, also describe:

- Windows version
- Python version
- how `xtquant` was provided
- whether you validated on a test account or read-only flow

## Scope Guidelines

- Keep the Windows gateway boundary intact
- Do not make Linux or macOS depend on local MiniQMT
- Keep response contracts stable unless the change clearly improves the public API
- Be explicit when a strategy is proxy-based rather than strict historical factor-based

## Pull Request Notes

Good PRs here usually include:

- a clear problem statement
- a small test or reproduction
- docs updates when behavior changes
- notes about Windows-only validation when relevant
