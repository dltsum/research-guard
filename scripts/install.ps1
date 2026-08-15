param(
    [switch]$SkipCodexRegistration
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
$packageRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$resourcePolicyPath = Join-Path $packageRoot 'assets\resource-policy.json'
if (-not (Test-Path -LiteralPath $resourcePolicyPath -PathType Leaf)) { throw 'assets/resource-policy.json is required.' }
$resourcePolicy = Get-Content -LiteralPath $resourcePolicyPath -Raw | ConvertFrom-Json
if ($resourcePolicy.schema_version -ne 1 -or $resourcePolicy.maximum_parallel_workers -ne 1 -or $resourcePolicy.gpu_allowed -ne $false) {
    throw 'RESOURCE_POLICY_INVALID: only the serial CPU policy is supported.'
}
if ([int64]$resourcePolicy.worker_job_limit_bytes + [int64]$resourcePolicy.orchestrator_reserve_bytes -gt [int64]$resourcePolicy.owned_task_budget_bytes) {
    throw 'RESOURCE_POLICY_INVALID: worker plus orchestrator exceeds the owned-task budget.'
}
if ([int64]$resourcePolicy.lean_worker_limit_bytes + [int64]$resourcePolicy.lean_orchestrator_reserve_bytes -gt [int64]$resourcePolicy.owned_task_budget_bytes) {
    throw 'RESOURCE_POLICY_INVALID: Lean worker plus orchestrator exceeds the owned-task budget.'
}
if ([string]$resourcePolicy.memory_metric -ne 'aggregate_working_set' -or [double]$resourcePolicy.sampling_interval_seconds -gt 0.01) {
    throw 'RESOURCE_POLICY_INVALID: aggregate working-set sampling must be enabled at 10 ms or faster.'
}
Assert-MemoryHeadroom ([int64]$resourcePolicy.start_min_free_bytes)
Invoke-OrchestratorCheckpoint ([int64]$resourcePolicy.orchestrator_reserve_bytes)
$manifestPath = Join-Path $packageRoot 'RELEASE_MANIFEST.json'
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw 'RELEASE_MANIFEST.json is required. Install from the built migration archive, not the development source tree.'
}

$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ($manifest.package -ne 'research-guard' -or $manifest.variant -ne 'windows-x64-modular') {
    throw 'This installer only accepts the Research Guard windows-x64-modular release.'
}
foreach ($file in $manifest.files) {
    $path = Join-Path $packageRoot ([string]$file.path)
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Release file is missing: $($file.path)" }
    $item = Get-Item -LiteralPath $path
    if ($item.Length -ne [int64]$file.bytes) { throw "Release file size mismatch: $($file.path)" }
    $hash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($hash -ne ([string]$file.sha256).ToLowerInvariant()) { throw "Release file SHA-256 mismatch: $($file.path)" }
    Invoke-OrchestratorCheckpoint ([int64]$resourcePolicy.orchestrator_reserve_bytes)
}

$userRoot = if ($env:RESEARCH_GUARD_INSTALL_USER_ROOT) { [IO.Path]::GetFullPath($env:RESEARCH_GUARD_INSTALL_USER_ROOT) } else { [Environment]::GetFolderPath('UserProfile') }
$guardHome = if ($env:RESEARCH_GUARD_HOME) { [IO.Path]::GetFullPath($env:RESEARCH_GUARD_HOME) } else { Join-Path $userRoot '.research-guard' }
$codexHome = if ($env:RESEARCH_GUARD_CODEX_ROOT) {
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
    foreach ($entry in Get-ChildItem -LiteralPath $packageRoot -Force) {
        Copy-Item -LiteralPath $entry.FullName -Destination $pluginStage -Recurse -Force
        Invoke-OrchestratorCheckpoint ([int64]$resourcePolicy.orchestrator_reserve_bytes)
    }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::ExtractToDirectory($payload, $runtimeStage)
    Invoke-OrchestratorCheckpoint ([int64]$resourcePolicy.orchestrator_reserve_bytes)
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

result = run_managed_light(
    [sys.executable, "-X", "utf8", "-c", "import matplotlib,numpy,PIL,pypdf,networkx,optuna,pint,sympy,z3; print('CORE_IMPORT_PASS')"],
    env=os.environ.copy(), timeout=120,
)
if result.returncode != 0 or "CORE_IMPORT_PASS" not in result.stdout:
    raise SystemExit("Bundled Python dependency smoke failed: " + (result.stderr or result.stdout)[-2000:])
print("CORE_IMPORT_PASS")
'@ | Set-Content -LiteralPath $smokeRunner -Encoding ascii
    & $python -X utf8 $smokeRunner (Join-Path $pluginStage 'scripts')
    if ($LASTEXITCODE -ne 0) { throw 'Bundled Python bounded dependency smoke failed.' }
    Invoke-OrchestratorCheckpoint ([int64]$resourcePolicy.orchestrator_reserve_bytes)

    Copy-Item -LiteralPath (Join-Path $pluginStage 'SKILL.md') -Destination (Join-Path $skillStage 'SKILL.md') -Force
    foreach ($directory in @('agents','references')) {
        Copy-Item -LiteralPath (Join-Path $pluginStage $directory) -Destination (Join-Path $skillStage $directory) -Recurse -Force
    }
    Invoke-OrchestratorCheckpoint ([int64]$resourcePolicy.orchestrator_reserve_bytes)

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

    $inventory = & $installedPython -X utf8 (Join-Path $pluginTarget 'scripts\dependency_manager.py') inventory --json
    [pscustomobject]@{
        status = 'INSTALLED'
        skill = $skillTarget
        plugin = $pluginTarget
        core_runtime = $runtimeTarget
        codex_registration = $codexRegistration
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
}
