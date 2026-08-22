from __future__ import annotations

import sys


# Keep a checksum-bound installation byte-for-byte stable across launches.
sys.dont_write_bytecode = True

from research_console.server import main


if __name__ == "__main__":
    raise SystemExit(main())
