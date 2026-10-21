@echo off
setlocal DisableDelayedExpansion
title VirtualCloset
set "VC_LAUNCHER=%~f0"
set "VC_PROJECT=%~dp0"
set "VC_REPAIR=%~1"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "$src = [IO.File]::ReadAllText($env:VC_LAUNCHER); & ([scriptblock]::Create(($src -split '(?m)^# POWERSHELL_PAYLOAD\r?$', 2)[1]))"
set "VC_RESULT=%ERRORLEVEL%"
if not "%VC_RESULT%"=="0" (
    echo.
    echo VirtualCloset could not start. See the error above.
    pause
)
exit /b %VC_RESULT%
# POWERSHELL_PAYLOAD
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
# Keep pip and the app inside this project's environment.
$env:PYTHONNOUSERSITE = '1'
$env:PIP_DISABLE_PIP_VERSION_CHECK = '1'
$env:PYTHONUTF8 = '1'
Remove-Item Env:PYTHONHOME -ErrorAction SilentlyContinue
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue

function Invoke-Checked {
    param([string]$Exe, [string[]]$Arguments)
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed (exit $LASTEXITCODE): $Exe $($Arguments -join ' ')"
    }
}
function Test-Python {
    param([string]$Exe)
    try {
        & $Exe -c "import sys,struct,platform; sys.exit(0 if (3,11)<=sys.version_info[:2]<(3,14) and struct.calcsize('P')==8 and platform.machine().lower() in ('amd64','x86_64') else 1)" 2>$null | Out-Null
        return ($LASTEXITCODE -eq 0)
    } catch { return $false }
}
function Find-Python {
    # Use the Python launcher first, then known locations and PATH.
    $pyCommand = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($pyCommand) {
        foreach ($version in @('-3.13', '-3.12', '-3.11')) {
            try {
                $candidate = & $pyCommand.Source $version -c "import sys; print(sys.executable)" 2>$null
                if ($LASTEXITCODE -eq 0 -and $candidate -and (Test-Python ([string]$candidate))) {
                    return [string]$candidate
                }
            } catch {}
        }
    }
    foreach ($version in @('313', '312', '311')) {
        foreach ($base in @($env:LOCALAPPDATA, $env:ProgramFiles)) {
            if (-not $base) { continue }
            $relative = if ($base -eq $env:LOCALAPPDATA) { "Programs\Python\Python$version\python.exe" } else { "Python$version\python.exe" }
            $candidate = Join-Path $base $relative
            if ((Test-Path -LiteralPath $candidate) -and (Test-Python $candidate)) { return $candidate }
        }
    }
    $command = Get-Command python.exe -ErrorAction SilentlyContinue
    # Do not invoke the Windows Store alias, which can open the Store instead.
    if ($command -and $command.Source -notlike '*\WindowsApps\*' -and (Test-Python $command.Source)) {
        return $command.Source
    }
    return $null
}
function Select-TorchIndex {
    $smi = Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue
    $smiPath = if ($smi) { $smi.Source } else { Join-Path $env:SystemRoot 'System32\nvidia-smi.exe' }
    if (Test-Path -LiteralPath $smiPath) {
        try {
            $info = (& $smiPath 2>$null | Out-String)
            if ($LASTEXITCODE -eq 0 -and $info -match 'CUDA Version:\s*(\d+\.\d+)') {
                if ([version]$Matches[1] -ge [version]'12.6') {
                    return 'https://download.pytorch.org/whl/cu126'
                }
            }
        } catch {}
    }
    return 'https://download.pytorch.org/whl/cpu'
}
try {
    $root = [IO.Path]::GetFullPath($env:VC_PROJECT)
    Set-Location -LiteralPath $root
    Write-Host 'VirtualCloset - checking this computer...' -ForegroundColor Cyan
    foreach ($file in @('app.py', 'requirements.txt', 'virtual_closet\model.py', 'virtual_closet\database.py')) {
        if (-not (Test-Path -LiteralPath (Join-Path $root $file) -PathType Leaf)) {
            throw "Missing $file. Put this BAT in the complete project folder beside app.py, then try again."
        }
    }
    $venv = Join-Path $root '.venv'
    $python = Join-Path $venv 'Scripts\python.exe'
    if (-not ((Test-Path -LiteralPath $python) -and (Test-Python $python))) {
        $basePython = Find-Python
        if (-not $basePython) {
            $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
            if (-not $winget) {
                throw 'Python is missing and Windows Package Manager is unavailable. Install 64-bit Python 3.13 from https://www.python.org/downloads/windows/ and click this BAT again.'
            }
            Write-Host 'Installing Python 3.13 for your Windows account...'
            Invoke-Checked $winget.Source @('install', '--id', 'Python.Python.3.13', '--exact', '--source', 'winget', '--scope', 'user', '--architecture', 'x64', '--silent', '--accept-package-agreements', '--accept-source-agreements', '--disable-interactivity')
            $basePython = Find-Python
            if (-not $basePython) { throw 'Python was installed but could not be found. Close this window and run the BAT again.' }
        }
        if (Test-Path -LiteralPath $venv) {
            # Validate the exact target before renaming a copied/broken environment.
            $resolved = [IO.Path]::GetFullPath($venv)
            $expected = [IO.Path]::GetFullPath((Join-Path $root '.venv'))
            if ($resolved -ne $expected -or (Split-Path $resolved -Parent).TrimEnd('\') -ne $root.TrimEnd('\')) {
                throw 'Environment path validation failed.'
            }
            $backupName = '.venv.backup_' + [DateTime]::Now.ToString('yyyyMMdd_HHmmss_fff')
            Write-Host "Preserving the incompatible environment as $backupName"
            Rename-Item -LiteralPath $venv -NewName $backupName
        }
        Write-Host 'Creating this project''s .venv...'
        Invoke-Checked $basePython @('-m', 'venv', $venv)
        if (-not (Test-Python $python)) { throw 'The new Python environment could not run.' }
    }
    $requirements = Join-Path $root 'requirements.txt'
    $marker = Join-Path $venv '.virtualcloset_setup'
    $fingerprint = (Get-FileHash -LiteralPath $requirements -Algorithm SHA256).Hash + ':' + (Get-FileHash -LiteralPath $env:VC_LAUNCHER -Algorithm SHA256).Hash
    $installed = ''
    if (Test-Path -LiteralPath $marker) { $installed = (Get-Content -LiteralPath $marker -Raw).Trim() }
    # Fast metadata check: no model loads and no package downloads on normal launches.
    $metadataCheck = @'
import sys
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path
try:
    from packaging.requirements import Requirement
    required = [Requirement(x.split("#",1)[0].strip()) for x in Path(sys.argv[1]).read_text(encoding="utf-8-sig").splitlines() if x.split("#",1)[0].strip()]
    for r in required:
        if r.marker is None or r.marker.evaluate():
            assert version(r.name) in r.specifier
    for name in ("torch", "torchvision", "onnxruntime"):
        version(name)
except Exception:
    sys.exit(1)
'@
    # Send Python source through stdin: Windows PowerShell 5 strips embedded
    # double quotes when multiline source is passed as a native -c argument.
    $metadataCheck | & $python - $requirements
    $metadataOK = ($LASTEXITCODE -eq 0)
    if ($installed -ne $fingerprint -or -not $metadataOK -or $env:VC_REPAIR -eq '--repair') {
        if (Test-Path -LiteralPath $marker) { Remove-Item -LiteralPath $marker }
        Write-Host 'Preparing dependencies. First-time setup needs internet and may take several minutes.' -ForegroundColor Cyan
        Invoke-Checked $python @('-m', 'ensurepip', '--upgrade')
        Invoke-Checked $python @('-m', 'pip', 'install', '--upgrade', 'pip')
        $torchCheck = @'
import sys
try:
    import torch, torchvision
except Exception:
    sys.exit(1)
'@
        $torchCheck | & $python -
        if ($LASTEXITCODE -ne 0) {
            $index = Select-TorchIndex
            Write-Host "Installing PyTorch from $index"
            & $python -m pip install --upgrade 'torch==2.9.1' 'torchvision==0.24.1' --index-url $index
            if ($LASTEXITCODE -ne 0 -and $index -like '*/cu126') {
                Write-Host 'NVIDIA package installation failed. Trying the CPU packages...'
                Invoke-Checked $python @('-m', 'pip', 'install', '--upgrade', 'torch==2.9.1', 'torchvision==0.24.1', '--index-url', 'https://download.pytorch.org/whl/cpu')
            } elseif ($LASTEXITCODE -ne 0) { throw 'PyTorch installation failed. Check the pip error above.' }
        }
        Invoke-Checked $python @('-m', 'pip', 'install', '-r', $requirements)
        # Required by the updated app even if an old requirements.txt is copied.
        Invoke-Checked $python @('-m', 'pip', 'install', 'rembg[cpu]>=2.0.67,<3')
        Invoke-Checked $python @('-m', 'pip', 'check')
        Write-Host 'Checking image processing, recognition, and tab support...'
        $smoke = @'
import inspect
import torch, torchvision, onnxruntime, rembg, streamlit
from PIL import Image
from transformers import CLIPModel, CLIPProcessor
from virtual_closet import model, images, database, recommendation
assert "key" in inspect.signature(streamlit.tabs).parameters and "on_change" in inspect.signature(streamlit.tabs).parameters, "Update requirements.txt to streamlit==1.66.0 for this app's tabs."
print("Dependency check passed. FashionCLIP device:", "CUDA" if torch.cuda.is_available() else "CPU")
'@
        $smoke | & $python -
        if ($LASTEXITCODE -ne 0) { throw 'Dependency check failed. See the Python error above.' }
        [IO.File]::WriteAllText($marker, $fingerprint)
    } else {
        Write-Host 'Dependencies are ready. Skipping installation.'
    }
    Write-Host ''
    Write-Host 'Starting VirtualCloset. Keep this window open while using the app.' -ForegroundColor Green
    Write-Host 'FashionCLIP and rembg download model weights on first use, then reuse their cache.'
    Write-Host 'Press Ctrl+C here to stop the app.'
    Invoke-Checked $python @('-m', 'streamlit', 'run', (Join-Path $root 'app.py'), '--server.address', 'localhost', '--server.headless', 'false')
    exit 0
} catch {
    Write-Host ''
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host 'If a DLL is missing, install the Microsoft Visual C++ 2015-2022 x64 Redistributable.'
    Write-Host 'After correcting the issue, click the BAT again. Existing closet data is preserved.'
    exit 1
}
