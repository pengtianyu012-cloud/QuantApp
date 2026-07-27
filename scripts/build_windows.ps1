$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Spec = Join-Path $Root "A股量化模拟交易系统.spec"

if (-not (Test-Path $Python)) {
    throw "未找到虚拟环境 Python：$Python"
}
if (-not (Test-Path $Spec)) {
    throw "未找到 PyInstaller spec：$Spec"
}

& $Python -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('PyInstaller') else 1)"
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller 未安装。请先运行：.\.venv\Scripts\python.exe -m pip install -r requirements.txt"
}

& $Python -m PyInstaller --clean $Spec
