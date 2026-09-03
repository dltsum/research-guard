#!/usr/bin/env sh
set -eu

RG_HOME="${RESEARCH_GUARD_HOME:-$HOME/.research-guard}"
RG_PYTHON="${RESEARCH_GUARD_PYTHON:-$RG_HOME/runtime/python/bin/python}"
if [ ! -x "$RG_PYTHON" ]; then
  printf '%s\n' '{"status":"ERROR","error":"DEPENDENCY_MISSING","message":"Research Guard POSIX runtime is not installed"}' >&2
  exit 86
fi
# The project resource/figure contract owns these values; a host preset must
# not change memory use or rendering merely because the variable is present.
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export MPLBACKEND=Agg
for variable in HTTP_PROXY HTTPS_PROXY ALL_PROXY NO_PROXY http_proxy https_proxy all_proxy no_proxy \
  PIP_INDEX_URL PIP_EXTRA_INDEX_URL PIP_TRUSTED_HOST PIP_NO_INDEX PIP_FIND_LINKS \
  PIP_CONFIG_FILE PIP_CERT PIP_CLIENT_CERT UV_INDEX_URL UV_EXTRA_INDEX_URL UV_FIND_LINKS \
  PYTHONHOME PYTHONPATH PYTHONUSERBASE PYTHONSTARTUP PYTHONEXECUTABLE \
  PYTHONIOENCODING PYTHONWARNINGS PYTHONBREAKPOINT PYTHONUTF8; do
  unset "$variable"
done
exec "$RG_PYTHON" -X utf8 "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/mcp_server.py"
