$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Spec = Join-Path $Root "A股量化模拟交易系统.spec"
$RequiredPython = "3.13.2"

if (-not (Test-Path $Python)) {
    throw "未找到虚拟环境 Python：$Python"
}
if (-not (Test-Path $Spec)) {
    throw "未找到 PyInstaller spec：$Spec"
}

$ActualPython = & $Python -c "import platform; print(platform.python_version())"
if ($LASTEXITCODE -ne 0) {
    throw "无法读取虚拟环境 Python 版本"
}
$ActualPython = $ActualPython.Trim()
if ($ActualPython -ne $RequiredPython) {
    throw "Windows 构建要求 Python $RequiredPython，当前为 $ActualPython。请重建 .venv 后再构建。"
}

& $Python -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('PyInstaller') else 1)"
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller 未安装。请先运行：.\.venv\Scripts\python.exe -m pip install -r requirements.txt"
}

& $Python -m PyInstaller --clean --noconfirm $Spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller 构建失败，退出码：$LASTEXITCODE"
}
