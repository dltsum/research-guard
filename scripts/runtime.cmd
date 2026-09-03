@echo off
setlocal
rem Explicit runtime path wins; then explicit Research Guard home; only then
rem use the conventional per-user fallback.  Never assume this checkout's
rem developer profile is another installation's runtime.
set "RG_PYTHON="
if defined RESEARCH_GUARD_PYTHON set "RG_PYTHON=%RESEARCH_GUARD_PYTHON%"
if not defined RG_PYTHON if defined RESEARCH_GUARD_HOME set "RG_PYTHON=%RESEARCH_GUARD_HOME%\runtime\python\python.exe"
if not defined RG_PYTHON set "RG_PYTHON=%USERPROFILE%\.research-guard\runtime\python\python.exe"
if not exist "%RG_PYTHON%" (
  >&2 echo {"status":"ERROR","error":"DEPENDENCY_MISSING","message":"Research Guard bundled Python is not installed"}
  exit /b 86
)
rem The project resource/figure contract owns thread count and renderer.
set "OPENBLAS_NUM_THREADS=1"
set "OMP_NUM_THREADS=1"
set "MKL_NUM_THREADS=1"
set "NUMEXPR_NUM_THREADS=1"
set "MPLBACKEND=Agg"
set "HTTP_PROXY="
set "HTTPS_PROXY="
set "ALL_PROXY="
set "NO_PROXY="
set "http_proxy="
set "https_proxy="
set "all_proxy="
set "no_proxy="
set "PIP_INDEX_URL="
set "PIP_EXTRA_INDEX_URL="
set "PIP_TRUSTED_HOST="
set "PIP_NO_INDEX="
set "PIP_FIND_LINKS="
set "PIP_CONFIG_FILE="
set "PIP_CERT="
set "PIP_CLIENT_CERT="
set "UV_INDEX_URL="
set "UV_EXTRA_INDEX_URL="
set "UV_FIND_LINKS="
set "PYTHONHOME="
set "PYTHONPATH="
set "PYTHONUSERBASE="
set "PYTHONSTARTUP="
set "PYTHONEXECUTABLE="
set "PYTHONIOENCODING="
set "PYTHONWARNINGS="
set "PYTHONBREAKPOINT="
set "PYTHONUTF8="
"%RG_PYTHON%" %*
