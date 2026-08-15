from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any


class FigureError(ValueError):
    pass


SCHEMA_VERSION = 1
RENDERER_VERSION = "research-guard-academic-figure-v1"
ALLOWED_KINDS = {"statistical", "diagram"}
ALLOWED_FORMATS = {"svg", "pdf", "png"}
ALLOWED_CHARTS = {"line", "scatter", "bar", "box", "histogram", "heatmap"}
ALLOWED_PALETTES = {"okabe_ito_on_white", "tol_high_contrast", "grayscale"}
PALETTES = {
    "okabe_ito_on_white": ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#000000"],
    "tol_high_contrast": ["#004488", "#DDAA33", "#BB5566"],
    "grayscale": ["#111111", "#555555", "#999999", "#CCCCCC"],
}
MARKERS = ["o", "s", "^", "D", "v", "P", "X"]
LINESTYLES = ["-", "--", "-.", ":"]
FIGURE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
FORBIDDEN_CHOICE_KEYS = {
    "highlight_ours", "recommended_series", "recommendedseries", "auto_emphasis", "autoemphasis",
    "winner", "best_series", "bestseries",
}
BASE_VISUAL_CHECKS = {
    "labels_readable", "no_clipping", "legend_clear", "uncertainty_clear",
    "color_redundant", "semantic_accuracy", "panel_hierarchy", "no_content_occlusion",
    "space_utilization_balanced", "text_and_line_alignment", "margins_and_gutters_balanced",
}
VENUE_VISUAL_CHECK = "venue_style_conformant"
FIGURE_ROLES = {
    "statistical_numeric", "semantic_diagram", "visual_evidence_integrity",
    "accessibility_export", "venue_style",
}
IMAGE_AUDIT_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
IMAGE_RECORD_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,62}$")
IMAGE_ROLES = {"original", "processed", "panel"}
ALLOWED_IMAGE_TRANSFORMS = {
    "crop", "rotate", "resize", "global_brightness_contrast", "global_color_balance",
    "denoise", "annotate", "stitch", "channel_merge", "pseudocolor", "format_conversion",
}
PROHIBITED_IMAGE_TRANSFORMS = {
    "clone_stamp", "content_aware_fill", "generative_fill", "selective_erasure", "object_removal",
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _hash_value(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def _state_path(root: Path, figure_id: str) -> Path:
    return root / ".research-guard" / "figures" / f"{figure_id}.json"


def _safe_figure_id(value: str) -> str:
    figure_id = str(value or "").strip().lower()
    if not FIGURE_ID.fullmatch(figure_id):
        raise FigureError("figure_id must use lowercase letters, digits, and hyphens")
    return figure_id


def _safe_file(root: Path, value: str, *, require: bool = True) -> tuple[Path, str]:
    candidate = Path(str(value))
    path = (root / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError as exc:
        raise FigureError(f"source file must stay inside project_root: {value}") from exc
    lexical = root / candidate if not candidate.is_absolute() else candidate
    if lexical.is_symlink() or path.is_symlink():
        raise FigureError(f"source file cannot be a symlink: {relative}")
    if require and not path.is_file():
        raise FigureError(f"source file does not exist: {relative}")
    return path, relative


def _tracked_sources(root: Path, values: list[str] | None) -> list[dict[str, Any]]:
    tracked: list[dict[str, Any]] = []
    seen: set[str] = set()
    for value in values or []:
        path, relative = _safe_file(root, value)
        if relative in seen:
            raise FigureError(f"duplicate source file: {relative}")
        seen.add(relative)
        tracked.append({"path": relative, "sha256": _sha256(path), "bytes": path.stat().st_size})
    return sorted(tracked, key=lambda item: item["path"])


def _load_state(root: Path, figure_id: str) -> dict[str, Any]:
    path = _state_path(root, figure_id)
    if not path.is_file() or path.is_symlink():
        raise FigureError("academic figure has not been planned")
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise FigureError(f"academic figure state is invalid: {exc}") from exc
    unsigned = {key: value for key, value in state.items() if key != "state_sha256"}
    if state.get("state_sha256") != _hash_value(unsigned):
        raise FigureError("academic figure state integrity check failed")
    return state


def _save_state(root: Path, figure_id: str, state: dict[str, Any]) -> dict[str, Any]:
    unsigned = {key: value for key, value in state.items() if key != "state_sha256"}
    unsigned["state_sha256"] = _hash_value(unsigned)
    _atomic_json(_state_path(root, figure_id), unsigned)
    return unsigned


def _normalize_figure_roles(
    kind: str,
    selected_roles: list[str] | None,
    selected_by: str,
    selection_rationale: str,
    venue_contract: dict[str, Any] | None,
) -> tuple[list[str], str]:
    if selected_by != "main_agent":
        raise FigureError("selected_by=main_agent is required; automatic figure-role selection is forbidden")
    rationale = " ".join(str(selection_rationale or "").split())
    if len(rationale) < 12:
        raise FigureError("selection_rationale must explain the main agent's figure-role choice")
    roles = [str(value).strip() for value in (selected_roles or []) if str(value).strip()]
    if not 2 <= len(roles) <= 3 or len(roles) != len(set(roles)):
        raise FigureError("the main agent must select two or three distinct figure roles")
    unknown = sorted(set(roles) - FIGURE_ROLES)
    if unknown:
        raise FigureError(f"unknown figure roles: {', '.join(unknown)}")
    mandatory = {"visual_evidence_integrity", "statistical_numeric" if kind == "statistical" else "semantic_diagram"}
    if venue_contract is not None:
        mandatory.add("venue_style")
    missing = sorted(mandatory - set(roles))
    if missing:
        raise FigureError("selected figure roles do not cover required checks: " + ", ".join(missing))
    return roles, rationale


def _normalize_venue_contract(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise FigureError("venue_contract must be an object")
    required = (
        "venue_name", "year", "track", "stage", "policy_url", "figure_rules_url",
        "verified_at", "source_type", "status", "rules",
    )
    missing = [key for key in required if value.get(key) in (None, "", [], {})]
    if missing:
        raise FigureError("venue_contract is missing: " + ", ".join(missing))
    normalized = dict(value)
    for key in ("policy_url", "figure_rules_url"):
        if not str(normalized[key]).startswith("https://"):
            raise FigureError(f"venue_contract {key} must be an official https:// URL")
    if str(normalized["source_type"]).casefold() != "official" or str(normalized["status"]).casefold() != "verified":
        raise FigureError("venue_contract requires source_type=official and status=verified")
    try:
        verified = dt.datetime.fromisoformat(str(normalized["verified_at"]).replace("Z", "+00:00"))
    except ValueError as exc:
        raise FigureError("venue_contract verified_at must be ISO-8601") from exc
    if verified.tzinfo is None:
        verified = verified.replace(tzinfo=dt.timezone.utc)
    age = dt.datetime.now(dt.timezone.utc) - verified.astimezone(dt.timezone.utc)
    if age < dt.timedelta(days=-1) or age > dt.timedelta(days=30):
        raise FigureError("venue_contract is future-dated or older than 30 days; recheck the exact venue rules")
    if not isinstance(normalized["rules"], (dict, list)):
        raise FigureError("venue_contract rules must preserve the exact figure requirements")
    normalized["source_type"] = "official"
    normalized["status"] = "verified"
    normalized["contract_sha256"] = _hash_value({key: value for key, value in normalized.items() if key != "contract_sha256"})
    return normalized


def plan_academic_figure(
    root: str | os.PathLike[str],
    *,
    figure_id: str,
    request_text: str,
    figure_kind: str,
    source_files: list[str] | None,
    width_mm: float,
    height_mm: float,
    formats: list[str] | None = None,
    effort: str = "medium",
    venue_contract: dict[str, Any] | None = None,
    selected_roles: list[str] | None = None,
    selected_by: str = "",
    selection_rationale: str = "",
) -> dict[str, Any]:
    base = Path(root).expanduser().resolve()
    figure_id = _safe_figure_id(figure_id)
    kind = str(figure_kind or "").strip().lower()
    if kind not in ALLOWED_KINDS:
        raise FigureError("figure_kind must be statistical or diagram")
    effort = str(effort or "").strip().lower()
    if effort not in {"low", "medium", "high"}:
        raise FigureError("effort must be low, medium, or high; xhigh/ultra are forbidden")
    if not str(request_text or "").strip():
        raise FigureError("request_text is required")
    try:
        width, height = float(width_mm), float(height_mm)
    except (TypeError, ValueError) as exc:
        raise FigureError("width_mm and height_mm must be numeric") from exc
    if not (20 <= width <= 400 and 20 <= height <= 500):
        raise FigureError("final physical dimensions are outside the supported 20-400 mm by 20-500 mm range")
    requested_formats = list(dict.fromkeys(str(value).lower() for value in (formats or ["svg", "pdf", "png"])))
    if set(requested_formats) != {"svg", "pdf", "png"}:
        raise FigureError("P8 publication bundles require svg, pdf, and png")
    tracked = _tracked_sources(base, source_files)
    if kind == "statistical" and not tracked:
        raise FigureError("statistical figures require at least one raw source file")
    normalized_venue = _normalize_venue_contract(venue_contract)
    roles, rationale = _normalize_figure_roles(
        kind, selected_roles, selected_by, selection_rationale, normalized_venue,
    )
    plan = {
        "schema_version": SCHEMA_VERSION,
        "renderer_version": RENDERER_VERSION,
        "figure_id": figure_id,
        "request_text": str(request_text),
        "figure_kind": kind,
        "backend": "python_matplotlib",
        "effort": effort,
        "selected_roles": roles,
        "selected_by": "main_agent",
        "selection_rationale": rationale,
        "automatic_role_selection": False,
        "source_files": tracked,
        "width_mm": width,
        "height_mm": height,
        "formats": requested_formats,
        "venue_contract": normalized_venue,
    }
    plan["plan_sha256"] = _hash_value(plan)
    state = {
        "schema_version": SCHEMA_VERSION,
        "figure_id": figure_id,
        "status": "RENDER_REQUIRED",
        "reason": "the figure contract is planned but no rendered bundle exists",
        "planned_at": utc_now(),
        "plan": plan,
        "latest_revision": 0,
        "render": None,
        "audit": None,
        "visual_review": None,
        "receipt": None,
    }
    return _save_state(base, figure_id, state)["plan"]


def _forbidden_keys(value: Any, path: str = "spec") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
            if str(key).lower() in FORBIDDEN_CHOICE_KEYS or normalized in {re.sub(r"[^a-z0-9]", "", item) for item in FORBIDDEN_CHOICE_KEYS}:
                found.append(f"{path}.{key}")
            found.extend(_forbidden_keys(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_forbidden_keys(child, f"{path}[{index}]"))
    return found


def _nonempty_text(spec: dict[str, Any], key: str) -> str:
    value = str(spec.get(key) or "").strip()
    if not value:
        raise FigureError(f"figure spec requires {key}")
    return value


def validate_figure_spec(spec: dict[str, Any], *, planned_kind: str) -> dict[str, Any]:
    if not isinstance(spec, dict):
        raise FigureError("figure spec must be an object")
    kind = str(spec.get("kind") or "").strip().lower()
    if kind != planned_kind or kind not in ALLOWED_KINDS:
        raise FigureError("figure spec kind does not match the planned figure")
    forbidden = _forbidden_keys(spec)
    if forbidden:
        raise FigureError(f"forbidden automatic scientific choice: {', '.join(forbidden)}")
    _nonempty_text(spec, "claim")
    alt_text = _nonempty_text(spec, "alt_text")
    if len(alt_text) < 20:
        raise FigureError("alt_text must describe the scientific content")
    if spec.get("renderer") in {"image_generation", "gemini", "openrouter", "imagegen"}:
        raise FigureError("image generation is forbidden for quantitative or exact formal figures")
    if spec.get("three_dimensional") is True:
        raise FigureError("decorative 3D encodings are forbidden")
    if spec.get("dual_axis") is True:
        raise FigureError("dual axes are forbidden in the P8 deterministic renderer")
    if spec.get("excluded_rows"):
        raise FigureError("row exclusions require a registered transformation contract; inline exclusion is forbidden")
    style = spec.get("style") or {}
    if not isinstance(style, dict):
        raise FigureError("style must be an object")
    palette = str(style.get("palette") or "okabe_ito_on_white")
    if palette not in ALLOWED_PALETTES:
        raise FigureError(f"unsupported or deceptive palette: {palette}")
    emphasis = style.get("emphasis_series")
    if emphasis is not None and style.get("emphasis_selected_by") != "user":
        raise FigureError("series emphasis requires emphasis_selected_by=user")

    if kind == "statistical":
        chart = str(spec.get("chart_type") or "").strip().lower()
        if chart not in ALLOWED_CHARTS:
            raise FigureError(f"unsupported chart_type: {chart}")
        _nonempty_text(spec, "data_file")
        for key in ("x", "y", "x_label", "y_label"):
            _nonempty_text(spec, key)
        missing_policy = str(spec.get("missing_policy") or "error")
        if missing_policy not in {"error", "gap"}:
            raise FigureError("missing_policy must be error or gap; silent drop is forbidden")
        summary = spec.get("summary")
        if not isinstance(summary, dict):
            raise FigureError("statistical figures require a summary contract")
        estimator = str(summary.get("estimator") or "")
        uncertainty = str(summary.get("uncertainty") or "")
        replicate = str(summary.get("replicate_unit") or "").strip()
        if estimator not in {"mean", "median", "raw"}:
            raise FigureError("estimator must be mean, median, or raw")
        if uncertainty not in {"none", "sd", "sem", "ci95"}:
            raise FigureError("uncertainty must be none, sd, sem, or ci95")
        if uncertainty != "none" and not replicate:
            raise FigureError("uncertainty requires a non-empty replicate_unit")
        if uncertainty == "ci95" and not isinstance(summary.get("seed"), int):
            raise FigureError("ci95 requires a deterministic integer seed")
        if estimator == "raw" and chart not in {"scatter", "box", "histogram"}:
            raise FigureError("raw estimator is supported only by scatter, box, or histogram")
        exclusions = spec.get("exclusions", [])
        if not isinstance(exclusions, list):
            raise FigureError("exclusions must be an array")
        for index, exclusion in enumerate(exclusions):
            if not isinstance(exclusion, dict):
                raise FigureError(f"exclusion {index} must be an object")
            rows = exclusion.get("row_numbers")
            if not isinstance(rows, list) or not rows or any(not isinstance(row, int) or row < 2 for row in rows):
                raise FigureError(f"exclusion {index} requires CSV row_numbers >= 2")
            if exclusion.get("predeclared") is not True or exclusion.get("selected_by") != "user":
                raise FigureError(f"exclusion {index} must be predeclared and selected_by=user")
            if len(str(exclusion.get("reason") or "").strip()) < 20:
                raise FigureError(f"exclusion {index} requires a concrete scientific reason")
        y_limits = spec.get("y_limits")
        if chart == "bar" and isinstance(y_limits, list) and len(y_limits) == 2 and float(y_limits[0]) != 0:
            raise FigureError("bar baseline must start at zero")
        if str(spec.get("y_scale") or "linear") not in {"linear", "log"}:
            raise FigureError("y_scale must be linear or log")
    else:
        nodes = spec.get("nodes")
        edges = spec.get("edges")
        if not isinstance(nodes, list) or not nodes:
            raise FigureError("diagram requires non-empty nodes")
        if not isinstance(edges, list):
            raise FigureError("diagram edges must be an array")
        identifiers: set[str] = set()
        boxes: list[tuple[str, float, float, float, float]] = []
        for index, node in enumerate(nodes):
            if not isinstance(node, dict):
                raise FigureError(f"node {index} must be an object")
            identifier = str(node.get("id") or "").strip()
            if not identifier or identifier in identifiers:
                raise FigureError(f"duplicate node or missing id: {identifier or index}")
            identifiers.add(identifier)
            _nonempty_text(node, "label")
            try:
                x, y = float(node["x"]), float(node["y"])
                width, height = float(node.get("width", 0.22)), float(node.get("height", 0.18))
            except (KeyError, TypeError, ValueError) as exc:
                raise FigureError(f"node {identifier} requires numeric x/y/width/height") from exc
            if not (0 < x < 1 and 0 < y < 1 and 0 < width <= 0.8 and 0 < height <= 0.8):
                raise FigureError(f"node {identifier} geometry must use normalized canvas coordinates")
            boxes.append((identifier, x, y, width, height))
            if x - width / 2 < 0.015 or x + width / 2 > 0.985 or y - height / 2 < 0.015 or y + height / 2 > 0.985:
                raise FigureError(f"diagram node {identifier} clips or crowds the canvas boundary")
        for left_index, left in enumerate(boxes):
            for right in boxes[left_index + 1:]:
                if abs(left[1] - right[1]) < (left[3] + right[3]) / 2 and abs(left[2] - right[2]) < (left[4] + right[4]) / 2:
                    raise FigureError(f"diagram node overlap: {left[0]} and {right[0]}")
        for index, edge in enumerate(edges):
            if not isinstance(edge, dict):
                raise FigureError(f"edge {index} must be an object")
            source, target = str(edge.get("from") or ""), str(edge.get("to") or "")
            if source not in identifiers or target not in identifiers:
                raise FigureError(f"edge {index} references an unknown node")
            if str(edge.get("style") or "solid") not in {"solid", "dashed", "dotted"}:
                raise FigureError(f"edge {index} has an unsupported style")
            if edge.get("label"):
                source_box = next(item for item in boxes if item[0] == source)
                target_box = next(item for item in boxes if item[0] == target)
                label_x = (source_box[1] + target_box[1]) / 2
                label_y = (source_box[2] + target_box[2]) / 2 + (0.24 if edge.get("curve") else 0.04)
                for node_id, node_x, node_y, node_width, node_height in boxes:
                    if node_id in {source, target}:
                        continue
                    if abs(label_x - node_x) <= node_width / 2 + 0.015 and abs(label_y - node_y) <= node_height / 2 + 0.015:
                        raise FigureError(f"edge label overlaps node {node_id}; revise the diagram layout")
    return {"kind": kind, "external_image_api": False, "palette": palette}


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = [str(field) for field in (reader.fieldnames or [])]
            rows = [dict(row) for row in reader]
    except (OSError, UnicodeError, csv.Error) as exc:
        raise FigureError(f"could not read CSV source: {exc}") from exc
    if not fields or not rows:
        raise FigureError("CSV source requires a header and at least one row")
    return fields, rows


def _numeric(value: str, *, column: str, row: int, missing_ok: bool) -> float | None:
    stripped = str(value or "").strip()
    if stripped == "":
        if missing_ok:
            return None
        raise FigureError(f"missing value in {column} at data row {row}")
    try:
        number = float(stripped)
    except ValueError as exc:
        raise FigureError(f"non-numeric value in {column} at data row {row}") from exc
    if not math.isfinite(number):
        raise FigureError(f"non-finite value in {column} at data row {row}")
    return number


def _x_value(value: str, *, column: str, row: int, missing_ok: bool) -> float | str | None:
    stripped = str(value or "").strip()
    if stripped == "":
        if missing_ok:
            return None
        raise FigureError(f"missing value in {column} at data row {row}")
    try:
        number = float(stripped)
    except ValueError:
        return stripped
    if not math.isfinite(number):
        raise FigureError(f"non-finite value in {column} at data row {row}")
    return number


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2


def _sd(values: list[float]) -> float:
    if len(values) < 2:
        raise FigureError("SD/SEM/CI requires at least two observations per summarized cell")
    center = _mean(values)
    return math.sqrt(sum((value - center) ** 2 for value in values) / (len(values) - 1))


def _bootstrap_ci(values: list[float], seed: int, *, samples: int = 5000) -> tuple[float, float]:
    if len(values) < 2:
        raise FigureError("CI requires at least two observations per summarized cell")
    import random

    generator = random.Random(seed)
    estimates = []
    for _ in range(samples):
        estimates.append(_mean([generator.choice(values) for _ in range(len(values))]))
    estimates.sort()
    return estimates[int(0.025 * (samples - 1))], estimates[int(0.975 * (samples - 1))]


def _prepare_statistical(root: Path, plan: dict[str, Any], spec: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    data_path, relative = _safe_file(root, str(spec["data_file"]))
    tracked = {item["path"]: item for item in plan["source_files"]}
    if relative not in tracked or _sha256(data_path) != tracked[relative]["sha256"]:
        raise FigureError("data_file was not hash-bound during planning or has changed")
    fields, rows = _read_csv(data_path)
    chart = str(spec["chart_type"])
    x_name, y_name = str(spec["x"]), str(spec["y"])
    series_name = str(spec.get("series") or "")
    required = {x_name, y_name}
    if series_name:
        required.add(series_name)
    missing_columns = sorted(required - set(fields))
    if missing_columns:
        raise FigureError(f"CSV source is missing columns: {', '.join(missing_columns)}")
    missing_ok = spec.get("missing_policy") == "gap"
    exclusion_contract = list(spec.get("exclusions") or [])
    excluded_rows: set[int] = set()
    for exclusion in exclusion_contract:
        for row_number in exclusion["row_numbers"]:
            if row_number in excluded_rows:
                raise FigureError(f"CSV row {row_number} appears in more than one exclusion")
            excluded_rows.add(row_number)
    invalid_exclusions = sorted(row for row in excluded_rows if row > len(rows) + 1)
    if invalid_exclusions:
        raise FigureError(f"exclusion references nonexistent CSV rows: {invalid_exclusions}")
    normalized: list[dict[str, Any]] = []
    missing_x = missing_y = 0
    for index, row in enumerate(rows, start=2):
        if index in excluded_rows:
            continue
        x_value = _x_value(row.get(x_name, ""), column=x_name, row=index, missing_ok=missing_ok)
        y_value = _numeric(row.get(y_name, ""), column=y_name, row=index, missing_ok=missing_ok)
        if x_value is None:
            missing_x += 1
        if y_value is None:
            missing_y += 1
        if (x_value is None or y_value is None) and not missing_ok:
            raise FigureError(f"missing value at data row {index}")
        if x_value is None or y_value is None:
            continue
        normalized.append({"x": x_value, "y": y_value, "series": str(row.get(series_name) or "Data") if series_name else "Data", "row": index})
    if not normalized:
        raise FigureError("no usable rows remain after the explicit missing-value policy")
    if spec.get("y_scale") == "log" and any(item["y"] <= 0 for item in normalized):
        raise FigureError("log scale requires strictly positive y values")
    summary = spec["summary"]
    estimator = summary["estimator"]
    uncertainty = summary["uncertainty"]
    grouped: dict[tuple[str, float | str], list[float]] = {}
    for row in normalized:
        grouped.setdefault((row["series"], row["x"]), []).append(row["y"])
    points: list[dict[str, Any]] = []
    for group_index, ((series, x_value), values) in enumerate(sorted(grouped.items(), key=lambda item: (item[0][0], str(item[0][1])))):
        center = _mean(values) if estimator in {"mean", "raw"} else _median(values)
        lower = upper = center
        if uncertainty == "sd":
            spread = _sd(values)
            lower, upper = center - spread, center + spread
        elif uncertainty == "sem":
            spread = _sd(values) / math.sqrt(len(values))
            lower, upper = center - spread, center + spread
        elif uncertainty == "ci95":
            lower, upper = _bootstrap_ci(values, int(summary["seed"]) + group_index)
        points.append({"series": series, "x": x_value, "center": center, "lower": lower, "upper": upper, "n": len(values), "raw": values})
    statistics = {
        "data_file": relative,
        "data_sha256": _sha256(data_path),
        "rows_total": len(rows),
        "rows_used": len(normalized),
        "rows_excluded": len(excluded_rows),
        "exclusions": exclusion_contract,
        "missing_x": missing_x,
        "missing_y": missing_y,
        "missing_policy": spec["missing_policy"],
        "estimator": estimator,
        "uncertainty": uncertainty,
        "replicate_unit": str(summary.get("replicate_unit") or ""),
        "seed": summary.get("seed"),
        "chart_type": chart,
        "groups": points,
    }
    return statistics, normalized


def _matplotlib():
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
        from PIL import Image
        import pypdf
    except ImportError as exc:
        raise FigureError(f"missing P8 figure dependency: {exc.name}") from exc
    return matplotlib, plt, np, Image, pypdf


def _style_context(matplotlib: Any, palette: list[str]) -> dict[str, Any]:
    return {
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "font.size": 7,
        "axes.labelsize": 7,
        "xtick.labelsize": 6,
        "ytick.labelsize": 6,
        "legend.fontsize": 6,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.linewidth": 0.7,
        "legend.frameon": False,
        "svg.fonttype": "none",
        "svg.hashsalt": RENDERER_VERSION,
        "pdf.fonttype": 42,
        "savefig.facecolor": "white",
        "axes.prop_cycle": matplotlib.cycler(color=palette),
    }


def _render_statistical(fig: Any, ax: Any, spec: dict[str, Any], statistics: dict[str, Any], rows: list[dict[str, Any]], palette: list[str]) -> None:
    chart = spec["chart_type"]
    points = statistics["groups"]
    series_names = list(dict.fromkeys(point["series"] for point in points))
    emphasis = (spec.get("style") or {}).get("emphasis_series")
    color_map = {name: palette[index % len(palette)] for index, name in enumerate(series_names)}
    if emphasis in color_map:
        color_map[emphasis] = "#D55E00"
    if chart == "line":
        categorical_values = sorted({point["x"] for point in points if isinstance(point["x"], str)})
        category_map = {value: index for index, value in enumerate(categorical_values)}
        for index, series in enumerate(series_names):
            items = [point for point in points if point["series"] == series]
            x = [category_map.get(item["x"], item["x"]) for item in items]
            y = [item["center"] for item in items]
            ax.plot(x, y, label=series, color=color_map[series], marker=MARKERS[index % len(MARKERS)], linestyle=LINESTYLES[index % len(LINESTYLES)], linewidth=1.3, markersize=3.5)
            if statistics["uncertainty"] != "none":
                ax.fill_between(x, [item["lower"] for item in items], [item["upper"] for item in items], color=color_map[series], alpha=0.16, linewidth=0)
        if category_map:
            ax.set_xticks(list(category_map.values()), list(category_map.keys()))
        else:
            numeric_x = sorted({float(point["x"]) for point in points})
            if len(numeric_x) <= 12:
                ax.set_xticks(numeric_x)
    elif chart == "scatter":
        for index, series in enumerate(series_names):
            items = [row for row in rows if row["series"] == series]
            ax.scatter([row["x"] for row in items], [row["y"] for row in items], label=series, color=color_map[series], marker=MARKERS[index % len(MARKERS)], s=18, linewidths=0.4, edgecolors="white")
    elif chart == "bar":
        categories = sorted(set(point["x"] for point in points), key=str)
        width = 0.78 / max(1, len(series_names))
        for index, series in enumerate(series_names):
            items = {point["x"]: point for point in points if point["series"] == series}
            positions = [position + (index - (len(series_names) - 1) / 2) * width for position in range(len(categories))]
            centers = [items[value]["center"] for value in categories]
            errors = [[items[value]["center"] - items[value]["lower"] for value in categories], [items[value]["upper"] - items[value]["center"] for value in categories]]
            ax.bar(positions, centers, width=width * 0.9, label=series, color=color_map[series], edgecolor="#222222", linewidth=0.35, hatch=["", "//", "xx", ".."][index % 4], yerr=errors if statistics["uncertainty"] != "none" else None, capsize=2)
        ax.set_xticks(range(len(categories)), [f"{value:g}" if isinstance(value, (int, float)) else str(value) for value in categories])
        ax.set_ylim(bottom=0)
    elif chart == "box":
        grouped = []
        labels = []
        for series in series_names:
            grouped.append([row["y"] for row in rows if row["series"] == series])
            labels.append(series)
        artists = ax.boxplot(grouped, tick_labels=labels, patch_artist=True, showfliers=True)
        for index, box in enumerate(artists["boxes"]):
            box.set_facecolor(palette[index % len(palette)])
            box.set_alpha(0.65)
            box.set_hatch(["", "//", "xx", ".."][index % 4])
    elif chart == "histogram":
        for index, series in enumerate(series_names):
            values = [row["y"] for row in rows if row["series"] == series]
            ax.hist(values, bins="auto", histtype="step", linewidth=1.3, linestyle=LINESTYLES[index % len(LINESTYLES)], color=color_map[series], label=series)
    elif chart == "heatmap":
        x_values = sorted(set(row["x"] for row in rows), key=str)
        matrix = []
        for series in series_names:
            lookup = {point["x"]: point["center"] for point in points if point["series"] == series}
            matrix.append([lookup.get(value, float("nan")) for value in x_values])
        image = ax.imshow(matrix, aspect="auto", interpolation="nearest", cmap="viridis")
        ax.set_xticks(range(len(x_values)), [f"{value:g}" if isinstance(value, (int, float)) else str(value) for value in x_values])
        ax.set_yticks(range(len(series_names)), series_names)
        fig.colorbar(image, ax=ax, label=spec["y_label"])
    if chart not in {"box", "heatmap"} and len(series_names) > 1:
        ax.legend()
    ax.set_xlabel(spec["x_label"])
    ax.set_ylabel(spec["y_label"])
    if spec.get("y_scale") == "log":
        ax.set_yscale("log")
    if isinstance(spec.get("y_limits"), list):
        ax.set_ylim(*spec["y_limits"])
    ax.grid(axis="y", color="#D9D9D9", linewidth=0.4, alpha=0.65)


def _render_diagram(fig: Any, ax: Any, spec: dict[str, Any], palette: list[str]) -> None:
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Ellipse, Polygon, Rectangle

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    node_map = {node["id"]: node for node in spec["nodes"]}

    def boundary_point(source: dict[str, Any], target: dict[str, Any]) -> tuple[float, float]:
        sx, sy = float(source["x"]), float(source["y"])
        tx, ty = float(target["x"]), float(target["y"])
        dx, dy = tx - sx, ty - sy
        half_width = float(source.get("width", 0.22)) / 2
        half_height = float(source.get("height", 0.18)) / 2
        if dx == 0 and dy == 0:
            return sx, sy + half_height
        scale_x = half_width / abs(dx) if dx else float("inf")
        scale_y = half_height / abs(dy) if dy else float("inf")
        scale = min(scale_x, scale_y)
        return sx + dx * scale, sy + dy * scale

    for index, edge in enumerate(spec["edges"]):
        source, target = node_map[edge["from"]], node_map[edge["to"]]
        linestyle = {"solid": "-", "dashed": "--", "dotted": ":"}[edge.get("style", "solid")]
        if edge.get("curve"):
            start = (float(source["x"]) - 0.035, float(source["y"]) + float(source.get("height", 0.18)) / 2)
            end = (float(target["x"]) + 0.035, float(target["y"]) + float(target.get("height", 0.18)) / 2)
            connection = "arc3,rad=0.28"
        else:
            start = boundary_point(source, target)
            end = boundary_point(target, source)
            connection = "arc3,rad=0"
        arrow = FancyArrowPatch(
            start, end,
            arrowstyle="-|>", mutation_scale=8, linewidth=1.0, linestyle=linestyle,
            color="#444444", connectionstyle=connection, shrinkA=0, shrinkB=0, zorder=1,
        )
        ax.add_patch(arrow)
        if edge.get("label"):
            midpoint_x = (float(source["x"]) + float(target["x"])) / 2
            midpoint_y = (float(source["y"]) + float(target["y"])) / 2 + (0.24 if edge.get("curve") else 0.04)
            ax.text(midpoint_x, midpoint_y, str(edge["label"]), ha="center", va="center", fontsize=6, color="#444444", zorder=3)
    for index, node in enumerate(spec["nodes"]):
        x, y = float(node["x"]), float(node["y"])
        width, height = float(node.get("width", 0.22)), float(node.get("height", 0.18))
        color = palette[index % len(palette)]
        shape = node.get("shape", "rounded")
        if shape in {"rounded", "rect"}:
            patch = FancyBboxPatch((x - width / 2, y - height / 2), width, height, boxstyle="round,pad=0.012,rounding_size=0.018" if shape == "rounded" else "square,pad=0", facecolor=color + "22", edgecolor=color, linewidth=1.1, zorder=2)
        elif shape in {"circle", "ellipse"}:
            patch = Ellipse((x, y), width, height, facecolor=color + "22", edgecolor=color, linewidth=1.1, zorder=2)
        elif shape == "diamond":
            patch = Polygon([(x, y + height / 2), (x + width / 2, y), (x, y - height / 2), (x - width / 2, y)], facecolor=color + "22", edgecolor=color, linewidth=1.1, zorder=2)
        else:
            patch = Rectangle((x - width / 2, y - height / 2), width, height, facecolor=color + "22", edgecolor=color, linewidth=1.1, zorder=2)
        ax.add_patch(patch)
        ax.text(x, y, str(node["label"]), ha="center", va="center", fontsize=7, fontweight="semibold", color="#222222", zorder=3)


def _output_record(root: Path, path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(root).as_posix(), "sha256": _sha256(path), "bytes": path.stat().st_size}


def _reproduce_script(figure_id: str, spec_name: str) -> str:
    return (
        "#!/usr/bin/env python\n"
        "from pathlib import Path\n"
        "import json\n"
        "from academic_figure_core import reproduce_from_bundle\n"
        f"reproduce_from_bundle(Path(__file__).resolve().parents[3], {figure_id!r}, Path(__file__).with_name({spec_name!r}))\n"
    )


def render_academic_figure(root: str | os.PathLike[str], figure_id: str, spec: dict[str, Any]) -> dict[str, Any]:
    base = Path(root).expanduser().resolve()
    figure_id = _safe_figure_id(figure_id)
    state = _load_state(base, figure_id)
    plan = state["plan"]
    validate_figure_spec(spec, planned_kind=plan["figure_kind"])
    changed = [item["path"] for item in plan["source_files"] if not (base / item["path"]).is_file() or _sha256(base / item["path"]) != item["sha256"]]
    if changed:
        raise FigureError(f"planned source files changed: {', '.join(changed)}")
    revision = int(state.get("latest_revision") or 0) + 1
    output_dir = base / "figures" / figure_id / f"v{revision:03d}"
    if output_dir.exists() or output_dir.is_symlink():
        raise FigureError("append-only figure revision already exists")
    matplotlib, plt, _np, Image, _pypdf = _matplotlib()
    palette_name = str((spec.get("style") or {}).get("palette") or "okabe_ito_on_white")
    palette = PALETTES[palette_name]
    statistics: dict[str, Any] | None = None
    rows: list[dict[str, Any]] = []
    if plan["figure_kind"] == "statistical":
        statistics, rows = _prepare_statistical(base, plan, spec)
    output_dir.mkdir(parents=True, exist_ok=False)
    width_in, height_in = float(plan["width_mm"]) / 25.4, float(plan["height_mm"]) / 25.4
    with matplotlib.rc_context(_style_context(matplotlib, palette)):
        fig, ax = plt.subplots(figsize=(width_in, height_in), layout="constrained")
        if plan["figure_kind"] == "statistical":
            _render_statistical(fig, ax, spec, statistics or {}, rows, palette)
        else:
            _render_diagram(fig, ax, spec, palette)
        svg_path = output_dir / f"{figure_id}.svg"
        pdf_path = output_dir / f"{figure_id}.pdf"
        png_path = output_dir / f"{figure_id}.png"
        fig.savefig(svg_path, format="svg", metadata={"Title": str(spec["claim"]), "Date": None})
        fig.savefig(pdf_path, format="pdf", metadata={
            "Title": str(spec["claim"]), "Creator": RENDERER_VERSION,
            "CreationDate": None, "ModDate": None,
        })
        fig.savefig(png_path, format="png", dpi=300, metadata={"Software": RENDERER_VERSION})
        plt.close(fig)
    with Image.open(png_path) as image:
        image.verify()
    spec_path = output_dir / f"{figure_id}.spec.json"
    _atomic_json(spec_path, spec)
    reproduce_path = output_dir / f"reproduce_{figure_id}.py"
    reproduce_path.write_text(_reproduce_script(figure_id, spec_path.name), encoding="utf-8", newline="\n")
    outputs = {
        "svg": _output_record(base, svg_path),
        "pdf": _output_record(base, pdf_path),
        "png": _output_record(base, png_path),
        "spec": _output_record(base, spec_path),
        "reproduce": _output_record(base, reproduce_path),
    }
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "renderer_version": RENDERER_VERSION,
        "figure_id": figure_id,
        "revision": revision,
        "plan_sha256": plan["plan_sha256"],
        "spec_sha256": _hash_value(spec),
        "source_files": plan["source_files"],
        "statistics": statistics,
        "claim": spec["claim"],
        "alt_text": spec["alt_text"],
        "physical_size_mm": [plan["width_mm"], plan["height_mm"]],
        "outputs": outputs,
        "rendered_at": utc_now(),
    }
    manifest["manifest_sha256"] = _hash_value(manifest)
    manifest_path = output_dir / "manifest.json"
    _atomic_json(manifest_path, manifest)
    outputs["manifest"] = _output_record(base, manifest_path)
    render = {
        "status": "REVIEW_REQUIRED",
        "revision": revision,
        "spec_sha256": manifest["spec_sha256"],
        "manifest_sha256": manifest["manifest_sha256"],
        "statistics": statistics,
        "outputs": outputs,
    }
    state.update({
        "status": "PROGRAMMATIC_AUDIT_REQUIRED",
        "reason": "the rendered bundle has not passed exported-file inspection",
        "latest_revision": revision,
        "render": render,
        "audit": None,
        "visual_review": None,
        "receipt": None,
    })
    _save_state(base, figure_id, state)
    return render


def reproduce_from_bundle(root: Path, figure_id: str, spec_path: Path) -> dict[str, Any]:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    return render_academic_figure(root, figure_id, spec)


def _verify_render_files(base: Path, state: dict[str, Any]) -> None:
    render = state.get("render")
    if not isinstance(render, dict):
        raise FigureError("no rendered figure bundle exists")
    for name, item in render.get("outputs", {}).items():
        if not isinstance(item, dict):
            raise FigureError(f"invalid output record: {name}")
        path, relative = _safe_file(base, str(item.get("path") or ""))
        if relative != item.get("path") or _sha256(path) != item.get("sha256"):
            raise FigureError(f"rendered output changed: {name}")
    manifest_path = base / render["outputs"]["manifest"]["path"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise FigureError(f"figure manifest is invalid: {exc}") from exc
    saved_hash = manifest.get("manifest_sha256")
    unsigned = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    if saved_hash != _hash_value(unsigned) or saved_hash != render.get("manifest_sha256"):
        raise FigureError("figure manifest integrity check failed")


def _svg_audit(path: Path) -> dict[str, Any]:
    from xml.etree import ElementTree

    try:
        root = ElementTree.parse(path).getroot()
    except ElementTree.ParseError as exc:
        raise FigureError(f"SVG is invalid: {exc}") from exc
    view_box = root.attrib.get("viewBox")
    text_count = sum(1 for element in root.iter() if element.tag.endswith("text"))
    embedded_rasters = sum(1 for element in root.iter() if element.tag.endswith("image"))
    if not view_box or text_count == 0:
        raise FigureError("SVG must contain a viewBox and editable text")
    if embedded_rasters:
        raise FigureError("SVG contains embedded raster images")
    return {"view_box": view_box, "text_elements": text_count, "embedded_rasters": embedded_rasters}


def _pdf_audit(reader: Any) -> dict[str, int]:
    extracted = "".join(page.extract_text() or "" for page in reader.pages)
    embedded_rasters = 0
    for page in reader.pages:
        resources = page.get("/Resources") or {}
        xobjects = resources.get("/XObject") if hasattr(resources, "get") else None
        if xobjects:
            for _name, reference in xobjects.get_object().items():
                obj = reference.get_object()
                if obj.get("/Subtype") == "/Image":
                    embedded_rasters += 1
    return {"extracted_text_characters": len(extracted.strip()), "embedded_rasters": embedded_rasters}


def audit_academic_figure(root: str | os.PathLike[str], figure_id: str) -> dict[str, Any]:
    base = Path(root).expanduser().resolve()
    figure_id = _safe_figure_id(figure_id)
    state = _load_state(base, figure_id)
    _verify_render_files(base, state)
    matplotlib, _plt, _np, Image, pypdf = _matplotlib()
    render = state["render"]
    png_path = base / render["outputs"]["png"]["path"]
    pdf_path = base / render["outputs"]["pdf"]["path"]
    svg_path = base / render["outputs"]["svg"]["path"]
    with Image.open(png_path) as image:
        width_px, height_px = image.size
        dpi = image.info.get("dpi", (0, 0))
    reader = pypdf.PdfReader(str(pdf_path))
    if len(reader.pages) != 1:
        raise FigureError("publication figure PDF must contain exactly one page")
    page = reader.pages[0]
    pdf_result = _pdf_audit(reader)
    if pdf_result["extracted_text_characters"] == 0:
        raise FigureError("PDF contains no extractable vector text")
    if pdf_result["embedded_rasters"]:
        raise FigureError("PDF contains embedded raster images")
    width_pt = float(page.mediabox.width)
    height_pt = float(page.mediabox.height)
    expected_width = float(state["plan"]["width_mm"]) / 25.4 * 72
    expected_height = float(state["plan"]["height_mm"]) / 25.4 * 72
    if abs(width_pt - expected_width) > 1.5 or abs(height_pt - expected_height) > 1.5:
        raise FigureError("PDF physical dimensions do not match the planned final size")
    expected_px = [round(float(state["plan"]["width_mm"]) / 25.4 * 300), round(float(state["plan"]["height_mm"]) / 25.4 * 300)]
    if abs(width_px - expected_px[0]) > 2 or abs(height_px - expected_px[1]) > 2:
        raise FigureError("PNG dimensions do not match 300 DPI at the planned final size")
    svg_result = _svg_audit(svg_path)
    audit = {
        "status": "VISUAL_REVIEW_REQUIRED",
        "audited_at": utc_now(),
        "revision": render["revision"],
        "outputs_sha256": {name: item["sha256"] for name, item in render["outputs"].items()},
        "checks": {
            "svg": svg_result,
            "pdf": {"pages": 1, "width_pt": width_pt, "height_pt": height_pt, **pdf_result},
            "png": {"width_px": width_px, "height_px": height_px, "dpi_metadata": list(dpi)},
            "dependencies": {
                "python": sys.version.split()[0],
                "matplotlib": matplotlib.__version__,
                "pillow": getattr(Image, "__version__", "unknown"),
                "pypdf": getattr(pypdf, "__version__", "unknown"),
            },
        },
        "limitations": [
            "programmatic checks do not prove scientific correctness",
            "programmatic checks do not certify accessibility or journal acceptance",
        ],
    }
    audit["audit_sha256"] = _hash_value(audit)
    state.update({
        "status": "VISUAL_REVIEW_REQUIRED",
        "reason": "inspect the actual PNG at final physical size before PASS",
        "audit": audit,
        "visual_review": None,
        "receipt": None,
    })
    _save_state(base, figure_id, state)
    return audit


def record_visual_review(
    root: str | os.PathLike[str],
    figure_id: str,
    *,
    rendered_png_sha256: str,
    review_method: str,
    checks: dict[str, Any],
    issues: list[str] | None,
) -> dict[str, Any]:
    base = Path(root).expanduser().resolve()
    figure_id = _safe_figure_id(figure_id)
    state = _load_state(base, figure_id)
    _verify_render_files(base, state)
    if (state.get("audit") or {}).get("status") != "VISUAL_REVIEW_REQUIRED":
        raise FigureError("programmatic audit must pass before visual review")
    expected_png = state["render"]["outputs"]["png"]["sha256"]
    if rendered_png_sha256 != expected_png:
        raise FigureError("visual review is not bound to the current rendered PNG")
    if str(review_method) != "actual_png_at_final_size":
        raise FigureError("review_method must be actual_png_at_final_size")
    expected_checks = set(BASE_VISUAL_CHECKS)
    if state["plan"].get("venue_contract") is not None:
        expected_checks.add(VENUE_VISUAL_CHECK)
    if not isinstance(checks, dict) or set(checks) != expected_checks or any(value is not True for value in checks.values()):
        raise FigureError("every final-size visual review check must be explicitly true")
    if issues not in (None, []):
        raise FigureError("unresolved visual review issues require a new render")
    review = {
        "status": "PASS",
        "reviewed_at": utc_now(),
        "rendered_png_sha256": expected_png,
        "review_method": review_method,
        "checks": checks,
        "venue_contract_sha256": (state["plan"].get("venue_contract") or {}).get("contract_sha256"),
        "issues": [],
    }
    review["review_sha256"] = _hash_value(review)
    receipt = {
        "status": "PASS",
        "figure_id": figure_id,
        "plan_sha256": state["plan"]["plan_sha256"],
        "revision": state["render"]["revision"],
        "manifest_sha256": state["render"]["manifest_sha256"],
        "audit_sha256": state["audit"]["audit_sha256"],
        "review_sha256": review["review_sha256"],
        "outputs_sha256": {name: item["sha256"] for name, item in state["render"]["outputs"].items()},
        "venue_contract_sha256": (state["plan"].get("venue_contract") or {}).get("contract_sha256"),
        "issued_at": utc_now(),
    }
    receipt["receipt_sha256"] = _hash_value(receipt)
    state.update({"status": "PASS", "reason": "programmatic and final-size visual checks passed", "visual_review": review, "receipt": receipt})
    _save_state(base, figure_id, state)
    return receipt


def get_academic_figure_status(root: str | os.PathLike[str], figure_id: str) -> dict[str, Any]:
    base = Path(root).expanduser().resolve()
    figure_id = _safe_figure_id(figure_id)
    path = _state_path(base, figure_id)
    if not path.is_file():
        return {"status": "NOT_PLANNED", "reason": "academic figure has not been planned", "figure_id": figure_id}
    state = _load_state(base, figure_id)
    source_changes = [item["path"] for item in state["plan"]["source_files"] if not (base / item["path"]).is_file() or _sha256(base / item["path"]) != item["sha256"]]
    try:
        if state.get("render"):
            _verify_render_files(base, state)
    except FigureError as exc:
        state.update({"status": "RENDER_REQUIRED", "reason": str(exc), "audit": None, "visual_review": None, "receipt": None})
        return _save_state(base, figure_id, state)
    if source_changes:
        state.update({"status": "REPLAN_REQUIRED", "reason": f"source files changed: {', '.join(source_changes)}", "audit": None, "visual_review": None, "receipt": None})
        _save_state(base, figure_id, state)
    if state.get("status") == "PASS":
        receipt = state.get("receipt")
        if not isinstance(receipt, dict):
            raise FigureError("academic figure receipt is missing")
        saved = receipt.get("receipt_sha256")
        unsigned = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
        if saved != _hash_value(unsigned):
            raise FigureError("academic figure receipt integrity check failed")
    return state


def _image_integrity_path(root: Path, audit_id: str) -> Path:
    return root / ".research-guard" / "image-integrity" / f"{audit_id}.json"


def _dhash(image: Any) -> str:
    from PIL import Image as PillowImage

    resized = image.convert("L").resize((9, 8), PillowImage.Resampling.LANCZOS)
    pixels = list(resized.getdata())
    bits = 0
    for row in range(8):
        for column in range(8):
            bits = (bits << 1) | int(pixels[row * 9 + column] > pixels[row * 9 + column + 1])
    return f"{bits:016x}"


def _hash_distance(left: str, right: str) -> int:
    return (int(left, 16) ^ int(right, 16)).bit_count()


def _region_hashes(image: Any) -> list[dict[str, Any]]:
    from PIL import ImageStat

    converted = image.convert("L")
    width, height = converted.size
    cells: list[dict[str, Any]] = []
    grid = 4
    for row in range(grid):
        for column in range(grid):
            left, upper = width * column // grid, height * row // grid
            right, lower = width * (column + 1) // grid, height * (row + 1) // grid
            crop = converted.crop((left, upper, right, lower))
            if min(crop.size) < 16 or float(ImageStat.Stat(crop).stddev[0]) < 4.0:
                continue
            cells.append({
                "region": [left, upper, right, lower], "dhash": _dhash(crop),
                "pixel_sha256": hashlib.sha256(crop.tobytes()).hexdigest(),
            })
    return cells


def audit_scientific_image_integrity(
    root: str | os.PathLike[str],
    audit_id: str,
    *,
    images: list[dict[str, Any]],
    transformations: list[dict[str, Any]],
    approximate_image_distance: int = 5,
    approximate_region_distance: int = 3,
) -> dict[str, Any]:
    """Bind image provenance and surface review evidence without inferring misconduct."""
    from PIL import ExifTags, Image, ImageStat, UnidentifiedImageError

    base = Path(root).expanduser().resolve()
    identifier = str(audit_id or "").strip().lower()
    if not IMAGE_AUDIT_ID.fullmatch(identifier):
        raise FigureError("image audit_id must use lowercase letters, digits, and hyphens")
    if not isinstance(images, list) or not images:
        raise FigureError("scientific image integrity audit requires image records")
    if not isinstance(transformations, list):
        raise FigureError("transformations must be an array")
    if not (0 <= int(approximate_image_distance) <= 12 and 0 <= int(approximate_region_distance) <= 8):
        raise FigureError("image similarity thresholds are outside their frozen safe ranges")
    transform_map: dict[str, dict[str, Any]] = {}
    hard_failures: list[dict[str, Any]] = []
    for index, transformation in enumerate(transformations):
        if not isinstance(transformation, dict):
            raise FigureError(f"transformation {index} must be an object")
        transform_id = str(transformation.get("id") or "").strip()
        operation = str(transformation.get("operation") or "").strip().lower()
        justification = str(transformation.get("justification") or "").strip()
        if not IMAGE_RECORD_ID.fullmatch(transform_id) or transform_id in transform_map:
            raise FigureError(f"transformation {index} has an illegal or duplicate id")
        if operation in PROHIBITED_IMAGE_TRANSFORMS:
            hard_failures.append({"type": "prohibited_transformation", "transformation_id": transform_id, "operation": operation})
        elif operation not in ALLOWED_IMAGE_TRANSFORMS:
            hard_failures.append({"type": "unrecognized_transformation", "transformation_id": transform_id, "operation": operation})
        if len(justification) < 12:
            hard_failures.append({"type": "missing_transformation_justification", "transformation_id": transform_id})
        transform_map[transform_id] = dict(transformation)
    records: list[dict[str, Any]] = []
    record_map: dict[str, dict[str, Any]] = {}
    for index, image_record in enumerate(images):
        if not isinstance(image_record, dict):
            raise FigureError(f"image record {index} must be an object")
        image_id = str(image_record.get("id") or "").strip()
        role = str(image_record.get("role") or "").strip().lower()
        if not IMAGE_RECORD_ID.fullmatch(image_id) or image_id in record_map or role not in IMAGE_ROLES:
            raise FigureError(f"image record {index} has an illegal/duplicate id or role")
        path, relative = _safe_file(base, str(image_record.get("path") or ""))
        source_id = str(image_record.get("source_id") or "").strip() or None
        transform_ids = [str(value) for value in (image_record.get("transformation_ids") or [])]
        unknown = sorted(set(transform_ids) - set(transform_map))
        if unknown:
            hard_failures.append({"type": "unknown_transformations", "image_id": image_id, "ids": unknown})
        if role != "original" and (not source_id or not transform_ids):
            hard_failures.append({"type": "processed_image_missing_provenance", "image_id": image_id})
        try:
            with Image.open(path) as loaded:
                loaded.verify()
            with Image.open(path) as loaded:
                loaded.load()
                width, height = loaded.size
                if width * height > 100_000_000:
                    raise FigureError(f"image {image_id} exceeds the 100 megapixel audit bound")
                rgb = loaded.convert("RGB")
                stat = ImageStat.Stat(rgb)
                extrema = rgb.getextrema()
                total = max(1, width * height * 3)
                histogram = rgb.histogram()
                clipped = sum(histogram[offset] + histogram[offset + 255] for offset in (0, 256, 512))
                text_metadata = {
                    str(key): str(value)[:240] for key, value in loaded.info.items()
                    if isinstance(value, (str, int, float)) and not isinstance(value, bool)
                }
                exif_metadata = {
                    str(ExifTags.TAGS.get(key, key)): str(value)[:240]
                    for key, value in loaded.getexif().items()
                    if isinstance(value, (str, int, float)) and not isinstance(value, bool)
                }
                record = {
                    "id": image_id, "role": role, "path": relative, "sha256": _sha256(path),
                    "bytes": path.stat().st_size, "format": loaded.format, "mode": loaded.mode,
                    "dimensions": [width, height], "source_id": source_id,
                    "transformation_ids": transform_ids, "metadata_keys": sorted(str(key) for key in loaded.info),
                    "text_metadata": text_metadata, "exif_metadata": exif_metadata,
                    "channel_means": [round(float(value), 6) for value in stat.mean],
                    "channel_extrema": [list(value) for value in extrema],
                    "clipped_channel_fraction": clipped / total,
                    "dhash": _dhash(rgb), "pixel_sha256": hashlib.sha256(rgb.tobytes()).hexdigest(),
                    "regions": _region_hashes(rgb),
                }
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise FigureError(f"image {image_id} cannot be decoded safely: {exc}") from exc
        records.append(record)
        record_map[image_id] = record
    for record in records:
        if record["source_id"] and record["source_id"] not in record_map:
            hard_failures.append({"type": "missing_source_image", "image_id": record["id"], "source_id": record["source_id"]})
        elif record["source_id"] and record_map[record["source_id"]]["role"] != "original":
            hard_failures.append({"type": "source_image_is_not_original", "image_id": record["id"], "source_id": record["source_id"]})
    for transform_id, transformation in transform_map.items():
        applies_to = transformation.get("applies_to")
        if not isinstance(applies_to, list) or not applies_to:
            hard_failures.append({"type": "transformation_missing_applies_to", "transformation_id": transform_id})
            continue
        unknown_images = sorted({str(value) for value in applies_to} - set(record_map))
        if unknown_images:
            hard_failures.append({"type": "transformation_unknown_images", "transformation_id": transform_id, "image_ids": unknown_images})
        for image_id in applies_to:
            if image_id in record_map and transform_id not in record_map[image_id]["transformation_ids"]:
                hard_failures.append({"type": "transformation_reverse_link_missing", "transformation_id": transform_id, "image_id": image_id})
    flags: list[dict[str, Any]] = []
    for index, left in enumerate(records):
        if left["clipped_channel_fraction"] > 0.20:
            flags.append({"type": "high_pixel_clipping", "image_id": left["id"], "fraction": left["clipped_channel_fraction"]})
        metadata_text = " ".join([*left["text_metadata"].values(), *left["exif_metadata"].values()]).casefold()
        editing_signals = sorted({
            term for term in ("photoshop", "gimp", "generative", "stable diffusion", "dall-e", "midjourney")
            if term in metadata_text
        })
        if editing_signals:
            flags.append({"type": "editing_software_metadata", "image_id": left["id"], "signals": editing_signals})
        for left_index, left_region in enumerate(left["regions"]):
            for right_region in left["regions"][left_index + 1:]:
                if left_region["pixel_sha256"] == right_region["pixel_sha256"]:
                    flags.append({"type": "exact_duplicate_region_within_image", "image_id": left["id"], "regions": [left_region["region"], right_region["region"]]})
                else:
                    distance = _hash_distance(left_region["dhash"], right_region["dhash"])
                    if distance <= int(approximate_region_distance):
                        flags.append({"type": "approximate_duplicate_region_within_image", "image_id": left["id"], "regions": [left_region["region"], right_region["region"]], "distance": distance})
        for right in records[index + 1:]:
            declared_relation = left["source_id"] == right["id"] or right["source_id"] == left["id"] or (
                left["source_id"] is not None and left["source_id"] == right["source_id"]
            )
            if left["pixel_sha256"] == right["pixel_sha256"]:
                flags.append({"type": "exact_duplicate_image", "image_ids": [left["id"], right["id"]], "declared_relation": declared_relation})
            else:
                distance = _hash_distance(left["dhash"], right["dhash"])
                if distance <= int(approximate_image_distance):
                    flags.append({"type": "approximate_duplicate_image", "image_ids": [left["id"], right["id"]], "distance": distance, "declared_relation": declared_relation})
            for left_region in left["regions"]:
                for right_region in right["regions"]:
                    if left_region["pixel_sha256"] == right_region["pixel_sha256"]:
                        flags.append({"type": "exact_duplicate_region", "image_ids": [left["id"], right["id"]], "regions": [left_region["region"], right_region["region"]], "declared_relation": declared_relation})
                    else:
                        distance = _hash_distance(left_region["dhash"], right_region["dhash"])
                        if distance <= int(approximate_region_distance):
                            flags.append({"type": "approximate_duplicate_region", "image_ids": [left["id"], right["id"]], "regions": [left_region["region"], right_region["region"]], "distance": distance, "declared_relation": declared_relation})
    # Cap evidence, not scanning, so a repeated grid cannot inflate state indefinitely.
    flags = flags[:500]
    result = {
        "schema_version": 1,
        "status": "FAIL" if hard_failures else "REVIEW_REQUIRED",
        "audit_id": identifier,
        "checked_at": utc_now(),
        "images": records,
        "transformations": transformations,
        "hard_failures": hard_failures,
        "review_flags": flags,
        "thresholds": {
            "approximate_image_hamming_distance": int(approximate_image_distance),
            "approximate_region_hamming_distance": int(approximate_region_distance),
            "clipped_channel_fraction": 0.20,
        },
        "conclusion_boundary": "Automated evidence flags require expert review and are not findings of fabrication, falsification, or fraud.",
    }
    result["audit_sha256"] = _hash_value(result)
    _atomic_json(_image_integrity_path(base, identifier), result)
    return result


def get_scientific_image_integrity_status(root: str | os.PathLike[str], audit_id: str) -> dict[str, Any]:
    base = Path(root).expanduser().resolve()
    identifier = str(audit_id or "").strip().lower()
    path = _image_integrity_path(base, identifier)
    if not path.is_file():
        return {"status": "NOT_FOUND", "audit_id": identifier}
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FigureError(f"scientific image integrity state is invalid: {exc}") from exc
    saved = result.get("audit_sha256")
    unsigned = {key: value for key, value in result.items() if key != "audit_sha256"}
    if saved != _hash_value(unsigned):
        raise FigureError("scientific image integrity receipt failed its hash check")
    changes = [
        record["path"] for record in result.get("images", [])
        if not (base / record["path"]).is_file() or _sha256(base / record["path"]) != record["sha256"]
    ]
    if changes:
        return {**result, "status": "AUDIT_REQUIRED", "reason": f"image inputs changed: {', '.join(changes)}"}
    return result


def record_scientific_image_review(
    root: str | os.PathLike[str], audit_id: str, *, audit_sha256: str,
    review_method: str, decisions: list[dict[str, Any]], reviewer: str,
) -> dict[str, Any]:
    base = Path(root).expanduser().resolve()
    current = get_scientific_image_integrity_status(base, audit_id)
    if current.get("status") != "REVIEW_REQUIRED":
        raise FigureError("a current hard-failure-free image audit is required before expert review")
    if str(audit_sha256) != current.get("audit_sha256"):
        raise FigureError("expert review is not bound to the current image audit")
    if str(review_method) != "expert_original_resolution":
        raise FigureError("review_method must be expert_original_resolution")
    if len(str(reviewer or "").strip()) < 3:
        raise FigureError("reviewer identity or role is required")
    flags = current.get("review_flags") or []
    expected = {f"flag-{index + 1}" for index in range(len(flags))}
    if not isinstance(decisions, list):
        raise FigureError("image review decisions must be an array")
    normalized: dict[str, dict[str, Any]] = {}
    for decision in decisions:
        if not isinstance(decision, dict):
            raise FigureError("each image review decision must be an object")
        flag_id = str(decision.get("flag_id") or "")
        outcome = str(decision.get("outcome") or "")
        rationale = str(decision.get("rationale") or "").strip()
        if flag_id in normalized or flag_id not in expected:
            raise FigureError(f"unknown or duplicate image flag decision: {flag_id}")
        if outcome not in {"explained_expected_relation", "acceptable_artifact", "correction_required"}:
            raise FigureError(f"invalid image review outcome: {outcome}")
        if len(rationale) < 20:
            raise FigureError(f"image review decision {flag_id} needs a concrete rationale")
        normalized[flag_id] = {"flag_id": flag_id, "outcome": outcome, "rationale": rationale}
    if set(normalized) != expected:
        raise FigureError("expert image review must decide every current automatic flag")
    unresolved = [flag_id for flag_id, decision in normalized.items() if decision["outcome"] == "correction_required"]
    review = {
        "schema_version": 1,
        "status": "CORRECTION_REQUIRED" if unresolved else "PASS",
        "audit_id": current["audit_id"], "audit_sha256": current["audit_sha256"],
        "review_method": review_method, "reviewer": str(reviewer).strip(),
        "decisions": [normalized[key] for key in sorted(normalized)],
        "unresolved_flags": unresolved, "reviewed_at": utc_now(),
        "conclusion_boundary": "The review resolves recorded evidence flags only and is not a finding about research intent or misconduct.",
    }
    review["review_sha256"] = _hash_value(review)
    state = {**current, "status": review["status"], "expert_review": review}
    state["audit_sha256"] = _hash_value({key: value for key, value in state.items() if key != "audit_sha256"})
    _atomic_json(_image_integrity_path(base, current["audit_id"]), state)
    return state


def verify_academic_figure(root: str | os.PathLike[str], figure_id: str) -> dict[str, Any]:
    state = get_academic_figure_status(root, figure_id)
    if state.get("status") != "PASS":
        if state.get("status") == "VISUAL_REVIEW_REQUIRED":
            raise FigureError("final-size visual review has not passed")
        raise FigureError(f"academic figure is not verified: {state.get('status')} - {state.get('reason')}")
    return dict(state["receipt"])
