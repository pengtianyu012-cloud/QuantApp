$ErrorActionPreference = "Stop"
$Python = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
& $Python -m compileall -q (Join-Path $Root "main.py") (Join-Path $Root "app") (Join-Path $Root "tests")
& $Python -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('ruff') else 1)"
if ($LASTEXITCODE -eq 0) {
    & $Python -m ruff check $Root
} else {
    Write-Host "ruff 未安装，已跳过 ruff 检查。请运行 pip install -r requirements.txt 后重试。"
}
