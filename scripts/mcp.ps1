$ErrorActionPreference = 'Stop'
$python = if ($env:RESEARCH_GUARD_PYTHON) {
    [IO.Path]::GetFullPath($env:RESEARCH_GUARD_PYTHON)
} else {
    $null
}
$runtimeHome = if ($env:RESEARCH_GUARD_HOME) {
    [IO.Path]::GetFullPath($env:RESEARCH_GUARD_HOME)
} else {
    Join-Path ([Environment]::GetFolderPath('UserProfile')) '.research-guard'
}
if (-not $python) { $python = Join-Path $runtimeHome 'runtime\python\python.exe' }
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    [Console]::Error.WriteLine('{"status":"ERROR","error":"DEPENDENCY_MISSING","message":"Research Guard bundled Python is not installed"}')
    exit 86
}
# The project resource/figure contract owns these values; host variables must
# not change memory use or rendering.  Scholarly/package routes are resolved
# only from explicit Research Guard configuration inside the Python core.
$env:OPENBLAS_NUM_THREADS = '1'
$env:OMP_NUM_THREADS = '1'
$env:MKL_NUM_THREADS = '1'
$env:NUMEXPR_NUM_THREADS = '1'
$env:MPLBACKEND = 'Agg'
foreach ($variable in @(
    'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY', 'http_proxy', 'https_proxy', 'all_proxy', 'no_proxy',
    'PIP_INDEX_URL', 'PIP_EXTRA_INDEX_URL', 'PIP_TRUSTED_HOST', 'PIP_NO_INDEX', 'PIP_FIND_LINKS',
    'PIP_CONFIG_FILE', 'PIP_CERT', 'PIP_CLIENT_CERT', 'UV_INDEX_URL', 'UV_EXTRA_INDEX_URL', 'UV_FIND_LINKS',
    'PYTHONHOME', 'PYTHONPATH', 'PYTHONUSERBASE', 'PYTHONSTARTUP', 'PYTHONEXECUTABLE',
    'PYTHONIOENCODING', 'PYTHONWARNINGS', 'PYTHONBREAKPOINT', 'PYTHONUTF8'
)) {
    Remove-Item -LiteralPath "Env:$variable" -ErrorAction SilentlyContinue
}
& $python -X utf8 (Join-Path $PSScriptRoot 'mcp_server.py')
exit $LASTEXITCODE
