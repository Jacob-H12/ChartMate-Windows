param([switch]$CI)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$Root = (Get-Location).Path
function Run-Checked {
    param([string]$Exe, [string[]]$Arguments)
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Exe failed (exit $LASTEXITCODE). Build stopped; keep the error output." }
}
if ([Environment]::OSVersion.Platform -ne 'Win32NT') { throw 'Build on Windows x64, not macOS.' }
if ($env:PROCESSOR_ARCHITECTURE -ne 'AMD64') { throw 'Use native x64 Windows / PowerShell; ARM64 and 32-bit builds are not supported.' }
if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
    throw 'Install Node.js LTS, close this window and run again. See README_CN.md.'
}
$Python = $null
foreach ($Candidate in @('python.exe','py.exe')) {
    if (-not (Get-Command $Candidate -ErrorAction SilentlyContinue)) { continue }
    $Prefix = @(); if ($Candidate -eq 'py.exe') { $Prefix = @('-3.12') }
    $Probe = & $Candidate @Prefix -c 'import sys,struct;print(sys.executable if sys.version_info[:2]==(3,12) and struct.calcsize(chr(80))==8 else str())'
    if ($LASTEXITCODE -eq 0 -and $Probe) { $Python = [string]$Probe; break }
}
if (-not $Python) { throw 'Install Python 3.12 x64 (with the Python launcher), then run again. See README_CN.md.' }
Run-Checked $Python @('-m','venv','.build-venv')
$Py = Join-Path $Root '.build-venv\Scripts\python.exe'
Run-Checked $Py @('-m','pip','install','--disable-pip-version-check','pyinstaller>=6.11,<7')
Run-Checked 'npm.cmd' @('ci')
Run-Checked $Py @('scripts/prepare-windows.py')
$Redist = Join-Path $Root 'runtime\vc_redist.x64.exe'
$Signature = Get-AuthenticodeSignature -LiteralPath $Redist
if ($Signature.Status -ne 'Valid' -or $Signature.SignerCertificate.Subject -notmatch 'Microsoft Corporation') {
    throw 'Microsoft runtime signature verification failed. Do not run this downloaded file.'
}
# Also prepare the build PC; the installer performs this same prerequisite on the user's PC.
$InstallArgs = @{FilePath=$Redist; ArgumentList='/install /quiet /norestart'; Wait=$true; PassThru=$true}
if (-not $CI) { $InstallArgs.Verb = 'RunAs' }
$Installed = Start-Process @InstallArgs
if ($Installed.ExitCode -notin @(0,3010,1638)) { throw "Microsoft runtime installation failed: $($Installed.ExitCode)" }
Run-Checked $Py @('-m','PyInstaller','--noconfirm','--clean','--onedir','--console',
    '--name','chartmate-server','--distpath',"$Root\.build\python-dist",
    '--workpath',"$Root\.build\pyinstaller",'--specpath',"$Root\.build",
    '--paths',"$Root\backend",'--add-data',"$Root\backend\static;static","$Root\backend\desktop_entry.py")
if (Test-Path 'runtime\backend') { Remove-Item -Recurse -Force 'runtime\backend' }
Copy-Item -Recurse '.build\python-dist\chartmate-server' 'runtime\backend'
Run-Checked 'npm.cmd' @('test')
Run-Checked $Py @('-m','unittest','discover','-s','tests','-p','test_*.py','-v')
$Layout = Get-Content 'runtime\layout.json' -Raw | ConvertFrom-Json
$env:CHARTMATE_FFMPEG = Join-Path "$Root\runtime" $Layout.ffmpeg
Run-Checked $Py @('-m','unittest','discover','-s','backend','-v')
Remove-Item Env:CHARTMATE_FFMPEG
# Validate frozen binaries before making the installer, then validate packaged copies.
Run-Checked $Py @('scripts/audit-windows.py','runtime')
Run-Checked 'npm.cmd' @('run','dist')
Run-Checked $Py @('scripts/audit-windows.py','dist/win-unpacked/resources/runtime')
Write-Host 'Build complete. Test dist\win-unpacked\ChartMate.exe, then the Setup installer.'
Write-Host 'Unsigned test installer: distribution still needs a clean Windows PC test.'
if (-not $CI) { Start-Process explorer.exe -ArgumentList "`"$Root\dist`"" }
