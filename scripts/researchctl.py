from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from research_guard_core import (  # noqa: E402
    GuardError,
    classify_domain,
    get_collision_report,
    get_gate_status,
    get_search_plan,
    list_sources,
    record_collision_resolution,
    register_manual_evidence,
    register_method,
    request_manual_evidence,
    run_novelty_search,
    verify_receipt,
)


def _method(value: str) -> dict:
    candidate = Path(value)
    if candidate.exists():
        return json.loads(candidate.read_text(encoding="utf-8"))
    return json.loads(value)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="researchctl", description="Strict research novelty evidence gate")
    sub = root.add_subparsers(dest="command", required=True)
    register = sub.add_parser("register")
    register.add_argument("--project-root", required=True)
    register.add_argument("--method", required=True, help="JSON object or path to a JSON file")
    classify = sub.add_parser("classify")
    classify.add_argument("--text", required=True)
    sources = sub.add_parser("sources")
    sources.add_argument("--access")
    sources.add_argument("--automation")
    sources.add_argument("--domain")
    manual_request = sub.add_parser("manual-request")
    manual_request.add_argument("--project-root", required=True)
    manual_request.add_argument("--sources")
    manual_register = sub.add_parser("manual-register")
    manual_register.add_argument("--project-root", required=True)
    manual_register.add_argument("--evidence", required=True, help="JSON object or path to a JSON file")
    for name in ("plan", "status", "report"):
        command = sub.add_parser(name)
        command.add_argument("--project-root", required=True)
    search = sub.add_parser("search")
    search.add_argument("--project-root", required=True)
    search.add_argument("--timeout", type=float, default=20)
    search.add_argument("--source-limit", type=int)
    resolve = sub.add_parser("resolve-collision")
    resolve.add_argument("--project-root", required=True)
    resolve.add_argument("--resolution", required=True, help="JSON object or path to a JSON file")
    verify = sub.add_parser("verify")
    verify.add_argument("--project-root", required=True)
    verify.add_argument("--strict", action="store_true")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "register":
            result = register_method(args.project_root, _method(args.method))
        elif args.command == "classify":
            result = classify_domain(args.text)
        elif args.command == "sources":
            result = list_sources(access=args.access, automation=args.automation, domain=args.domain)
        elif args.command == "manual-request":
            result = request_manual_evidence(args.project_root, args.sources)
        elif args.command == "manual-register":
            evidence = _method(args.evidence)
            result = register_manual_evidence(args.project_root, **evidence)
        elif args.command == "plan":
            result = get_search_plan(args.project_root)
        elif args.command == "search":
            result = run_novelty_search(args.project_root, timeout=args.timeout, source_limit=args.source_limit)
        elif args.command == "resolve-collision":
            result = record_collision_resolution(args.project_root, **_method(args.resolution))
        elif args.command == "status":
            result = get_gate_status(args.project_root)
        elif args.command == "report":
            result = get_collision_report(args.project_root)
        elif args.command == "verify":
            result = verify_receipt(args.project_root, strict=args.strict)
        else:
            raise GuardError(f"Unsupported command: {args.command}")
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        if args.command == "verify" and not result["valid"]:
            return 2
        return 0
    except (GuardError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
