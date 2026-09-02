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

$foreignProxy = $null
if ($env:RESEARCH_GUARD_FOREIGN_PROXY -ne $null) {
    $foreignProxy = $env:RESEARCH_GUARD_FOREIGN_PROXY.Trim()
} else {
    $networkHome = if ($env:RESEARCH_GUARD_HOME) { $env:RESEARCH_GUARD_HOME } else { Join-Path ([Environment]::GetFolderPath('UserProfile')) '.research-guard' }
    $networkConfigPath = Join-Path $networkHome 'network-config.json'
    if (Test-Path -LiteralPath $networkConfigPath -PathType Leaf) {
        try {
            $networkConfig = Get-Content -LiteralPath $networkConfigPath -Raw | ConvertFrom-Json
            if ($networkConfig.schema_version -ne 1) { throw 'unsupported schema' }
            $foreignProxy = [string]$networkConfig.foreign_proxy
            if ($networkConfig.configured -ne $null -and ([bool]$networkConfig.configured -ne [bool]$foreignProxy)) { throw 'configured does not match foreign_proxy' }
        } catch {
            throw "NETWORK_CONFIG_INVALID: $networkConfigPath"
        }
    }
}
if ($foreignProxy) {
    [Uri]$proxyUri = $null
    if (-not [Uri]::TryCreate($foreignProxy, [UriKind]::Absolute, [ref]$proxyUri) -or $proxyUri.Scheme.ToLowerInvariant() -notin @('http', 'https') -or [string]::IsNullOrWhiteSpace($proxyUri.Host) -or $proxyUri.UserInfo -or $proxyUri.Query -or $proxyUri.Fragment) {
        throw 'NETWORK_PROXY_INVALID: the foreign proxy must be a credential-free HTTP(S) URL.'
    }
    $foreignProxy = $foreignProxy.TrimEnd('/')
}
$proxyVariables = @('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY', 'http_proxy', 'https_proxy', 'all_proxy', 'no_proxy')
foreach ($variable in $proxyVariables) {
    Remove-Item -LiteralPath ("Env:" + $variable) -ErrorAction SilentlyContinue
}
$env:ELAN_HOME = $elanHome
$env:PATH = "$(Split-Path -Parent $GitExe);$elanHome\bin;$env:PATH"
if ($foreignProxy) {
    $env:HTTPS_PROXY = $foreignProxy
    $env:HTTP_PROXY = $foreignProxy
    $env:https_proxy = $foreignProxy
    $env:http_proxy = $foreignProxy
}
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
