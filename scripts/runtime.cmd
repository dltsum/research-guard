@echo off
setlocal
set "RG_PYTHON=%USERPROFILE%\.research-guard\runtime\python\python.exe"
if defined RESEARCH_GUARD_HOME set "RG_PYTHON=%RESEARCH_GUARD_HOME%\runtime\python\python.exe"
if not exist "%RG_PYTHON%" (
  >&2 echo {"status":"ERROR","error":"DEPENDENCY_MISSING","message":"Research Guard bundled Python is not installed"}
  exit /b 86
)
if not defined OPENBLAS_NUM_THREADS set "OPENBLAS_NUM_THREADS=1"
if not defined OMP_NUM_THREADS set "OMP_NUM_THREADS=1"
if not defined MKL_NUM_THREADS set "MKL_NUM_THREADS=1"
if not defined NUMEXPR_NUM_THREADS set "NUMEXPR_NUM_THREADS=1"
if not defined MPLBACKEND set "MPLBACKEND=Agg"
"%RG_PYTHON%" %*
