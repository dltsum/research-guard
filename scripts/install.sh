#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PYTHON_BIN=${PYTHON_BIN:-python3}
# Do not let a developer's Python startup/path settings affect the installer
# itself; the selected interpreter and explicit package index are the inputs.
unset PYTHONHOME PYTHONPATH PYTHONUSERBASE PYTHONSTARTUP PYTHONEXECUTABLE \
  PYTHONIOENCODING PYTHONWARNINGS PYTHONBREAKPOINT PYTHONUTF8
exec "$PYTHON_BIN" -X utf8 "$SCRIPT_DIR/install_posix.py" "$@"
