param([Parameter(Mandatory = $true)][string]$PackageRoot, [switch]$InstallPython)
$ErrorActionPreference = 'Stop'
function Find-Python { if (Get-Command py -ErrorAction SilentlyContinue) { try { & py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)"; if ($LASTEXITCODE -eq 0) { return @('py', '-3') } } catch {} }; if (Get-Command python -ErrorAction SilentlyContinue) { try { & python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)"; if ($LASTEXITCODE -eq 0) { return @('python') } } catch {} }; return $null }
function Invoke-Python { param([Parameter(ValueFromRemainingArguments = $true)][string[]]$PythonArguments); if ($python.Count -eq 2) { & $python[0] $python[1] @PythonArguments } else { & $python[0] @PythonArguments }; if ($LASTEXITCODE -ne 0) { throw "Python command failed: $LASTEXITCODE" } }
$python = @(Find-Python)
if ($python.Count -eq 0) { if (-not $InstallPython) { Write-Error 'Python 3.10+ is missing. Re-run with -InstallPython after authorizing system installation.'; exit 4 }; if (Get-Command winget -ErrorAction SilentlyContinue) { winget install --id Python.Python.3.12 -e --source winget --accept-package-agreements --accept-source-agreements } elseif (Get-Command choco -ErrorAction SilentlyContinue) { choco install python -y } elseif (Get-Command scoop -ErrorAction SilentlyContinue) { scoop install python } else { Write-Error 'No Windows package manager found. Install Python from https://www.python.org/downloads/windows/, then rerun.'; exit 4 }; $python = @(Find-Python); if ($python.Count -eq 0) { Write-Error 'Python is not yet available in this shell. Open a new PowerShell window and rerun.'; exit 4 } }
$runtime = Join-Path $PackageRoot '.runtime'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Invoke-Python -m venv $runtime
$runtimePython = Join-Path $runtime 'Scripts/python.exe'
& $runtimePython -m pip install --upgrade pip
& $runtimePython -m pip install -r (Join-Path $scriptDir '..\requirements.txt')
Write-Output $runtimePython
