$ErrorActionPreference = "Stop"
$Python = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
& $Python (Join-Path $PSScriptRoot "..\main.py")
