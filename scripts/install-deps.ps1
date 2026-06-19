# Install backend dependencies into the project virtual environment.
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_lib.ps1")
Set-ProjectRootLocation

$python = Join-Path $ProjectRoot "venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    py -3 -m venv venv
    $python = Join-Path $ProjectRoot "venv\Scripts\python.exe"
}

& $python -m pip install -r requirements.txt
