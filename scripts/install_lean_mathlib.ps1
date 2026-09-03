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
$proxyVariables = @(
    'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY', 'http_proxy', 'https_proxy', 'all_proxy', 'no_proxy',
    'PIP_INDEX_URL', 'PIP_EXTRA_INDEX_URL', 'PIP_TRUSTED_HOST', 'PIP_NO_INDEX', 'PIP_FIND_LINKS',
    'PIP_CONFIG_FILE', 'PIP_CERT', 'PIP_CLIENT_CERT', 'UV_INDEX_URL', 'UV_EXTRA_INDEX_URL', 'UV_FIND_LINKS',
    'PYTHONHOME', 'PYTHONPATH', 'PYTHONUSERBASE', 'PYTHONSTARTUP', 'PYTHONEXECUTABLE',
    'PYTHONIOENCODING', 'PYTHONWARNINGS', 'PYTHONBREAKPOINT', 'PYTHONUTF8'
)
foreach ($variable in $proxyVariables) {
    Remove-Item -LiteralPath ("Env:" + $variable) -ErrorAction SilentlyContinue
}
# The bootstrap invokes Git indirectly through Lake.  Ignore per-machine Git
# config/include/url rewrites so a copied install cannot follow the builder's
# credentials, proxy, or repository aliases.  The selected Git executable and
# explicit proxy route remain the only inputs to this installer.
$env:GIT_CONFIG_NOSYSTEM = '1'
$env:GIT_CONFIG_GLOBAL = 'NUL'
$env:GIT_CONFIG_SYSTEM = 'NUL'
$env:GIT_TERMINAL_PROMPT = '0'
$env:ELAN_HOME = $elanHome
$env:PATH = "$(Split-Path -Parent $GitExe);$elanHome\bin;$env:PATH"

# Every remote Lean/Lake operation gets the same explicit route policy as the
# Python scholarly clients.  A configured proxy is attempted first; only a
# recognisable transport failure permits the direct fallback.  Semantic
# command errors (bad revisions, malformed projects, etc.) are not retried.
$networkRoutes = @()
if ($foreignProxy) {
    $networkRoutes += @{ Name = 'foreign-proxy'; Proxy = $foreignProxy }
    $disableDirectFallback = [string]$env:RESEARCH_GUARD_DISABLE_FOREIGN_DIRECT_FALLBACK
    if ($disableDirectFallback.Trim().ToLowerInvariant() -notin @('1', 'true', 'yes', 'on')) {
        $networkRoutes += @{ Name = 'foreign-direct-fallback'; Proxy = $null }
    }
} else {
    $networkRoutes += @{ Name = 'foreign-direct'; Proxy = $null }
}

$script:networkRoutesAttempted = @()
$script:networkRoutesUsed = @()

function Set-NetworkRoute {
    param([AllowNull()][string]$Proxy)
    foreach ($variable in $proxyVariables) {
        Remove-Item -LiteralPath ("Env:" + $variable) -ErrorAction SilentlyContinue
    }
    if ($Proxy) {
        $env:HTTPS_PROXY = $Proxy
        $env:HTTP_PROXY = $Proxy
        $env:https_proxy = $Proxy
        $env:http_proxy = $Proxy
    }
}

function Test-TransportFailure {
    param([AllowNull()][string]$Text)
    if (-not $Text) { return $false }
    # Elan/Lake emit provider-specific wording; this list intentionally covers
    # transport symptoms only, not arbitrary non-zero exits.
    return $Text -match '(?i)(timed?\s*out|timeout|(?:connection|connect(?:ion)?)\s+(?:refused|reset|failed|error|closed|timed?\s*out)|dns|name or service not known|network is unreachable|no route to host|(?:proxy|tls|ssl)\s*(?:error|failure|handshake|connect|connection)|handshake|unexpected eof|reset by peer|failed to download|unable to access|could not resolve|temporary failure in name resolution)'
}

function Invoke-NetworkStep {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][string[]]$Command
    )
    $attempted = @()
    $failures = @()
    foreach ($route in $networkRoutes) {
        $attempted += [string]$route.Name
        $script:networkRoutesAttempted += [string]$route.Name
        Set-NetworkRoute ([string]$route.Proxy)
        $executable = $Command[0]
        $arguments = @()
        if ($Command.Count -gt 1) { $arguments = $Command[1..($Command.Count - 1)] }
        $output = @(& $executable @arguments 2>&1)
        $exitCode = $LASTEXITCODE
        $output | ForEach-Object { Write-Output $_ }
        if ($exitCode -eq 0) {
            $script:networkRoutesUsed += [string]$route.Name
            return
        }
        $detail = (($output | ForEach-Object { [string]$_ }) -join "`n").Trim()
        $failures += "$($route.Name)=exit ${exitCode}: $detail"
        $hasNext = $attempted.Count -lt $networkRoutes.Count
        if (-not $hasNext -or -not (Test-TransportFailure $detail)) {
            throw "$Label failed via $($route.Name) (exit $exitCode): $detail"
        }
    }
    throw "$Label failed after routes [$($attempted -join ', ')]: $($failures -join '; ')"
}

# The bootstrap executable is local; do not carry a proxy into it.  Remote
# toolchain/cache operations below select and record their own route.
Set-NetworkRoute $null
& $elanInit.FullName -y --no-modify-path --default-toolchain none
if ($LASTEXITCODE -ne 0) { throw "Elan bootstrap failed with exit code $LASTEXITCODE" }
$elan = Join-Path $elanHome 'bin\elan.exe'
Invoke-NetworkStep -Label 'Lean toolchain installation' -Command @($elan, 'toolchain', 'install', 'leanprover/lean4:v4.33.0')

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
    Invoke-NetworkStep -Label 'lake update' -Command @($lake, 'update')
    $lakeManifest = Get-Content -LiteralPath (Join-Path $runtime 'lake-manifest.json') -Raw | ConvertFrom-Json
    $mathlib = $lakeManifest.packages | Where-Object { $_.name -eq 'mathlib' } | Select-Object -First 1
    if ($null -eq $mathlib -or $mathlib.inputRev -ne 'v4.33.0' -or $mathlib.rev -ne 'db584cd6d46c92f209a44c0f1c829460d327499d') {
        throw 'Mathlib resolution did not match the audited tag and commit.'
    }
    Invoke-NetworkStep -Label 'mathlib cache acquisition' -Command @($lake, 'exe', 'cache', 'get')
    Set-NetworkRoute $null
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
    network_routes_attempted = @($script:networkRoutesAttempted)
    network_routes_used = @($script:networkRoutesUsed)
    network_route = if ($script:networkRoutesUsed.Count -gt 0) { $script:networkRoutesUsed[-1] } else { $null }
}
$runtimeReceipt | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $Destination 'research-guard-lean-runtime.json') -Encoding utf8
