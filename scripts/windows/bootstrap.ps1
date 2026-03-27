param(
    [string]$CondaEnv = "quant-qmt311",
    [string]$PythonVersion = "3.11",
    [string]$QmtPath = "",
    [string]$XtquantPath = "",
    [int]$QmtSessionId = 123456,
    [string]$GatewayHost = "127.0.0.1",
    [int]$GatewayPort = 9527,
    [string]$CallbackLogFile = "",
    [switch]$StartGateway,
    [switch]$UseActivePython,
    [switch]$WithDev,
    [switch]$SkipXtquantPip
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

    if (-not [string]::IsNullOrWhiteSpace($PreferredPath)) {
        if (Test-Path -LiteralPath $PreferredPath) {
            return $PreferredPath
        }
        throw "QMT_PATH does not exist: $PreferredPath"
    }

    if (-not [string]::IsNullOrWhiteSpace($env:QMT_PATH)) {
        if (Test-Path -LiteralPath $env:QMT_PATH) {
            return $env:QMT_PATH
        }
        throw "QMT_PATH from env does not exist: $env:QMT_PATH"
    }

    return ""
}

$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
Set-Location $projectRoot

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
        Write-Host "[INFO] Creating conda env $CondaEnv (python=$PythonVersion)..."
        & $condaExe create -n $CondaEnv "python=$PythonVersion" -y
        if ($LASTEXITCODE -ne 0) {
            throw "failed to create conda env $CondaEnv"
        }
        $envPrefix = Get-CondaEnvPrefix -CondaExe $condaExe -Name $CondaEnv
    }

    $pythonExe = Join-Path $envPrefix "python.exe"
    if (-not (Test-Path -LiteralPath $pythonExe)) {
        throw "python.exe was not found in conda env: $envPrefix"
    }
}

$installTarget = if ($WithDev.IsPresent) { ".[dev]" } else { "." }

Write-Host "[INFO] PROJECT_ROOT=$projectRoot"
Write-Host "[INFO] PYTHON=$pythonExe"
Write-Host "[INFO] INSTALL_TARGET=$installTarget"

Invoke-Python -PythonExe $pythonExe -Arguments @("-X", "utf8", "-m", "pip", "install", "-U", "pip")
Invoke-Python -PythonExe $pythonExe -Arguments @("-X", "utf8", "-m", "pip", "install", "-e", $installTarget)

$xtquantOk = $false
try {
    Invoke-Python -PythonExe $pythonExe -Arguments @("-X", "utf8", "-c", "import xtquant; print(getattr(xtquant, '__file__', '<builtin>'))")
    $xtquantOk = $true
    Write-Host "[INFO] xtquant import succeeded."
} catch {
    Write-Host "[WARN] xtquant is not importable in the selected environment yet."
}

if (-not $xtquantOk -and -not $SkipXtquantPip.IsPresent) {
    Write-Host "[INFO] Trying pip install xtquant..."
    try {
        Invoke-Python -PythonExe $pythonExe -Arguments @("-X", "utf8", "-m", "pip", "install", "xtquant")
        Invoke-Python -PythonExe $pythonExe -Arguments @("-X", "utf8", "-c", "import xtquant; print(getattr(xtquant, '__file__', '<builtin>'))")
        $xtquantOk = $true
        Write-Host "[INFO] xtquant installed successfully from PyPI."
    } catch {
        Write-Host "[WARN] pip install xtquant did not complete successfully."
    }
}

if (-not [string]::IsNullOrWhiteSpace($XtquantPath)) {
    $env:QMT_XTQUANT_PATH = $XtquantPath
}

if ($QmtSessionId -eq 123456 -and $env:QMT_SESSION_ID) {
    try { $QmtSessionId = [int]$env:QMT_SESSION_ID } catch { $QmtSessionId = 123456 }
}

if ($StartGateway.IsPresent) {
    $resolvedQmtPath = Resolve-QmtPath -PreferredPath $QmtPath
    if ([string]::IsNullOrWhiteSpace($resolvedQmtPath)) {
        throw "QMT_PATH is required when using -StartGateway"
    }

    if ([string]::IsNullOrWhiteSpace($CallbackLogFile)) {
        if ($env:QMT_CALLBACK_LOG_FILE) {
            $CallbackLogFile = $env:QMT_CALLBACK_LOG_FILE
        } else {
            $CallbackLogFile = Join-Path $projectRoot "var\callbacks\callbacks.jsonl"
        }
    }

    if (-not $xtquantOk -and [string]::IsNullOrWhiteSpace($env:QMT_XTQUANT_PATH)) {
        Write-Host "[ERROR] xtquant is still unavailable."
        Write-Host "[HINT] First try: pip install xtquant"
        Write-Host "[HINT] If you want to reuse the broker-bundled runtime, set QMT_XTQUANT_PATH."
        exit 1
    }

    $env:QMT_PATH = $resolvedQmtPath
    $env:QMT_SESSION_ID = "$QmtSessionId"
    $env:QMT_GATEWAY_HOST = $GatewayHost
    $env:QMT_GATEWAY_PORT = "$GatewayPort"
    $env:QMT_CALLBACK_LOG_FILE = $CallbackLogFile
    if ([string]::IsNullOrWhiteSpace($env:PYTHONUTF8)) {
        $env:PYTHONUTF8 = "1"
    }
    if ([string]::IsNullOrWhiteSpace($env:PYTHONIOENCODING)) {
        $env:PYTHONIOENCODING = "utf-8"
    }

    Write-Host ""
    Write-Host "[INFO] Running doctor before startup..."
    Invoke-Python -PythonExe $pythonExe -Arguments @("-X", "utf8", "-m", "quant_qmt", "doctor", "--qmt-path", $resolvedQmtPath)
    Write-Host "[INFO] Starting quant-qmt gateway..."
    & $pythonExe -X utf8 -m quant_qmt gateway start --host $GatewayHost --port $GatewayPort --qmt-path $resolvedQmtPath --session-id $QmtSessionId --callback-log-file $CallbackLogFile
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "[NEXT] 1. Set QMT_PATH to your MiniQMT userdata_mini directory."
Write-Host "[NEXT] 2. Run quant-qmt doctor."
Write-Host "[NEXT] 3. Start the gateway with local mode or remote mode."
Write-Host ""
Write-Host "Recommended one-liners:"
Write-Host "  .\scripts\windows\bootstrap.ps1 -QmtPath 'C:\broker\MiniQMT\userdata_mini' -StartGateway"
Write-Host "  .\scripts\windows\bootstrap.ps1 -QmtPath 'C:\broker\MiniQMT\userdata_mini' -StartGateway -GatewayHost 0.0.0.0"
Write-Host ""

if (-not $xtquantOk) {
    Write-Host "[HINT] If your broker ships xtquant with MiniQMT, you can:"
    Write-Host "  - set QMT_XTQUANT_PATH to the broker-provided site-packages path"
    Write-Host "  - or only set QMT_PATH and let quant-qmt probe common MiniQMT install paths"
}
