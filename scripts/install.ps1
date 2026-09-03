param(
    [ValidateSet('install', 'update', 'clean', 'hard-clean')]
    [string]$Command = 'install',
    [string]$ProjectRoot,
    [Alias('Home')]
    [string]$GuardHome,
    [string]$UserRoot,
    [string]$CodexHome,
    [switch]$DryRun,
    [switch]$Cancel,
    [switch]$Resume,
    [switch]$SkipCodexRegistration,
    [AllowNull()]
    [string]$ForeignProxy
)

$ErrorActionPreference = 'Stop'
function Assert-MemoryHeadroom([int64]$MinimumBytes) {
    $os = Get-CimInstance Win32_OperatingSystem
    $freeBytes = [int64]$os.FreePhysicalMemory * 1KB
    if ($freeBytes -lt $MinimumBytes) {
        throw ('RESOURCE_HEADROOM_INSUFFICIENT: available RAM is {0:N0} MiB; at least {1:N0} MiB is required.' -f ($freeBytes/1MB),($MinimumBytes/1MB))
    }
}
function Invoke-OrchestratorCheckpoint([int64]$MaximumBytes) {
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
    [GC]::Collect()
    $workingSet = (Get-Process -Id $PID).WorkingSet64
    if ($workingSet -gt $MaximumBytes) {
        throw ('RESOURCE_ORCHESTRATOR_LIMIT: installer uses {0:N0} MiB; limit is {1:N0} MiB.' -f ($workingSet/1MB),($MaximumBytes/1MB))
    }
}
function Normalize-ForeignProxy([AllowNull()][string]$Value) {
    if ([string]::IsNullOrWhiteSpace($Value)) { return $null }
    $text = $Value.Trim()
    [Uri]$uri = $null
    if (-not [Uri]::TryCreate($text, [UriKind]::Absolute, [ref]$uri)) {
        throw 'NETWORK_PROXY_INVALID: ForeignProxy must be a credential-free HTTP(S) proxy URL.'
    }
    if ($uri.Scheme.ToLowerInvariant() -notin @('http', 'https') -or [string]::IsNullOrWhiteSpace($uri.Host) -or $uri.UserInfo -or $uri.Query -or $uri.Fragment) {
        throw 'NETWORK_PROXY_INVALID: ForeignProxy must be a credential-free HTTP(S) proxy URL.'
    }
    return $text.TrimEnd('/')
}
function Write-NetworkConfig([string]$Path, [AllowNull()][string]$Proxy) {
    $parent = Split-Path -Parent $Path
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $value = [ordered]@{
        schema_version = 1
        foreign_proxy = $Proxy
        configured = [bool]$Proxy
        source = 'installer'
        updated_at = [DateTime]::UtcNow.ToString('o')
    }
    $temporary = $Path + '.tmp-' + [guid]::NewGuid().ToString('N')
    try {
        $value | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $temporary -Encoding utf8
        Move-Item -LiteralPath $temporary -Destination $Path -Force
    } finally {
        if (Test-Path -LiteralPath $temporary) {
            Remove-Item -LiteralPath $temporary -Force -ErrorAction SilentlyContinue
        }
    }
}
function Write-McpConfig([string]$PluginPath, [string]$PythonPath) {
    # The source declaration intentionally uses a neutral ``python`` launcher.
    # An installed copy binds to the runtime selected by this installation so
    # another host never inherits the builder's PATH or interpreter.
    $value = [ordered]@{
        mcpServers = [ordered]@{
            'research-guard' = [ordered]@{
                command = $PythonPath
                args = @('-X', 'utf8', (Join-Path $PluginPath 'scripts\mcp_server.py'))
            }
        }
    }
    $value | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $PluginPath '.mcp.json') -Encoding utf8
}
$packageRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
# Bundled Python must not read the invoking host's startup/path variables.
foreach ($variable in @(
    'PYTHONHOME', 'PYTHONPATH', 'PYTHONUSERBASE', 'PYTHONSTARTUP', 'PYTHONEXECUTABLE',
    'PYTHONIOENCODING', 'PYTHONWARNINGS', 'PYTHONBREAKPOINT', 'PYTHONUTF8'
)) {
    Remove-Item -LiteralPath "Env:$variable" -ErrorAction SilentlyContinue
}

# Maintenance commands intentionally bypass release/payload checks: cleaning
# must remain available after the optional payloads have been pruned.  The
# Python helper records one short unit per path and can be rerun after an
# interruption.  ``update`` is deliberately the same idempotent install path.
$maintenanceUserRoot = if ($UserRoot) {
    [IO.Path]::GetFullPath($UserRoot)
} elseif ($env:RESEARCH_GUARD_INSTALL_USER_ROOT) {
    [IO.Path]::GetFullPath($env:RESEARCH_GUARD_INSTALL_USER_ROOT)
} else {
    [Environment]::GetFolderPath('UserProfile')
}
if ($GuardHome) {
    $maintenanceHome = [IO.Path]::GetFullPath($GuardHome)
} elseif ($env:RESEARCH_GUARD_HOME) {
    $maintenanceHome = [IO.Path]::GetFullPath($env:RESEARCH_GUARD_HOME)
} else {
    $maintenanceHome = Join-Path $maintenanceUserRoot '.research-guard'
}
if ($Command -in @('clean', 'hard-clean') -or $Cancel -or $Resume) {
    $pythonCandidate = if ($env:RESEARCH_GUARD_PYTHON) {
        [IO.Path]::GetFullPath($env:RESEARCH_GUARD_PYTHON)
    } else {
        Join-Path $maintenanceHome 'runtime\python\python.exe'
    }
    if (-not (Test-Path -LiteralPath $pythonCandidate -PathType Leaf)) {
        $pythonCommand = Get-Command py -ErrorAction SilentlyContinue
        if ($null -eq $pythonCommand) { $pythonCommand = Get-Command python -ErrorAction SilentlyContinue }
        if ($null -eq $pythonCommand) { throw 'A Python interpreter is required for maintenance commands.' }
        $pythonCandidate = $pythonCommand.Source
    }
    $maintenanceArgs = @('-X', 'utf8', (Join-Path $packageRoot 'scripts\dependency_manager.py'))
    if ($Command -in @('clean', 'hard-clean')) {
        $maintenanceArgs += $Command
        if ($ProjectRoot) { $maintenanceArgs += @('--project-root', $ProjectRoot) }
        if ($GuardHome) { $maintenanceArgs += @('--home', $GuardHome) }
        if ($DryRun) { $maintenanceArgs += '--dry-run' }
        if ($Cancel) { $maintenanceArgs += '--cancel' }
    } elseif ($Cancel) {
        $maintenanceArgs += 'cancel'
    } else {
        $maintenanceArgs += 'resume'
    }
    & $pythonCandidate @maintenanceArgs
    exit $LASTEXITCODE
}
$resourcePolicyPath = Join-Path $packageRoot 'assets\resource-policy.json'
if (-not (Test-Path -LiteralPath $resourcePolicyPath -PathType Leaf)) { throw 'assets/resource-policy.json is required.' }
$resourcePolicy = Get-Content -LiteralPath $resourcePolicyPath -Raw | ConvertFrom-Json
if ($resourcePolicy.schema_version -ne 1 -or $resourcePolicy.maximum_parallel_workers -ne 1 -or $resourcePolicy.gpu_allowed -ne $false) {
    throw 'RESOURCE_POLICY_INVALID: only the serial CPU policy is supported.'
}
if ([int64]$resourcePolicy.worker_job_limit_bytes + [int64]$resourcePolicy.orchestrator_reserve_bytes -gt [int64]$resourcePolicy.owned_task_budget_bytes) {
    throw 'RESOURCE_POLICY_INVALID: worker plus orchestrator exceeds the owned-task budget.'
}
if ([int64]$resourcePolicy.install_worker_limit_bytes + [int64]$resourcePolicy.install_orchestrator_reserve_bytes -gt [int64]$resourcePolicy.owned_task_budget_bytes) {
    throw 'RESOURCE_POLICY_INVALID: installer worker plus orchestrator exceeds the owned-task budget.'
}
if ([int64]$resourcePolicy.lean_worker_limit_bytes + [int64]$resourcePolicy.lean_orchestrator_reserve_bytes -gt [int64]$resourcePolicy.owned_task_budget_bytes) {
    throw 'RESOURCE_POLICY_INVALID: Lean worker plus orchestrator exceeds the owned-task budget.'
}
if ([int64]$resourcePolicy.windows_installer_checkpoint_bytes -lt [int64]$resourcePolicy.orchestrator_reserve_bytes -or [int64]$resourcePolicy.windows_installer_checkpoint_bytes -gt [int64]$resourcePolicy.install_worker_limit_bytes) {
    throw 'RESOURCE_POLICY_INVALID: Windows installer checkpoint must cover the PowerShell process and remain inside the installer worker limit.'
}
if ([string]$resourcePolicy.memory_metric -ne 'aggregate_working_set' -or [double]$resourcePolicy.sampling_interval_seconds -gt 0.01) {
    throw 'RESOURCE_POLICY_INVALID: aggregate working-set sampling must be enabled at 10 ms or faster.'
}
$installerCheckpointBytes = [int64]$resourcePolicy.windows_installer_checkpoint_bytes
Assert-MemoryHeadroom ([int64]$resourcePolicy.start_min_free_bytes)
Invoke-OrchestratorCheckpoint $installerCheckpointBytes
$manifestPath = Join-Path $packageRoot 'RELEASE_MANIFEST.json'
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw 'RELEASE_MANIFEST.json is required. Install from the built migration archive, not the development source tree.'
}

$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ($manifest.package -ne 'research-guard' -or $manifest.variant -ne 'windows-x64-modular' -or $manifest.platform -ne 'windows-x64' -or $manifest.runtime_delivery -ne 'bundled-python') {
    throw 'This installer only accepts the Research Guard windows-x64-modular release.'
}
foreach ($file in $manifest.files) {
    $path = Join-Path $packageRoot ([string]$file.path)
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Release file is missing: $($file.path)" }
    $item = Get-Item -LiteralPath $path
    if ($item.Length -ne [int64]$file.bytes) { throw "Release file size mismatch: $($file.path)" }
    $hash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($hash -ne ([string]$file.sha256).ToLowerInvariant()) { throw "Release file SHA-256 mismatch: $($file.path)" }
    Invoke-OrchestratorCheckpoint $installerCheckpointBytes
}

$userRoot = if ($UserRoot) {
    [IO.Path]::GetFullPath($UserRoot)
} elseif ($env:RESEARCH_GUARD_INSTALL_USER_ROOT) {
    [IO.Path]::GetFullPath($env:RESEARCH_GUARD_INSTALL_USER_ROOT)
} else {
    [Environment]::GetFolderPath('UserProfile')
}
$guardHome = if ($GuardHome) {
    [IO.Path]::GetFullPath($GuardHome)
} elseif ($env:RESEARCH_GUARD_HOME) {
    [IO.Path]::GetFullPath($env:RESEARCH_GUARD_HOME)
} else {
    Join-Path $userRoot '.research-guard'
}
$codexHome = if ($CodexHome) {
    [IO.Path]::GetFullPath($CodexHome)
} elseif ($env:RESEARCH_GUARD_CODEX_ROOT) {
    [IO.Path]::GetFullPath($env:RESEARCH_GUARD_CODEX_ROOT)
} elseif ($env:CODEX_HOME) {
    [IO.Path]::GetFullPath($env:CODEX_HOME)
} else {
    Join-Path $userRoot '.codex'
}
$pluginTarget = Join-Path $userRoot 'plugins\research-guard'
$skillTarget = Join-Path $codexHome 'skills\research-guard'
$runtimeTarget = Join-Path $guardHome 'runtime\python'
$payload = Join-Path $packageRoot 'assets\payloads\python-runtime.zip'
$networkConfigPath = Join-Path $guardHome 'network-config.json'
$networkConfigExisted = Test-Path -LiteralPath $networkConfigPath -PathType Leaf
$networkConfigBackup = Join-Path ([IO.Path]::GetTempPath()) ('rg-network-' + [guid]::NewGuid().ToString('N') + '.json')
$networkConfigTouched = $false
$proxyChoiceMade = $true
$foreignProxy = $null
if ($PSBoundParameters.ContainsKey('ForeignProxy')) {
    $foreignProxy = Normalize-ForeignProxy $ForeignProxy
} elseif ($networkConfigExisted) {
    try {
        $savedNetworkConfig = Get-Content -LiteralPath $networkConfigPath -Raw | ConvertFrom-Json
        if ($savedNetworkConfig.schema_version -ne 1) { throw 'unsupported schema' }
        $foreignProxy = Normalize-ForeignProxy ([string]$savedNetworkConfig.foreign_proxy)
        if ($null -ne $savedNetworkConfig.configured -and ([bool]$savedNetworkConfig.configured -ne [bool]$foreignProxy)) {
            throw 'configured does not match foreign_proxy'
        }
        $proxyChoiceMade = $false
    } catch {
        throw "NETWORK_CONFIG_INVALID: $networkConfigPath"
    }
} elseif (-not [Console]::IsInputRedirected -and -not [Console]::IsOutputRedirected) {
    $answer = Read-Host 'Optional foreign-source proxy URL (Enter for direct)'
    $foreignProxy = Normalize-ForeignProxy $answer
}

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $pluginTarget),(Split-Path -Parent $skillTarget),(Split-Path -Parent $runtimeTarget) | Out-Null

$stagingRoot = Join-Path ([IO.Path]::GetTempPath()) ('rg-' + [guid]::NewGuid().ToString('N').Substring(0,8))
$pluginStage = Join-Path $stagingRoot 'plugin'
$runtimeStage = Join-Path $stagingRoot 'python'
$skillStage = Join-Path $stagingRoot 'skill'
$pluginBackup = Join-Path $stagingRoot 'backup-plugin'
$runtimeBackup = Join-Path $stagingRoot 'backup-runtime'
$skillBackup = Join-Path $stagingRoot 'backup-skill'
$coreReceiptPath = Join-Path $guardHome 'dependencies\components\core-runtime.json'
$coreReceiptBackup = Join-Path $stagingRoot 'backup-core-runtime.json'
$coreReceiptExisted = Test-Path -LiteralPath $coreReceiptPath -PathType Leaf
$marketplaceDirectory = Join-Path $userRoot '.agents\plugins'
$marketplacePath = Join-Path $marketplaceDirectory 'marketplace.json'
$marketplaceBackup = Join-Path $stagingRoot 'backup-marketplace.json'
$marketplaceExisted = Test-Path -LiteralPath $marketplacePath -PathType Leaf
$marketplaceTouched = $false
$codexRegistration = if ($SkipCodexRegistration) { 'SKIPPED_BY_FLAG' } else { 'CODEX_NOT_FOUND' }
$pluginSwapped = $false
$runtimeSwapped = $false
$skillSwapped = $false
New-Item -ItemType Directory -Force -Path $pluginStage,$skillStage | Out-Null
try {
    if ($coreReceiptExisted) { Copy-Item -LiteralPath $coreReceiptPath -Destination $coreReceiptBackup -Force }
    if ($marketplaceExisted) { Copy-Item -LiteralPath $marketplacePath -Destination $marketplaceBackup -Force }
    if ($networkConfigExisted) { Copy-Item -LiteralPath $networkConfigPath -Destination $networkConfigBackup -Force }
    foreach ($entry in Get-ChildItem -LiteralPath $packageRoot -Force) {
        Copy-Item -LiteralPath $entry.FullName -Destination $pluginStage -Recurse -Force
        Invoke-OrchestratorCheckpoint $installerCheckpointBytes
    }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::ExtractToDirectory($payload, $runtimeStage)
    Invoke-OrchestratorCheckpoint $installerCheckpointBytes
    $python = Join-Path $runtimeStage 'python.exe'
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'Bundled Python extraction did not create python.exe.' }
    $env:OPENBLAS_NUM_THREADS = '1'
    $env:OMP_NUM_THREADS = '1'
    $env:MKL_NUM_THREADS = '1'
    $env:NUMEXPR_NUM_THREADS = '1'
    $env:MPLBACKEND = 'Agg'
    $smokeRunner = Join-Path $stagingRoot 'bounded_core_import_smoke.py'
    @'
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(sys.argv[1]).resolve()))
from resource_guard import run_managed_light
from network_config_core import network_environment

result = run_managed_light(
    [sys.executable, "-X", "utf8", "-c", "import matplotlib,numpy,PIL,pypdf,networkx,optuna,pint,sympy,z3; print('CORE_IMPORT_PASS')"],
    env=network_environment(proxy=None), timeout=120,
)
if result.returncode != 0 or "CORE_IMPORT_PASS" not in result.stdout:
    raise SystemExit("Bundled Python dependency smoke failed: " + (result.stderr or result.stdout)[-2000:])
print("CORE_IMPORT_PASS")
'@ | Set-Content -LiteralPath $smokeRunner -Encoding ascii
    & $python -X utf8 $smokeRunner (Join-Path $pluginStage 'scripts')
    if ($LASTEXITCODE -ne 0) { throw 'Bundled Python bounded dependency smoke failed.' }
    Invoke-OrchestratorCheckpoint $installerCheckpointBytes

    Copy-Item -LiteralPath (Join-Path $pluginStage 'SKILL.md') -Destination (Join-Path $skillStage 'SKILL.md') -Force
    foreach ($directory in @('agents','references')) {
        Copy-Item -LiteralPath (Join-Path $pluginStage $directory) -Destination (Join-Path $skillStage $directory) -Recurse -Force
    }
    Invoke-OrchestratorCheckpoint $installerCheckpointBytes

    if (Test-Path -LiteralPath $pluginTarget) {
        Move-Item -LiteralPath $pluginTarget -Destination $pluginBackup
    }
    Move-Item -LiteralPath $pluginStage -Destination $pluginTarget
    $pluginSwapped = $true
    if (Test-Path -LiteralPath $runtimeTarget) {
        Move-Item -LiteralPath $runtimeTarget -Destination $runtimeBackup
    }
    Move-Item -LiteralPath $runtimeStage -Destination $runtimeTarget
    $runtimeSwapped = $true

    if (Test-Path -LiteralPath $skillTarget) {
        Move-Item -LiteralPath $skillTarget -Destination $skillBackup
    }
    Move-Item -LiteralPath $skillStage -Destination $skillTarget
    $skillSwapped = $true

    $installedPython = Join-Path $runtimeTarget 'python.exe'
    Write-McpConfig $pluginTarget $installedPython
    & $installedPython -X utf8 (Join-Path $pluginTarget 'scripts\dependency_manager.py') register-core $runtimeTarget
    if ($LASTEXITCODE -ne 0) { throw 'Core dependency registration failed.' }

    if (-not $SkipCodexRegistration) {
        $codex = Get-Command codex -ErrorAction SilentlyContinue
        if ($null -ne $codex) {
            New-Item -ItemType Directory -Force -Path $marketplaceDirectory | Out-Null
            if (Test-Path -LiteralPath $marketplacePath) {
                $marketplace = Get-Content -LiteralPath $marketplacePath -Raw | ConvertFrom-Json
            } else {
                $marketplace = [pscustomobject]@{
                    name = 'personal'
                    interface = [pscustomobject]@{ displayName = 'Personal' }
                    plugins = @()
                }
            }
            $others = @($marketplace.plugins | Where-Object { $_.name -ne 'research-guard' })
            $entry = [pscustomobject]@{
                name = 'research-guard'
                source = [pscustomobject]@{ source = 'local'; path = './plugins/research-guard' }
                policy = [pscustomobject]@{ installation = 'AVAILABLE'; authentication = 'ON_INSTALL' }
                category = 'Productivity'
            }
            $marketplace.plugins = @($others + $entry)
            $marketplaceTemporary = $marketplacePath + '.tmp-' + [guid]::NewGuid().ToString('N')
            $marketplace | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $marketplaceTemporary -Encoding utf8
            Move-Item -LiteralPath $marketplaceTemporary -Destination $marketplacePath -Force
            $marketplaceTouched = $true

            & $codex.Source plugin add 'research-guard@personal' --json | Out-Null
            if ($LASTEXITCODE -ne 0) { throw 'Could not register the Research Guard Codex plugin.' }
            $codexRegistration = 'REGISTERED'
        }
    }

    Write-NetworkConfig $networkConfigPath $foreignProxy
    $networkConfigTouched = $true

    $inventory = & $installedPython -X utf8 (Join-Path $pluginTarget 'scripts\dependency_manager.py') inventory --json
    [pscustomobject]@{
        status = 'INSTALLED'
        operation = 'install'
        requested_command = $Command
        skill = $skillTarget
        plugin = $pluginTarget
        core_runtime = $runtimeTarget
        codex_registration = $codexRegistration
        network_proxy = if ($foreignProxy) { 'configured' } else { 'direct' }
        network_proxy_choice = if ($proxyChoiceMade) { 'prompt_or_flag' } else { 'preserved' }
        network_config = $networkConfigPath
        core_work_ready = $true
        first_load_selection_pending = $false
        first_load_inventory_pending = (($inventory | ConvertFrom-Json).first_load_pending)
        optional_selection_mode = 'on-demand'
        next_step = 'Load the research-guard Skill. Core work starts immediately; a missing optional capability will show sizes and ask whether to reuse, install, or continue with its named degradation.'
    } | ConvertTo-Json -Depth 5
} catch {
    if ($marketplaceTouched) {
        if ($marketplaceExisted -and (Test-Path -LiteralPath $marketplaceBackup)) {
            Copy-Item -LiteralPath $marketplaceBackup -Destination $marketplacePath -Force
        } elseif (Test-Path -LiteralPath $marketplacePath) {
            Remove-Item -LiteralPath $marketplacePath -Force -ErrorAction SilentlyContinue
        }
    }
    if ($coreReceiptExisted -and (Test-Path -LiteralPath $coreReceiptBackup)) {
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $coreReceiptPath) | Out-Null
        Copy-Item -LiteralPath $coreReceiptBackup -Destination $coreReceiptPath -Force
    } elseif (Test-Path -LiteralPath $coreReceiptPath) {
        Remove-Item -LiteralPath $coreReceiptPath -Force -ErrorAction SilentlyContinue
    }
    if ($networkConfigTouched) {
        if ($networkConfigExisted -and (Test-Path -LiteralPath $networkConfigBackup)) {
            Copy-Item -LiteralPath $networkConfigBackup -Destination $networkConfigPath -Force
        } elseif (Test-Path -LiteralPath $networkConfigPath) {
            Remove-Item -LiteralPath $networkConfigPath -Force -ErrorAction SilentlyContinue
        }
    }
    if ($skillSwapped -and (Test-Path -LiteralPath $skillTarget)) { Remove-Item -LiteralPath $skillTarget -Recurse -Force -ErrorAction SilentlyContinue }
    if (Test-Path -LiteralPath $skillBackup) { Move-Item -LiteralPath $skillBackup -Destination $skillTarget -Force }
    if ($runtimeSwapped -and (Test-Path -LiteralPath $runtimeTarget)) { Remove-Item -LiteralPath $runtimeTarget -Recurse -Force -ErrorAction SilentlyContinue }
    if (Test-Path -LiteralPath $runtimeBackup) { Move-Item -LiteralPath $runtimeBackup -Destination $runtimeTarget -Force }
    if ($pluginSwapped -and (Test-Path -LiteralPath $pluginTarget)) { Remove-Item -LiteralPath $pluginTarget -Recurse -Force -ErrorAction SilentlyContinue }
    if (Test-Path -LiteralPath $pluginBackup) { Move-Item -LiteralPath $pluginBackup -Destination $pluginTarget -Force }
    throw
} finally {
    if (Test-Path -LiteralPath $stagingRoot) {
        Remove-Item -LiteralPath $stagingRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path -LiteralPath $networkConfigBackup) {
        Remove-Item -LiteralPath $networkConfigBackup -Force -ErrorAction SilentlyContinue
    }
}
