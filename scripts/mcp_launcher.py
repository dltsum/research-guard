from __future__ import annotations

import json
import os
import runpy
import sys
from pathlib import Path

from network_config_core import network_environment
from component_runtime import installed_components


_PYTHON_ENVIRONMENT_VARIABLES = (
    "PYTHONHOME", "PYTHONPATH", "PYTHONUSERBASE", "PYTHONSTARTUP", "PYTHONEXECUTABLE",
    "PYTHONIOENCODING", "PYTHONWARNINGS", "PYTHONBREAKPOINT", "PYTHONUTF8",
)


def _child_environment() -> dict[str, str]:
    """Keep an explicit user configuration while dropping host interpreter inputs."""
    environment = network_environment(proxy=None)
    for variable in _PYTHON_ENVIRONMENT_VARIABLES:
        environment.pop(variable, None)
    return environment


def _runtime_candidates() -> list[Path]:
    package_root = Path(__file__).resolve().parents[1]
    if installed_components() is not None:
        # A selected installation owns its interpreter. An ambient all-in-one
        # runtime must not silently add unselected dependencies or capabilities.
        receipt = json.loads((package_root / "COMPONENT_INSTALL.json").read_text(encoding="utf-8"))
        return [Path(receipt["interpreter"])]
    configured = os.environ.get("RESEARCH_GUARD_PYTHON")
    home = Path(os.environ.get("RESEARCH_GUARD_HOME", Path.home() / ".research-guard")).expanduser()
    candidates = [Path(configured).expanduser()] if configured else []
    candidates.extend([
        home / "runtime" / "python" / "python.exe",
        home / "runtime" / "python" / "Scripts" / "python.exe",
        home / "runtime" / "python" / "bin" / "python",
    ])
    return candidates


def main() -> int:
    script = Path(__file__).resolve().with_name("mcp_server.py")
    current = Path(sys.executable).resolve()
    for candidate in _runtime_candidates():
        if candidate.is_file() and candidate.resolve() != current:
            os.execve(
                str(candidate), [str(candidate), "-I", "-X", "utf8", str(script)],
                _child_environment(),
            )
    # The source-tree fallback is still isolated from host proxy/package-index
    # and Python path variables before loading the MCP server in-process.
    child_environment = _child_environment()
    os.environ.clear()
    os.environ.update(child_environment)
    runpy.run_path(str(script), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
