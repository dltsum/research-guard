from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from research_guard_core import (  # noqa: E402
    GuardError,
    get_collision_report,
    get_gate_status,
    get_search_plan,
    list_sources,
    record_collision_resolution,
    refresh_domain,
    register_manual_evidence,
    register_method,
    request_manual_evidence,
    run_novelty_search,
    verify_receipt,
)
from dependency_manager import clean_state  # noqa: E402
from preset_audit import PresetAuditError, audit_repository  # noqa: E402


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
    classify.add_argument("--project-root", required=True)
    classify.add_argument("--primary-domain", required=True)
    classify.add_argument("--secondary-domain", action="append", default=[])
    classify.add_argument("--rationale", required=True)
    classify.add_argument("--discipline-profile-id")
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
    search.add_argument("--attempt-timeout-seconds", type=float, default=20)
    search.add_argument("--work-units-per-call", type=int, default=3)
    search.add_argument("--retry-unit-id", action="append", default=[])
    search.add_argument("--blocker-decision", help="JSON object or path to a JSON file")
    search.add_argument("--source-limit", type=int)
    resolve = sub.add_parser("resolve-collision")
    resolve.add_argument("--project-root", required=True)
    resolve.add_argument("--resolution", required=True, help="JSON object or path to a JSON file")
    verify = sub.add_parser("verify")
    verify.add_argument("--project-root", required=True)
    verify.add_argument("--strict", action="store_true")
    for name in ("clean", "hard-clean"):
        maintenance = sub.add_parser(name, help="remove generated Research Guard session/cache paths")
        maintenance.add_argument("--project-root", help="project whose .research-guard state is cleaned")
        maintenance.add_argument("--home", help="Research Guard home (defaults to RESEARCH_GUARD_HOME or ~/.research-guard)")
        maintenance.add_argument("--dry-run", action="store_true", help="show candidates without deleting")
        maintenance.add_argument("--cancel", action="store_true", help="stop before removing the next unit")
    audit = sub.add_parser("preset-audit", help="scan all checkout files for host-specific presets")
    audit.add_argument("--project-root", required=True, help="checkout root to audit; this is intentionally explicit")
    audit.add_argument("--policy")
    audit.add_argument("--no-ignored", action="store_true", help="exclude generated ignored paths (not the full audit)")
    audit.add_argument("--output", help="optional JSON receipt path")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "register":
            result = register_method(args.project_root, _method(args.method))
        elif args.command == "classify":
            result = refresh_domain(
                args.project_root, primary_domain=args.primary_domain,
                secondary_domains=args.secondary_domain, selected_by="main_agent",
                selection_rationale=args.rationale, discipline_profile_id=args.discipline_profile_id,
            )
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
            result = run_novelty_search(
                args.project_root, attempt_timeout_seconds=args.attempt_timeout_seconds,
                source_limit=args.source_limit, work_units_per_call=args.work_units_per_call,
                retry_unit_ids=args.retry_unit_id,
                blocker_decision=_method(args.blocker_decision) if args.blocker_decision else None,
            )
        elif args.command == "resolve-collision":
            result = record_collision_resolution(args.project_root, **_method(args.resolution))
        elif args.command == "status":
            result = get_gate_status(args.project_root)
        elif args.command == "report":
            result = get_collision_report(args.project_root)
        elif args.command == "verify":
            result = verify_receipt(args.project_root, strict=args.strict)
        elif args.command in {"clean", "hard-clean"}:
            result = clean_state(
                args.project_root, home=args.home, hard=args.command == "hard-clean",
                dry_run=args.dry_run, cancel=args.cancel,
            )
        elif args.command == "preset-audit":
            result = audit_repository(
                args.project_root,
                policy_path=args.policy,
                include_ignored=not args.no_ignored,
            )
            if args.output:
                output = Path(args.output).expanduser().resolve()
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        else:
            raise GuardError(f"Unsupported command: {args.command}")
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        if args.command == "verify" and not result["valid"]:
            return 2
        if args.command == "preset-audit" and result.get("status") != "PASS":
            return 1
        return 0
    except (GuardError, PresetAuditError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
