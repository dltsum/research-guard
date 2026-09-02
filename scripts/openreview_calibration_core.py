from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from network_config_core import NetworkConfigError, foreign_proxy_for


class OpenReviewCalibrationError(ValueError):
    pass


CALIBRATION_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
DEFAULT_CATEGORIES = {
    "novelty": ["novel", "original", "incremental", "prior work"],
    "soundness": ["sound", "correct", "proof", "assumption", "theory"],
    "empirical_rigor": ["experiment", "baseline", "ablation", "statistical", "evaluation"],
    "clarity": ["clarity", "writing", "presentation", "unclear"],
    "reproducibility": ["reproduc", "code", "data", "implementation"],
    "ethics_limitations": ["ethic", "limitation", "risk", "bias", "societal"],
}


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _state_path(root: Path, calibration_id: str) -> Path:
    return root / ".research-guard" / "openreview" / f"{calibration_id}.json"


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _field_value(value: Any) -> Any:
    if isinstance(value, dict) and "value" in value:
        return value["value"]
    return value


def _text_fields(content: Any) -> dict[str, str]:
    if not isinstance(content, dict):
        return {}
    result: dict[str, str] = {}
    for key, raw in content.items():
        value = _field_value(raw)
        if isinstance(value, str):
            result[str(key)] = value
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            result[str(key)] = str(value)
        elif isinstance(value, list) and all(isinstance(item, str) for item in value):
            result[str(key)] = "\n".join(value)
    return result


def _official_forum_url(forum_id: str) -> str:
    return "https://openreview.net/forum?" + urllib.parse.urlencode({"id": forum_id})


def _normalize_notes(notes: Any, requested_forums: set[str]) -> list[dict[str, Any]]:
    if not isinstance(notes, list):
        raise OpenReviewCalibrationError("OpenReview payload notes must be an array")
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, note in enumerate(notes):
        if not isinstance(note, dict):
            raise OpenReviewCalibrationError(f"OpenReview note {index} must be an object")
        note_id = str(note.get("id") or "").strip()
        forum = str(note.get("forum") or note_id).strip()
        invitation = str(note.get("invitation") or "").strip()
        if not note_id or note_id in seen or not forum or not invitation:
            raise OpenReviewCalibrationError(f"OpenReview note {index} lacks id, forum, or invitation")
        if requested_forums and forum not in requested_forums:
            raise OpenReviewCalibrationError(f"OpenReview response contains an unrequested forum: {forum}")
        seen.add(note_id)
        fields = _text_fields(note.get("content"))
        records.append({
            "note_id": note_id,
            "forum_id": forum,
            "forum_url": _official_forum_url(forum),
            "invitation": invitation,
            "replyto": note.get("replyto"),
            "field_names": sorted(fields),
            "fields": fields,
        })
    return records


def _live_notes(forum_ids: list[str], timeout: float) -> tuple[list[dict[str, Any]], list[str]]:
    try:
        proxy = foreign_proxy_for("https://api2.openreview.net")
    except NetworkConfigError as exc:
        raise OpenReviewCalibrationError(str(exc)) from exc
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": proxy, "https": proxy} if proxy else {})
    )
    notes: list[dict[str, Any]] = []
    urls: list[str] = []
    for forum_id in forum_ids:
        offset, page_size = 0, 1000
        while True:
            url = "https://api2.openreview.net/notes?" + urllib.parse.urlencode({
                "forum": forum_id, "limit": page_size, "offset": offset,
            })
            request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "ResearchGuardOpenReview/1.0"})
            try:
                with opener.open(request, timeout=timeout) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
                raise OpenReviewCalibrationError(f"official OpenReview API request failed for {forum_id}: {exc}") from exc
            if not isinstance(payload, dict) or not isinstance(payload.get("notes"), list):
                raise OpenReviewCalibrationError(f"official OpenReview API returned an invalid payload for {forum_id}")
            page = payload["notes"]
            notes.extend(page)
            urls.append(url)
            offset += len(page)
            count = payload.get("count")
            if len(page) < page_size or (isinstance(count, int) and offset >= count):
                break
            if offset >= 10000:
                raise OpenReviewCalibrationError(f"OpenReview forum {forum_id} exceeds the 10,000-note calibration bound")
    return notes, urls


def calibrate_openreview(
    root: str | os.PathLike[str],
    calibration_id: str,
    *,
    forum_ids: list[str] | None = None,
    fixture_payload: dict[str, Any] | None = None,
    categories: dict[str, list[str]] | None = None,
    timeout: float = 30,
) -> dict[str, Any]:
    base = Path(root).expanduser().resolve()
    identifier = str(calibration_id or "").strip().lower()
    if not CALIBRATION_ID.fullmatch(identifier):
        raise OpenReviewCalibrationError("calibration_id must use lowercase letters, digits, and hyphens")
    requested = [str(value).strip() for value in (forum_ids or []) if str(value).strip()]
    if len(requested) != len(set(requested)):
        raise OpenReviewCalibrationError("forum_ids contains duplicates")
    if fixture_payload is not None:
        if not isinstance(fixture_payload, dict) or not isinstance(fixture_payload.get("notes"), list):
            raise OpenReviewCalibrationError("fixture_payload must contain a notes array")
        notes, api_urls, source_mode = fixture_payload["notes"], [], "hash_bound_fixture"
        fixture_sha256 = _hash(fixture_payload)
    else:
        if not requested:
            raise OpenReviewCalibrationError("live calibration requires at least one forum_id")
        notes, api_urls = _live_notes(requested, float(timeout))
        source_mode, fixture_sha256 = "official_public_api_v2", None
    records = _normalize_notes(notes, set(requested))
    review_records = [
        record for record in records
        if any(token in record["invitation"].casefold() for token in ("review", "comment", "meta_review"))
    ]
    if not review_records:
        raise OpenReviewCalibrationError("no public review/comment records were present")
    schema = categories or DEFAULT_CATEGORIES
    if not isinstance(schema, dict) or not schema:
        raise OpenReviewCalibrationError("categories must be a non-empty object")
    coverage: dict[str, dict[str, Any]] = {}
    for category, raw_terms in schema.items():
        terms = [str(value).casefold().strip() for value in raw_terms if str(value).strip()]
        if not terms:
            raise OpenReviewCalibrationError(f"category {category} has no terms")
        matches = []
        for record in review_records:
            text = "\n".join(record["fields"].values()).casefold()
            found = sorted({term for term in terms if term in text})
            if found:
                matches.append({"note_id": record["note_id"], "forum_url": record["forum_url"], "matched_terms": found})
        coverage[str(category)] = {
            "review_count": len(matches), "fraction": len(matches) / len(review_records), "matches": matches,
        }
    rating_fields = ("rating", "recommendation", "score", "overall_assessment")
    confidence_fields = ("confidence", "reviewer_confidence")
    reported_severity_signals = {
        "rating_or_recommendation": [
            {"note_id": record["note_id"], "forum_url": record["forum_url"], "field": field, "reported_value": value}
            for record in review_records for field, value in record["fields"].items()
            if field.casefold().replace(" ", "_") in rating_fields
        ],
        "confidence": [
            {"note_id": record["note_id"], "forum_url": record["forum_url"], "field": field, "reported_value": value}
            for record in review_records for field, value in record["fields"].items()
            if field.casefold().replace(" ", "_") in confidence_fields
        ],
    }
    result = {
        "schema_version": 1,
        "status": "PASS" if source_mode == "official_public_api_v2" else "FIXTURE_ONLY",
        "calibration_id": identifier,
        "source_mode": source_mode,
        "official_api_urls": api_urls,
        "forum_urls": sorted({record["forum_url"] for record in records}),
        "fixture_sha256": fixture_sha256,
        "record_count": len(records),
        "review_record_count": len(review_records),
        "invitation_schema": sorted({record["invitation"] for record in records}),
        "field_schema": sorted({field for record in review_records for field in record["field_names"]}),
        "category_schema": schema,
        "coverage": coverage,
        "reported_severity_signals": reported_severity_signals,
        "records": review_records,
        "calibration_only": True,
        "acceptance_prediction": False,
        "limitations": [
            "Public OpenReview records are a venue- and year-specific calibration sample, not ground truth.",
            "Keyword coverage does not infer reviewer intent, quality, severity, or an acceptance probability.",
        ],
        "checked_at": _now(),
    }
    result["receipt_sha256"] = _hash(result)
    _atomic_json(_state_path(base, identifier), result)
    return result


def get_openreview_calibration(root: str | os.PathLike[str], calibration_id: str) -> dict[str, Any]:
    base = Path(root).expanduser().resolve()
    identifier = str(calibration_id or "").strip().lower()
    path = _state_path(base, identifier)
    if not path.is_file():
        return {"status": "NOT_FOUND", "calibration_id": identifier}
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OpenReviewCalibrationError(f"calibration state is invalid: {exc}") from exc
    saved = result.get("receipt_sha256")
    unsigned = {key: value for key, value in result.items() if key != "receipt_sha256"}
    if saved != _hash(unsigned):
        raise OpenReviewCalibrationError("calibration receipt integrity check failed")
    return result
