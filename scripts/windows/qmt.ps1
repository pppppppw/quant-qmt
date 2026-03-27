[CmdletBinding(PositionalBinding = $false)]
param(
    [string]$CondaEnv = "",
    [switch]$UseActivePython,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CliArgs
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

$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

if ([string]::IsNullOrWhiteSpace($CondaEnv)) {
    $CondaEnv = if ($env:CONDA_ENV) { $env:CONDA_ENV } else { "quant-qmt311" }
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

& $pythonExe -X utf8 -m quant_qmt @CliArgs
exit $LASTEXITCODE
