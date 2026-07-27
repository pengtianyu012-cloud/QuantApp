$ErrorActionPreference = "Stop"
$Python = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
& $Python -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('PyInstaller') else 1)"
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller 未安装。请先运行：.\.venv\Scripts\python.exe -m pip install -r requirements.txt"
}
& $Python -m PyInstaller --name "A股量化模拟交易系统" --windowed --clean (Join-Path $PSScriptRoot "..\main.py")
