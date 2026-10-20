$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$projectPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $projectPython)) {
    $existingPython = 'E:\MyFile\Codiing\Python\VirtualCloset\.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $existingPython) {
        $projectPython = $existingPython
    } else {
        $projectPython = 'python'
    }
}
& $projectPython -m streamlit run app.py
