# Install backend dependencies with the same Python that runs the server
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
py -3 -m pip install -r requirements.txt
