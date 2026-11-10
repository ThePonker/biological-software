# Builds the free-standing Lector: a PyInstaller folder, then (if Inno Setup is installed) the
# installer. Run from anywhere:
#   powershell -ExecutionPolicy Bypass -File "<suite>\packaging\lector\build_lector.ps1"
# Writes nothing inside the suite or OneDrive: the virtual environment and the build live in
# %LOCALAPPDATA%\LectorBuild. Nothing is deleted; a second run reuses the environment.
# Windows PowerShell 5.1 safe (no PowerShell 7 syntax, plain ASCII).

$ErrorActionPreference = 'Stop'

function Say($text) { Write-Host ("[Lector build] " + $text) }
function Fail($text) { Write-Host ("[Lector build] STOPPED: " + $text) -ForegroundColor Red; exit 1 }

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$suite = (Resolve-Path (Join-Path $here '..\..')).Path
$work = Join-Path $env:LOCALAPPDATA 'LectorBuild'
if ($suite -like '*OneDrive*') { Say 'The suite is inside OneDrive; the build itself goes to LOCALAPPDATA, outside it.' }
if ($work -like '*OneDrive*') { Fail 'LOCALAPPDATA is inside OneDrive; set LOCALAPPDATA to a local folder first.' }
New-Item -ItemType Directory -Force -Path $work | Out-Null

# 1. the virtual environment (outside OneDrive)
$venv = Join-Path $work 'venv'
$py = Join-Path $venv 'Scripts\python.exe'
if (-not (Test-Path $py)) {
    Say 'Making the virtual environment (py -3.14)...'
    & py -3.14 -m venv $venv
    if ($LASTEXITCODE -ne 0) { Fail 'Could not make the virtual environment. Is Python 3.14 installed (py -3.14)?' }
}
Say 'Installing PySide6, python-docx, openpyxl and PyInstaller (a few minutes the first time)...'
& $py -m pip install --upgrade pip
& $py -m pip install PySide6 python-docx openpyxl pyinstaller
if ($LASTEXITCODE -ne 0) { Fail 'pip could not install the packages. Check the internet connection and run again.' }

# 2. PyInstaller
$dist = Join-Path $work 'dist'
$build = Join-Path $work 'build'
$spec = Join-Path $here 'lector.spec'
Say 'Running PyInstaller...'
$env:PYTHONPATH = $suite + ';' + (Join-Path $suite 'Observatum')
& $py -m PyInstaller $spec --noconfirm --distpath $dist --workpath $build
if ($LASTEXITCODE -ne 0) { Fail 'PyInstaller failed. The messages above say which module it could not find; see BUILD.md.' }
$app = Join-Path $dist 'Lector'
if (-not (Test-Path (Join-Path $app 'Lector.exe'))) { Fail 'PyInstaller finished but Lector.exe is not there.' }
Say ('The program folder is ready: ' + $app)
Say ('Try it now: run ' + (Join-Path $app 'Lector.exe') + ' (its data goes to Documents\Lector\data).')

# 3. Inno Setup (optional)
$iscc = $null
foreach ($candidate in @(
        (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
        (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'))) {
    if ($candidate -and (Test-Path $candidate)) { $iscc = $candidate; break }
}
if (-not $iscc) {
    Say 'Inno Setup 6 is not installed, so no installer was made. The folder above works on its own.'
    Say 'To make the installer: install Inno Setup 6 from https://jrsoftware.org/isdl.php and run this script again.'
    exit 0
}
$out = Join-Path $work 'installer'
$version = (Get-Date -Format 'yyyyMMdd')
Say 'Running Inno Setup...'
& $iscc ('/DSourceDir=' + $app) ('/DOutputDir=' + $out) ('/DAppVersion=' + $version) (Join-Path $here 'lector.iss')
if ($LASTEXITCODE -ne 0) { Fail 'Inno Setup failed. The messages above say why.' }
Say ('Done. The installer is in ' + $out)
