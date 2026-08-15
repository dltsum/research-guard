param(
    [Parameter(Mandatory=$true)][string]$Archive,
    [Parameter(Mandatory=$true)][string]$TestRoot
)

$ErrorActionPreference = 'Stop'
$archivePath = [IO.Path]::GetFullPath($Archive)
$root = [IO.Path]::GetFullPath($TestRoot)
if (-not (Test-Path -LiteralPath $archivePath -PathType Leaf)) { throw 'Release archive does not exist.' }
if (Test-Path -LiteralPath $root) { throw 'Isolated test root must not already exist.' }
New-Item -ItemType Directory -Path $root | Out-Null
$extract = Join-Path $root 'extract'
$user = Join-Path $root 'user'
New-Item -ItemType Directory -Path $extract,$user | Out-Null
Expand-Archive -LiteralPath $archivePath -DestinationPath $extract
$package = Join-Path $extract 'research-guard'
$env:RESEARCH_GUARD_INSTALL_USER_ROOT = $user
$env:RESEARCH_GUARD_HOME = Join-Path $user '.research-guard'
$env:RESEARCH_GUARD_CODEX_ROOT = Join-Path $user '.codex'
$installOutput = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $package 'scripts\install.ps1') -SkipCodexRegistration
if ($LASTEXITCODE -ne 0) { throw 'Isolated installer failed.' }
$installedPython = Join-Path $env:RESEARCH_GUARD_HOME 'runtime\python\python.exe'
$verification = & $installedPython -I -X utf8 (Join-Path $package 'scripts\verify_isolated_install.py') --user-root $user
if ($LASTEXITCODE -ne 0) { throw 'Isolated installation verification failed.' }
[pscustomobject]@{
    status = 'PASS'
    archive = $archivePath
    install = ($installOutput | Out-String).Trim()
    verification = ($verification | ConvertFrom-Json)
} | ConvertTo-Json -Depth 10
