from __future__ import annotations

import json
import os
import runpy
import sys
from pathlib import Path


def _runtime_candidates() -> list[Path]:
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
            os.execv(str(candidate), [str(candidate), "-X", "utf8", str(script)])
    try:
        import numpy  # noqa: F401
        import yaml  # noqa: F401
    except ImportError as exc:
        print(json.dumps({
            "status": "ERROR", "error": "DEPENDENCY_MISSING",
            "message": "Research Guard core runtime is missing. Run scripts/install.ps1 on Windows or scripts/install.sh on Linux/macOS.",
            "detail": str(exc),
        }), file=sys.stderr)
        return 86
    runpy.run_path(str(script), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
