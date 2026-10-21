"""Lightweight workflow reminders, with no file scans or permission gates."""
from __future__ import annotations

import json
import sys
from typing import Any


def context(event: str, message: str) -> dict[str, Any]:
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": message}}


def emit(value: dict[str, Any]) -> int:
    sys.stdout.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
    return 0


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    event = str(payload.get("hook_event_name", ""))
    if event == "SessionStart":
        return emit(context(event, "Research Guard: use the installed component needed by the task. "
                            "Existing Python, TeX and Lean environments can be reused. "
                            "Normal edits and updates need no digest, receipt seal or reinstall."))
    if event == "UserPromptSubmit":
        return emit(context(event, "Read the supplied research inputs and do the requested work directly. "
                            "Keep sources and actual results traceable. Use plans and status tools when useful; "
                            "they are not prerequisites for writing files or completing a response. "
                            "Preserve explicitly requested writing/figure audits and report checks that were not run."))
    # PreToolUse/PostToolUse/Stop never block an edit or response on cached state.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
