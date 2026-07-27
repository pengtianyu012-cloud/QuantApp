$ErrorActionPreference = "Stop"
$Python = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
& $Python -m unittest discover -s (Join-Path $PSScriptRoot "..\tests")
