#!/usr/bin/env sh
set -eu

RG_HOME="${RESEARCH_GUARD_HOME:-$HOME/.research-guard}"
RG_PYTHON="${RESEARCH_GUARD_PYTHON:-$RG_HOME/runtime/python/bin/python}"
if [ ! -x "$RG_PYTHON" ]; then
  printf '%s\n' '{"status":"ERROR","error":"DEPENDENCY_MISSING","message":"Research Guard POSIX runtime is not installed"}' >&2
  exit 86
fi
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
export NUMEXPR_NUM_THREADS="${NUMEXPR_NUM_THREADS:-1}"
export VECLIB_MAXIMUM_THREADS="${VECLIB_MAXIMUM_THREADS:-1}"
export MPLBACKEND="${MPLBACKEND:-Agg}"
exec "$RG_PYTHON" -X utf8 "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/mcp_server.py"
