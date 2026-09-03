#!/usr/bin/env sh
set -eu

RG_HOME="${RESEARCH_GUARD_HOME:-$HOME/.research-guard}"
RG_PYTHON="${RESEARCH_GUARD_PYTHON:-$RG_HOME/runtime/python/bin/python}"
if [ ! -x "$RG_PYTHON" ]; then
  RG_PYTHON="$(command -v python3 || command -v python || true)"
fi
if [ -z "$RG_PYTHON" ] || [ ! -x "$RG_PYTHON" ]; then
  printf '%s\n' '{"status":"ERROR","error":"DEPENDENCY_MISSING","message":"Research Guard Python runtime is not available for hooks"}' >&2
  exit 86
fi

# Hooks use the same bounded CPU/rendering and explicit-network contract as the
# MCP launchers. Do not inherit a host proxy, package index, or thread preset.
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 MPLBACKEND=Agg
for variable in HTTP_PROXY HTTPS_PROXY ALL_PROXY NO_PROXY http_proxy https_proxy all_proxy no_proxy \
  PIP_INDEX_URL PIP_EXTRA_INDEX_URL PIP_TRUSTED_HOST PIP_NO_INDEX PIP_FIND_LINKS \
  PIP_CONFIG_FILE PIP_CERT PIP_CLIENT_CERT UV_INDEX_URL UV_EXTRA_INDEX_URL UV_FIND_LINKS \
  PYTHONHOME PYTHONPATH PYTHONUSERBASE PYTHONSTARTUP PYTHONEXECUTABLE \
  PYTHONIOENCODING PYTHONWARNINGS PYTHONBREAKPOINT PYTHONUTF8; do
  unset "$variable"
done
exec "$RG_PYTHON" -I -X utf8 "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/guard_hook.py"
