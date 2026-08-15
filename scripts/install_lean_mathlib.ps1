param(
    [Parameter(Mandatory = $true)][string]$Destination,
    [Parameter(Mandatory = $true)][string]$GitExe
)

$ErrorActionPreference = 'Stop'
$pluginRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$elanArchive = Join-Path $pluginRoot 'assets\payloads\elan-x86_64-pc-windows-msvc.zip'
$payloadManifest = Join-Path $pluginRoot 'assets\payload-manifest.json'
if (-not (Test-Path -LiteralPath $GitExe -PathType Leaf)) { throw "Registered Git executable is missing: $GitExe" }
if (-not (Test-Path -LiteralPath $elanArchive -PathType Leaf)) { throw "Bundled Elan archive is missing: $elanArchive" }

$manifest = Get-Content -LiteralPath $payloadManifest -Raw | ConvertFrom-Json
$record = $manifest.payloads | Where-Object { $_.name -eq 'elan-x86_64-pc-windows-msvc.zip' } | Select-Object -First 1
if ($null -eq $record) { throw 'Elan payload is not registered.' }
$actualHash = (Get-FileHash -LiteralPath $elanArchive -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualHash -ne ([string]$record.sha256).ToLowerInvariant()) { throw 'Elan payload SHA-256 mismatch.' }

New-Item -ItemType Directory -Force -Path $Destination | Out-Null
$elanHome = Join-Path $Destination 'elan'
$runtime = Join-Path $Destination 'runtime-v4.33.0'
$bootstrap = Join-Path $Destination 'bootstrap'
New-Item -ItemType Directory -Force -Path $elanHome,$runtime,$bootstrap | Out-Null
Expand-Archive -LiteralPath $elanArchive -DestinationPath $bootstrap -Force
$elanInit = Get-ChildItem -LiteralPath $bootstrap -Recurse -Filter 'elan-init.exe' | Select-Object -First 1
if ($null -eq $elanInit) { throw 'elan-init.exe was not found after extraction.' }

$env:ELAN_HOME = $elanHome
$env:PATH = "$(Split-Path -Parent $GitExe);$elanHome\bin;$env:PATH"
$env:HTTPS_PROXY = if ($env:RESEARCH_GUARD_FOREIGN_PROXY) { $env:RESEARCH_GUARD_FOREIGN_PROXY } else { 'http://127.0.0.1:7897' }
$env:HTTP_PROXY = $env:HTTPS_PROXY
& $elanInit.FullName -y --no-modify-path --default-toolchain none
if ($LASTEXITCODE -ne 0) { throw "Elan bootstrap failed with exit code $LASTEXITCODE" }
$elan = Join-Path $elanHome 'bin\elan.exe'
& $elan toolchain install 'leanprover/lean4:v4.33.0'
if ($LASTEXITCODE -ne 0) { throw "Lean toolchain installation failed with exit code $LASTEXITCODE" }

Set-Content -LiteralPath (Join-Path $runtime 'lean-toolchain') -Value 'leanprover/lean4:v4.33.0' -Encoding utf8
@'
name = "research_guard_lean_runtime"
version = "0.1.0"
defaultTargets = ["ResearchGuardSmoke"]

[[lean_lib]]
name = "ResearchGuardSmoke"

[[require]]
name = "mathlib"
scope = "leanprover-community"
rev = "v4.33.0"
'@ | Set-Content -LiteralPath (Join-Path $runtime 'lakefile.toml') -Encoding utf8
New-Item -ItemType Directory -Force -Path (Join-Path $runtime 'ResearchGuardSmoke') | Out-Null
@'
import Mathlib
set_option autoImplicit false
example (x : Nat) : x = x := by rfl
'@ | Set-Content -LiteralPath (Join-Path $runtime 'ResearchGuardSmoke\Basic.lean') -Encoding utf8

$lake = Join-Path $elanHome 'bin\lake.exe'
Push-Location $runtime
try {
    & $lake update
    if ($LASTEXITCODE -ne 0) { throw "lake update failed with exit code $LASTEXITCODE" }
    $lakeManifest = Get-Content -LiteralPath (Join-Path $runtime 'lake-manifest.json') -Raw | ConvertFrom-Json
    $mathlib = $lakeManifest.packages | Where-Object { $_.name -eq 'mathlib' } | Select-Object -First 1
    if ($null -eq $mathlib -or $mathlib.inputRev -ne 'v4.33.0' -or $mathlib.rev -ne 'db584cd6d46c92f209a44c0f1c829460d327499d') {
        throw 'Mathlib resolution did not match the audited tag and commit.'
    }
    & $lake exe cache get
    if ($LASTEXITCODE -ne 0) { throw "mathlib cache acquisition failed with exit code $LASTEXITCODE" }
    & $lake env lean 'ResearchGuardSmoke\Basic.lean'
    if ($LASTEXITCODE -ne 0) { throw "import Mathlib smoke failed with exit code $LASTEXITCODE" }
} finally {
    Pop-Location
}

$runtimeReceipt = [ordered]@{
    schema_version = 1
    toolchain = 'leanprover/lean4:v4.33.0'
    mathlib_tag = 'v4.33.0'
    mathlib_commit = 'db584cd6d46c92f209a44c0f1c829460d327499d'
    lake = $lake
    runtime_root = $runtime
}
$runtimeReceipt | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $Destination 'research-guard-lean-runtime.json') -Encoding utf8
