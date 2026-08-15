from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from language_guard_core import analyze_language, plan_language_review


SOURCE = (
    "Because the sample is small, the method may not improve accuracy by 5% "
    "on `model_id` [12]. See https://example.org/data."
)


def evaluate(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    checks: dict[str, bool] = {}
    language = value.get("language", {})
    checks["language_status"] = language.get("status") == "USER_DECISION_REQUIRED"
    checks["language_preserves_may"] = language.get("protected_terms") == ["may"]
    checks["language_user_limitation"] = language.get("user_checklist_kinds") == ["material_limitation"]
    checks["language_textual_signal"] = language.get("textual_signals") == ["assistant_process_residue"]
    checks["language_no_auto_choice"] = language.get("auto_decision") is False

    ethics = value.get("ethics", {})
    checks["ethics_status"] = ethics.get("status") == "USER_DECISION_REQUIRED"
    checks["ethics_candidate"] = ethics.get("user_checklist_kinds") == ["potential_ethics_omission"]
    checks["ethics_not_proven"] = ethics.get("candidate_not_proven") is True
    checks["ethics_no_auto_choice"] = ethics.get("auto_decision") is False

    conference = value.get("conference", {})
    checks["conference_status"] = conference.get("status") == "OFFICIAL_VERIFICATION_REQUIRED"
    checks["conference_rejects_fixed_rules"] = conference.get("accepted_fixed_rules") == []
    checks["conference_requires_official_links"] = (
        conference.get("requires_official_policy_https") is True
        and conference.get("requires_official_template_https") is True
    )

    translation = value.get("translation", {})
    target = str(translation.get("translated_text") or "")
    checks["translation_status"] = translation.get("status") == "DRAFT_READY_FOR_CONTRACT_CHECK"
    with tempfile.TemporaryDirectory() as temp:
        plan_language_review(
            temp,
            "Translate",
            task_mode="translation",
            source_text=SOURCE,
            draft_text=target,
            source_language="English",
            target_language="Chinese",
        )
        result = analyze_language(temp, draft_text=target, source_text=SOURCE)
    checks["translation_contract"] = result["translation_check"]["status"] == "PASS"

    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "passed": sum(checks.values()),
        "total": len(checks),
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    arguments = parser.parse_args()
    result = evaluate(arguments.path)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
