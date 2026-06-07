# Run Django on port 8001 (frontend expects http://localhost:8001/api)
# Use "py" launcher — "python" may be missing on Windows if not on PATH.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
py -3 manage.py runserver 8001
