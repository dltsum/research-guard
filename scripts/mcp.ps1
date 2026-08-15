$ErrorActionPreference = 'Stop'
$runtimeHome = if ($env:RESEARCH_GUARD_HOME) {
    [IO.Path]::GetFullPath($env:RESEARCH_GUARD_HOME)
} else {
    Join-Path ([Environment]::GetFolderPath('UserProfile')) '.research-guard'
}
$python = Join-Path $runtimeHome 'runtime\python\python.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    [Console]::Error.WriteLine('{"status":"ERROR","error":"DEPENDENCY_MISSING","message":"Research Guard bundled Python is not installed"}')
    exit 86
}
if (-not $env:OPENBLAS_NUM_THREADS) { $env:OPENBLAS_NUM_THREADS = '1' }
if (-not $env:OMP_NUM_THREADS) { $env:OMP_NUM_THREADS = '1' }
if (-not $env:MKL_NUM_THREADS) { $env:MKL_NUM_THREADS = '1' }
if (-not $env:NUMEXPR_NUM_THREADS) { $env:NUMEXPR_NUM_THREADS = '1' }
if (-not $env:MPLBACKEND) { $env:MPLBACKEND = 'Agg' }
& $python -X utf8 (Join-Path $PSScriptRoot 'mcp_server.py')
exit $LASTEXITCODE
