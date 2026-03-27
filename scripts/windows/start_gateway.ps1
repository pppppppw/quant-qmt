param(
    [string]$CondaEnv = "",
    [string]$QmtPath = "",
    [string]$XtquantPath = "",
    [int]$QmtSessionId = 123456,
    [string]$GatewayHost = "127.0.0.1",
    [int]$GatewayPort = 9527,
    [string]$CallbackLogFile = "",
    [switch]$InstallDeps,
    [switch]$UseActivePython
)

function Get-CondaExecutable {
    $condaCmd = Get-Command conda -ErrorAction SilentlyContinue
    if ($condaCmd) {
        return $condaCmd.Source
    }
    return ""
}

function Get-CondaEnvPrefix {
    param(
        [string]$CondaExe,
        [string]$Name
    )

    $jsonText = & $CondaExe env list --json
    if ($LASTEXITCODE -ne 0) {
        throw "failed to inspect conda env list"
    }
    $payload = $jsonText | ConvertFrom-Json
    foreach ($prefix in $payload.envs) {
        if ((Split-Path -Leaf $prefix) -eq $Name) {
            return $prefix
        }
    }
    return ""
}

function Invoke-Python {
    param(
        [string]$PythonExe,
        [string[]]$Arguments
    )

    & $PythonExe @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "command failed: $PythonExe $($Arguments -join ' ')"
    }
}

function Resolve-QmtPath {
    param(
        [string]$PreferredPath
    )

    $defaultQmtPathB64 = "RDpc5Zu96YeRUU1U5Lqk5piT56uv5qih5oufXHVzZXJkYXRhX21pbmk="
    $defaultQmtPath = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($defaultQmtPathB64))

    if (-not [string]::IsNullOrWhiteSpace($PreferredPath)) {
        if (Test-Path -LiteralPath $PreferredPath) {
            return $PreferredPath
        }
        Write-Host "[ERROR] Provided QmtPath does not exist: $PreferredPath"
        return ""
    }

    if (-not [string]::IsNullOrWhiteSpace($env:QMT_PATH)) {
        if (Test-Path -LiteralPath $env:QMT_PATH) {
            return $env:QMT_PATH
        }
        Write-Host "[WARN] Ignoring invalid QMT_PATH from env: $env:QMT_PATH"
    }

    if (Test-Path -LiteralPath $defaultQmtPath) {
        return $defaultQmtPath
    }

    Write-Host "[ERROR] Default QMT_PATH does not exist: $defaultQmtPath"
    Write-Host "[HINT] Set -QmtPath or export QMT_PATH before retrying."
    return ""
}

$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
Set-Location $projectRoot

if ([string]::IsNullOrWhiteSpace($CondaEnv)) {
    $CondaEnv = if ($env:CONDA_ENV) { $env:CONDA_ENV } else { "quant-qmt311" }
}

$QmtPath = Resolve-QmtPath -PreferredPath $QmtPath
if ([string]::IsNullOrWhiteSpace($QmtPath)) {
    exit 1
}

if ($QmtSessionId -eq 123456 -and $env:QMT_SESSION_ID) {
    try { $QmtSessionId = [int]$env:QMT_SESSION_ID } catch { $QmtSessionId = 123456 }
}

if ([string]::IsNullOrWhiteSpace($XtquantPath) -and $env:QMT_XTQUANT_PATH) {
    $XtquantPath = $env:QMT_XTQUANT_PATH
}

if ([string]::IsNullOrWhiteSpace($CallbackLogFile)) {
    if ($env:QMT_CALLBACK_LOG_FILE) {
        $CallbackLogFile = $env:QMT_CALLBACK_LOG_FILE
    } else {
        $CallbackLogFile = Join-Path $projectRoot "var\callbacks\callbacks.jsonl"
    }
}

$pythonExe = ""
if ($UseActivePython.IsPresent) {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCmd) {
        throw "python was not found in PATH"
    }
    $pythonExe = $pythonCmd.Source
} else {
    $condaExe = Get-CondaExecutable
    if ([string]::IsNullOrWhiteSpace($condaExe)) {
        throw "conda was not found in PATH. Please install Miniconda first or rerun with -UseActivePython."
    }

    $envPrefix = Get-CondaEnvPrefix -CondaExe $condaExe -Name $CondaEnv
    if ([string]::IsNullOrWhiteSpace($envPrefix)) {
        throw "conda env not found: $CondaEnv. Run bootstrap.ps1 first or rerun with -UseActivePython."
    }

    $pythonExe = Join-Path $envPrefix "python.exe"
    if (-not (Test-Path -LiteralPath $pythonExe)) {
        throw "python.exe was not found in conda env: $envPrefix"
    }
}

$env:CONDA_ENV = $CondaEnv
$env:QMT_PATH = $QmtPath
$env:QMT_SESSION_ID = "$QmtSessionId"
$env:QMT_GATEWAY_HOST = $GatewayHost
$env:QMT_GATEWAY_PORT = "$GatewayPort"
$env:QMT_CALLBACK_LOG_FILE = $CallbackLogFile
$env:PYTHONPATH = "$projectRoot\src;$env:PYTHONPATH"
if (-not [string]::IsNullOrWhiteSpace($XtquantPath)) {
    $env:QMT_XTQUANT_PATH = $XtquantPath
}
if ([string]::IsNullOrWhiteSpace($env:PYTHONUTF8)) {
    $env:PYTHONUTF8 = "1"
}
if ([string]::IsNullOrWhiteSpace($env:PYTHONIOENCODING)) {
    $env:PYTHONIOENCODING = "utf-8"
}

Write-Host "[INFO] PROJECT_ROOT=$projectRoot"
Write-Host "[INFO] PYTHON=$pythonExe"
Write-Host "[INFO] CONDA_ENV=$env:CONDA_ENV"
Write-Host "[INFO] QMT_PATH=$env:QMT_PATH"
Write-Host "[INFO] QMT_SESSION_ID=$env:QMT_SESSION_ID"
Write-Host "[INFO] QMT_GATEWAY_HOST=$env:QMT_GATEWAY_HOST"
Write-Host "[INFO] QMT_GATEWAY_PORT=$env:QMT_GATEWAY_PORT"
Write-Host "[INFO] QMT_CALLBACK_LOG_FILE=$env:QMT_CALLBACK_LOG_FILE"
Write-Host "[INFO] QMT_XTQUANT_PATH=$env:QMT_XTQUANT_PATH"

if ($InstallDeps.IsPresent) {
    Write-Host "[INFO] Installing quant-qmt in editable mode..."
    Invoke-Python -PythonExe $pythonExe -Arguments @("-X", "utf8", "-m", "pip", "install", "-U", "pip")
    Invoke-Python -PythonExe $pythonExe -Arguments @("-X", "utf8", "-m", "pip", "install", "-e", ".")
}

$xtquantOk = $false
try {
    Write-Host "[INFO] Checking xtquant import..."
    Invoke-Python -PythonExe $pythonExe -Arguments @(
        "-X", "utf8", "-c",
        "import sys; from quant_qmt.config import configure_import_paths; configure_import_paths(); import xtquant; print('[INFO] Python=' + sys.executable); print('[INFO] xtquant=' + getattr(xtquant, '__file__', '<builtin>'))"
    )
    $xtquantOk = $true
} catch {
    Write-Host "[WARN] xtquant import failed in selected runtime."
}

if (-not $xtquantOk -and $InstallDeps.IsPresent -and [string]::IsNullOrWhiteSpace($env:QMT_XTQUANT_PATH)) {
    Write-Host "[INFO] Trying pip install xtquant..."
    try {
        Invoke-Python -PythonExe $pythonExe -Arguments @("-X", "utf8", "-m", "pip", "install", "xtquant")
        Invoke-Python -PythonExe $pythonExe -Arguments @(
            "-X", "utf8", "-c",
            "import sys; from quant_qmt.config import configure_import_paths; configure_import_paths(); import xtquant; print('[INFO] Python=' + sys.executable); print('[INFO] xtquant=' + getattr(xtquant, '__file__', '<builtin>'))"
        )
        $xtquantOk = $true
    } catch {
        Write-Host "[WARN] pip install xtquant did not complete successfully."
    }
}

if (-not $xtquantOk) {
    Write-Host "[ERROR] xtquant import failed in selected runtime."
    Write-Host "[HINT] First try: pip install xtquant"
    Write-Host "[HINT] If you want to reuse the broker-bundled runtime, set QMT_XTQUANT_PATH."
    exit 1
}

if (-not (Test-Path -LiteralPath (Split-Path -Parent $CallbackLogFile))) {
    New-Item -ItemType Directory -Path (Split-Path -Parent $CallbackLogFile) -Force | Out-Null
}

Write-Host "[INFO] Starting quant-qmt gateway..."
& $pythonExe -X utf8 -m quant_qmt gateway start --host $GatewayHost --port $GatewayPort --qmt-path $QmtPath --session-id $QmtSessionId --callback-log-file $CallbackLogFile
exit $LASTEXITCODE
