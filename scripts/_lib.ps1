# Shared helpers for DuoBackend utility scripts.
$Script:ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Set-ProjectRootLocation {
    Set-Location $Script:ProjectRoot
}
