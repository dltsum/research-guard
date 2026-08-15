from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from language_guard_core import (
    LanguageError,
    TEXT_SUFFIXES,
    analyze_language,
    finalize_language_review,
    get_language_status,
    plan_language_review,
    verify_language_receipt,
)
from academic_figure_core import FigureError, get_scientific_image_integrity_status, verify_academic_figure
from openreview_calibration_core import OpenReviewCalibrationError, get_openreview_calibration


class AuditError(ValueError):
    pass


ROLE_TEMPLATES: dict[str, dict[str, Any]] = {
    "journal_venue_fit": {
        "mission": "Verify scope, audience, article type, and current venue policies.",
        "online_scope": ["official venue scope", "submission policy", "reporting checklist"],
        "numeric_checks": ["word/page/figure limits", "sample and effect-size claims"],
    },
    "methodology_statistics": {
        "mission": "Audit design, assumptions, statistics, controls, and claim strength.",
        "online_scope": ["current reporting standard", "benchmark protocol when externally defined"],
        "numeric_checks": ["recompute reported comparisons", "units, denominators, uncertainty, and significance"],
    },
    "domain_literature": {
        "mission": "Check coverage, attribution, collision risk, and claim-to-source alignment.",
        "online_scope": ["primary literature", "corrections/retractions", "current index metadata"],
        "numeric_checks": ["cross-check quantitative statements against linked primary sources"],
    },
    "interdisciplinary_impact": {
        "mission": "Audit transfer claims, external validity, impact, and cross-domain terminology.",
        "online_scope": ["domain standards", "external datasets", "current policy or impact facts"],
        "numeric_checks": ["compare population, scale, and domain baselines on common units"],
    },
    "adversarial_logic": {
        "mission": "Try to falsify the central argument and expose unsupported alternatives.",
        "online_scope": ["counterevidence", "known failure modes", "contradictory primary sources"],
        "numeric_checks": ["stress-test boundary values and claimed improvements"],
    },
    "formal_math_lean": {
        "mission": "Cross-check logical propositions with Lean, dimensions with Pint, algebra with SymPy, parameter feasibility with Z3, and protocol-admitted numerical boundaries.",
        "online_scope": ["external definitions and standards used by the formalization"],
        "numeric_checks": ["report Lean, Pint, SymPy, Z3, and numerical/protocol outcomes separately; check every parameter is legal and used"],
    },
    "code_experiment_integrity": {
        "mission": "Audit executable paths, experiment provenance, evaluation validity, and result integrity.",
        "online_scope": ["dataset/license/version", "software/API version", "benchmark and leaderboard protocol"],
        "numeric_checks": ["recompute tables", "verify seeds/configs", "check aggregation and result-file provenance"],
    },
    "openreview_calibration": {
        "mission": "Calibrate review coverage against public OpenReview schemas without predicting acceptance.",
        "online_scope": ["official OpenReview API v2 notes", "clickable public forum records"],
        "numeric_checks": ["compare category coverage counts and denominators; never treat keyword frequency as review severity"],
    },
    "scientific_image_integrity": {
        "mission": "Audit image provenance, declared transformations, duplicate evidence, metadata, and pixel anomalies for expert review.",
        "online_scope": ["current venue image-integrity policy when applicable"],
        "numeric_checks": ["verify dimensions, clipping fractions, image/region hash distances, and threshold sensitivity"],
    },
}


FORMULA_TERMS = re.compile(
    r"\b(?:formulas?|equations?|theorems?|lemmas?|proofs?|derive|derivation|mathematical|lean|pint|sympy|z3|dimensions?|units?|constraints?|overflow|boundar(?:y|ies)|limits?)\b|"
    r"公式|方程|定理|引理|证明|推导|数学|参数",
    re.IGNORECASE,
)
EXPERIMENT_TERMS = re.compile(
    r"\b(?:code|implementations?|experiments?|results?|metrics?|datasets?|benchmarks?|seeds?|ablations?|evaluations?)\b|"
    r"代码|实现|实验|结果|指标|数据集|基准|随机种子|消融|评测",
    re.IGNORECASE,
)
LITERATURE_TERMS = re.compile(
    r"\b(?:literature|citations?|references?|related work|prior work|novelty|collisions?|paper search|arxiv|doi)\b|"
    r"文献|引用|参考文献|相关工作|已有工作|前沿|撞车|查重|检索",
    re.IGNORECASE,
)
VENUE_TERMS = re.compile(r"\b(?:journal|venue|conference|submission|submit|editor)\b|期刊|会议|投稿|编辑", re.IGNORECASE)
IMPACT_TERMS = re.compile(r"\b(?:impact|interdisciplinary|cross-domain|transfer)\b|影响|跨学科|跨领域|迁移", re.IGNORECASE)
FIGURE_TERMS = re.compile(
    r"\b(?:figures?|plots?|charts?|diagrams?|visuali[sz]ations?)\b|"
    r"科研图|学术图|论文图|统计图|向量图|架构图|流程图|可视化",
    re.IGNORECASE,
)
OPENREVIEW_TERMS = re.compile(r"\b(?:openreview|reviewer calibration|review calibration|public reviews?)\b|审稿校准|审稿人校准", re.IGNORECASE)
IMAGE_INTEGRITY_TERMS = re.compile(
    r"\b(?:scientific image integrity|image forensics?|duplicate regions?|image manipulation|microscopy integrity)\b|科研图像完整性|图像完整性|重复区域|图像取证",
    re.IGNORECASE,
)


TEXT_MANUSCRIPT_SUFFIXES = {".tex", ".md", ".markdown", ".txt", ".rst", ".qmd"}
LATEX_CITATION = re.compile(r"\\cite[a-zA-Z*]*\{([^}]+)\}")
PANDOC_CITATION = re.compile(r"(?<![\w.-])@([A-Za-z0-9_:.+-]+)")
NUMERIC_CLAIM = re.compile(r"(?<![\w.])[-+]?(?:\d+(?:,\d{3})*(?:\.\d+)?|\.\d+)\s*(?:%|％)?")
COMPARATIVE_CLAIM = re.compile(
    r"\b(?:improv(?:e|es|ed|ement)|outperform(?:s|ed)?|higher|lower|better|worse|versus|vs\.?|compared)\b|"
    r"提高|提升|下降|降低|优于|劣于|超过|相比|比较|显著",
    re.IGNORECASE,
)
SCOPE_CLAIM = re.compile(
    r"\b(?:all|every|always|never|first|novel|state[- ]of[- ]the[- ]art|generaliz(?:e|es|ed|ation)|universally)\b|"
    r"所有|全部|始终|从不|首次|首个|创新|最先进|泛化|普遍",
    re.IGNORECASE,
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def _state_path(root: str | os.PathLike[str]) -> Path:
    return Path(root).expanduser().resolve() / ".research-guard" / "paper-audit-state.json"


def _sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def _tracked_files(root: Path, values: list[str] | None, label: str) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for value in values or []:
        path = (root / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError as exc:
            raise AuditError(f"{label} must stay inside project_root: {value}") from exc
        if not path.is_file():
            raise AuditError(f"{label} does not exist: {relative}")
        result.append({"path": relative, "sha256": _sha256(path), "kind": label.removesuffix(" file")})
    return sorted(result, key=lambda item: item["path"])


def _select_roles(text: str, claim_types: set[str] | None = None) -> tuple[list[str], dict[str, bool]]:
    claim_types = claim_types or set()
    signals = {
        "formula": bool(FORMULA_TERMS.search(text)),
        "experiment": bool(EXPERIMENT_TERMS.search(text)),
        "literature": bool(LITERATURE_TERMS.search(text)) or "bibliographic" in claim_types,
        "venue": bool(VENUE_TERMS.search(text)),
        "impact": bool(IMPACT_TERMS.search(text)),
        "openreview": bool(OPENREVIEW_TERMS.search(text)),
        "image_integrity": bool(IMAGE_INTEGRITY_TERMS.search(text)),
    }
    roles: list[str] = []
    mandatory = [
        (signals["formula"], "formal_math_lean"),
        (signals["experiment"], "code_experiment_integrity"),
        (signals["openreview"], "openreview_calibration"),
        (signals["image_integrity"], "scientific_image_integrity"),
        (signals["literature"], "domain_literature"),
    ]
    for active, role in mandatory:
        if active and role not in roles:
            roles.append(role)
    optional = []
    if signals["venue"]:
        optional.append("journal_venue_fit")
    if signals["impact"]:
        optional.append("interdisciplinary_impact")
    optional.extend(["methodology_statistics", "adversarial_logic", "domain_literature"])
    for role in optional:
        if len(roles) >= 2:
            break
        if role not in roles:
            roles.append(role)
    if len(roles) < 2:
        raise AuditError("router could not select the minimum two roles")
    return roles[:3], signals


def _claim_id(path: str, line_number: int, claim_type: str, text: str) -> str:
    payload = f"{path}\n{line_number}\n{claim_type}\n{text}".encode("utf-8")
    return f"claim-{hashlib.sha256(payload).hexdigest()[:20]}"


def _claim_inventory(tracked_files: list[dict[str, str]], root: Path) -> dict[str, Any]:
    paper_files = [item for item in tracked_files if item.get("kind") == "paper"]
    if not paper_files:
        payload = {"status": "NOT_APPLICABLE", "reason": "no manuscript files were supplied", "claims": []}
        payload["inventory_sha256"] = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return payload

    blocked: list[str] = []
    claims: list[dict[str, Any]] = []
    for tracked in paper_files:
        relative = str(tracked["path"])
        path = root / relative
        if path.suffix.lower() not in TEXT_MANUSCRIPT_SUFFIXES:
            blocked.append(relative)
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            blocked.append(relative)
            continue
        for line_number, raw_line in enumerate(text.splitlines(), start=1):
            line = " ".join(raw_line.strip().split())
            if not line:
                continue
            citation_keys: list[str] = []
            for group in LATEX_CITATION.findall(line):
                citation_keys.extend(key.strip() for key in group.split(",") if key.strip())
            citation_keys.extend(PANDOC_CITATION.findall(line))
            if citation_keys:
                claims.append({
                    "claim_id": _claim_id(relative, line_number, "bibliographic", line),
                    "claim_type": "bibliographic",
                    "source_file": relative,
                    "line": line_number,
                    "location": f"{relative}:{line_number}",
                    "text": line,
                    "citation_keys": list(dict.fromkeys(citation_keys)),
                })
            observed_values = [match.group(0).strip() for match in NUMERIC_CLAIM.finditer(line)]
            if observed_values:
                claims.append({
                    "claim_id": _claim_id(relative, line_number, "quantitative", line),
                    "claim_type": "quantitative",
                    "source_file": relative,
                    "line": line_number,
                    "location": f"{relative}:{line_number}",
                    "text": line,
                    "observed_values": observed_values,
                })
            if COMPARATIVE_CLAIM.search(line):
                claims.append({
                    "claim_id": _claim_id(relative, line_number, "comparative", line),
                    "claim_type": "comparative",
                    "source_file": relative,
                    "line": line_number,
                    "location": f"{relative}:{line_number}",
                    "text": line,
                })
            if SCOPE_CLAIM.search(line):
                claims.append({
                    "claim_id": _claim_id(relative, line_number, "scope", line),
                    "claim_type": "scope",
                    "source_file": relative,
                    "line": line_number,
                    "location": f"{relative}:{line_number}",
                    "text": line,
                })

    if blocked:
        payload = {
            "status": "BLOCKED",
            "reason": "claim inventory requires UTF-8 text manuscript sources",
            "blocked_files": sorted(blocked),
            "claims": claims,
        }
    elif claims:
        payload = {"status": "REQUIRED", "reason": "auditable manuscript claims were detected", "claims": claims}
    else:
        payload = {
            "status": "NOT_APPLICABLE",
            "reason": "no citation, quantitative, comparative, or scope claims were detected",
            "claims": [],
        }
    payload["inventory_sha256"] = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return payload


def plan_paper_audit(
    root: str | os.PathLike[str],
    request_text: str,
    *,
    paper_files: list[str] | None = None,
    evidence_files: list[str] | None = None,
    figure_ids: list[str] | None = None,
    effort: str = "medium",
) -> dict[str, Any]:
    effort = str(effort).lower().strip()
    if effort not in {"low", "medium", "high"}:
        raise AuditError("effort must be low, medium, or high; xhigh/ultra are forbidden")
    if not str(request_text).strip():
        raise AuditError("request_text is required")
    base = Path(root).expanduser().resolve()
    tracked = _tracked_files(base, paper_files, "paper file") + _tracked_files(base, evidence_files, "evidence file")
    claim_inventory = _claim_inventory(tracked, base)
    claim_types = {str(item["claim_type"]) for item in claim_inventory.get("claims", [])}
    roles, signals = _select_roles(str(request_text), claim_types)
    figures_requested = bool(FIGURE_TERMS.search(str(request_text)))
    normalized_figure_ids = [str(value).strip().lower() for value in (figure_ids or []) if str(value).strip()]
    if len(normalized_figure_ids) != len(set(normalized_figure_ids)):
        raise AuditError("figure_ids contains duplicates")
    figure_receipts: list[dict[str, Any]] = []
    for figure_id in normalized_figure_ids:
        try:
            figure_receipts.append(verify_academic_figure(base, figure_id))
        except FigureError as exc:
            raise AuditError(f"academic figure {figure_id} is not verified: {exc}") from exc
    paper_tracked = [item for item in tracked if item.get("kind") == "paper"]
    language_required = bool(paper_tracked)
    language_tracked = [item for item in paper_tracked if Path(item["path"]).suffix.lower() in TEXT_SUFFIXES]
    if language_required and language_tracked:
        try:
            plan_language_review(
                base,
                str(request_text),
                manuscript_files=[item["path"] for item in language_tracked],
                claim_ids=[str(item["claim_id"]) for item in claim_inventory.get("claims", [])],
            )
            language_analysis = analyze_language(base)
            if language_analysis["status"] == "READY_TO_FINALIZE":
                language_review = finalize_language_review(base)
            else:
                language_review = get_language_status(base)
        except LanguageError as exc:
            raise AuditError(f"language review planning failed: {exc}") from exc
    elif language_required:
        language_review = {
            "status": "BLOCKED",
            "reason": "language review requires a UTF-8 text manuscript source; binary-only paper input cannot pass",
        }
    else:
        language_review = {
            "status": "NOT_APPLICABLE",
            "reason": "no UTF-8 manuscript source was supplied; pass paper_files to activate deterministic language review",
        }
    state = {
        "schema_version": 3,
        "status": "AUDIT_REQUIRED",
        "reason": "selected reviewer roles have not submitted a verified audit",
        "planned_at": utc_now(),
        "request_text": str(request_text),
        "effort": effort,
        "selected_roles": roles,
        "role_templates": [{"role": role, **ROLE_TEMPLATES[role]} for role in roles],
        "requirements": {
            "lean_required": signals["formula"],
            "cross_verification_required": signals["formula"],
            "experiment_evidence_required": signals["experiment"],
            "literature_https_links_required": True,
            "online_verification_required": True,
            "claim_evidence_required": claim_inventory["status"] == "REQUIRED",
            "language_review_required": language_required,
            "figure_receipts_required": figures_requested,
            "openreview_calibration_required": signals["openreview"],
            "scientific_image_integrity_required": signals["image_integrity"],
            "max_roles": 3,
            "max_effort": "high",
        },
        "tracked_files": tracked,
        "claim_inventory": claim_inventory,
        "figure_ids": normalized_figure_ids,
        "figure_receipts": figure_receipts,
        "language_review": language_review,
        "lean_check": None,
        "verification_results": None,
        "openreview_calibration": None,
        "scientific_image_integrity": None,
        "receipt": None,
    }
    _atomic_json(_state_path(base), state)
    return state


LEAN_TOOLCHAIN = "leanprover/lean4:v4.33.0"
MATHLIB_TAG = "v4.33.0"
MATHLIB_COMMIT = "db584cd6d46c92f209a44c0f1c829460d327499d"
FORMULA_MARKER = re.compile(r"^\s*--\s*FORMULA_ID:\s*([A-Za-z][A-Za-z0-9_.-]*)\s*$", re.MULTILINE)
FORBIDDEN_LEAN = re.compile(r"\b(?:sorry|admit|axiom|unsafe)\b", re.IGNORECASE)
LEAN_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
CONFUSING_PARAMETERS = {"I", "O", "l"}
LEAN_KEYWORDS = {
    "axiom", "by", "class", "def", "do", "else", "end", "example", "false", "for", "fun", "if",
    "import", "in", "inductive", "instance", "let", "match", "namespace", "open", "structure",
    "theorem", "then", "true", "unsafe", "where", "with",
}


def compile_tex_document(
    root: str | os.PathLike[str], tex_file: str | os.PathLike[str], *, timeout: float = 180,
) -> dict[str, Any]:
    from dependency_manager import DependencyError, require
    from resource_guard import ResourceGuardError, run_managed

    base = Path(root).expanduser().resolve()
    source = (base / tex_file).resolve() if not Path(tex_file).is_absolute() else Path(tex_file).resolve()
    try:
        relative = source.relative_to(base).as_posix()
    except ValueError as exc:
        raise AuditError("TeX source must stay inside project_root") from exc
    if source.suffix.casefold() != ".tex" or not source.is_file():
        raise AuditError("TeX compile requires one existing .tex file")
    try:
        receipt = require("tex-basic")
    except DependencyError as exc:
        raise AuditError(f"{exc.code}: {exc}") from exc
    executable = Path(str(receipt.get("executables", {}).get("pdflatex", ""))).resolve()
    if not executable.is_file():
        raise AuditError("DEPENDENCY_MISSING: registered pdflatex executable is unavailable")
    output = base / ".research-guard" / "tex-build" / hashlib.sha256(relative.encode("utf-8")).hexdigest()[:16]
    output.mkdir(parents=True, exist_ok=True)
    command = [
        str(executable), "-no-shell-escape", "-interaction=nonstopmode", "-halt-on-error",
        f"-output-directory={output}", source.name,
    ]
    try:
        first = run_managed(command, cwd=source.parent, timeout=float(timeout))
        second = run_managed(command, cwd=source.parent, timeout=float(timeout))
    except ResourceGuardError as exc:
        raise AuditError(f"RESOURCE_GUARD_BLOCKED: {exc}") from exc
    pdf = output / f"{source.stem}.pdf"
    if first.returncode != 0 or second.returncode != 0 or not pdf.is_file():
        detail = (second.stderr or second.stdout or first.stderr or first.stdout or "PDF was not created")[-3000:]
        raise AuditError(f"TeX compilation failed: {detail.strip()}")
    result = {
        "status": "PASS",
        "checked_at": utc_now(),
        "tex_file": relative,
        "tex_sha256": _sha256(source),
        "pdf_path": pdf.relative_to(base).as_posix(),
        "pdf_sha256": _sha256(pdf),
        "compiler": str(executable),
        "compiler_source_mode": receipt.get("source_mode"),
        "passes": 2,
        "shell_escape": False,
    }
    _atomic_json(output / "compile-receipt.json", result)
    return result


def _lean_runtime(value: str | os.PathLike[str] | None) -> Path:
    from dependency_manager import DependencyError, require

    try:
        receipt = require("lean-mathlib")
    except DependencyError as exc:
        raise AuditError(f"{exc.code}: {exc}") from exc
    registered = Path(str(receipt.get("executables", {}).get("runtime_root", ""))).resolve()
    if value is not None and Path(value).expanduser().resolve() != registered:
        raise AuditError("DEPENDENCY_PATH_NOT_REGISTERED: runtime_root differs from the selected Lean receipt")
    return registered


def _validate_runtime(runtime: Path) -> None:
    toolchain_path = runtime / "lean-toolchain"
    manifest_path = runtime / "lake-manifest.json"
    if not toolchain_path.is_file() or toolchain_path.read_text(encoding="utf-8").strip() != LEAN_TOOLCHAIN:
        raise AuditError(f"pinned Lean runtime is missing or mismatched at {runtime}")
    if not manifest_path.is_file():
        raise AuditError(f"mathlib manifest is missing at {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise AuditError(f"mathlib manifest is invalid: {exc}") from exc
    mathlib = next((item for item in manifest.get("packages", []) if item.get("name") == "mathlib"), None)
    if not mathlib or mathlib.get("inputRev") != MATHLIB_TAG or mathlib.get("rev") != MATHLIB_COMMIT:
        raise AuditError("mathlib runtime is not pinned to the audited tag and commit")


def _formula_contract(text: str, manifest: Any) -> tuple[list[str], list[str]]:
    if not isinstance(manifest, dict):
        raise AuditError("formula_manifest must be an object")
    formulas = manifest.get("formulas")
    parameters = manifest.get("parameters")
    if not isinstance(formulas, list) or not formulas:
        raise AuditError("formula_manifest.formulas must be a non-empty array")
    if not isinstance(parameters, list):
        raise AuditError("formula_manifest.parameters must be an array")
    formula_map: dict[str, dict[str, Any]] = {}
    formula_parameter_names: set[str] = set()
    for index, formula in enumerate(formulas):
        if not isinstance(formula, dict):
            raise AuditError(f"formula {index} must be an object")
        formula_id = str(formula.get("id") or "").strip()
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]*", formula_id):
            raise AuditError(f"formula {index} has an illegal id")
        if formula_id in formula_map:
            raise AuditError(f"duplicate formula id: {formula_id}")
        if not str(formula.get("source") or "").strip():
            raise AuditError(f"formula {formula_id} has no manuscript source location")
        names = formula.get("parameters")
        if not isinstance(names, list):
            raise AuditError(f"formula {formula_id} parameters must be an array")
        formula["parameters"] = [str(name) for name in names]
        formula_parameter_names.update(formula["parameters"])
        formula_map[formula_id] = formula
    markers = FORMULA_MARKER.findall(text)
    if len(markers) != len(set(markers)):
        raise AuditError("Lean file contains duplicate FORMULA_ID markers")
    if set(markers) != set(formula_map):
        missing = sorted(set(formula_map) - set(markers))
        extra = sorted(set(markers) - set(formula_map))
        raise AuditError(f"formula coverage mismatch; missing={missing}, extra={extra}")
    parameter_map: dict[str, dict[str, Any]] = {}
    for index, parameter in enumerate(parameters):
        if not isinstance(parameter, dict):
            raise AuditError(f"parameter {index} must be an object")
        name = str(parameter.get("name") or "").strip()
        if not LEAN_IDENTIFIER.fullmatch(name) or name in LEAN_KEYWORDS or name in CONFUSING_PARAMETERS:
            raise AuditError(f"illegal or confusing parameter name: {name or '<empty>'}")
        if name in parameter_map:
            raise AuditError(f"duplicate parameter: {name}")
        purpose = str(parameter.get("purpose") or "").strip()
        if len(purpose) < 6:
            raise AuditError(f"parameter {name} needs a concrete purpose")
        used_by = parameter.get("used_by")
        if not isinstance(used_by, list) or not used_by:
            raise AuditError(f"parameter {name} needs non-empty used_by formula ids")
        used_ids = {str(value) for value in used_by}
        if not used_ids <= set(formula_map):
            raise AuditError(f"parameter {name} references unknown formula ids")
        actual_ids = {formula_id for formula_id, formula in formula_map.items() if name in formula["parameters"]}
        if used_ids != actual_ids:
            raise AuditError(f"parameter {name} used_by does not match formula registrations")
        parameter_map[name] = parameter
    if set(parameter_map) != formula_parameter_names:
        missing = sorted(formula_parameter_names - set(parameter_map))
        unused = sorted(set(parameter_map) - formula_parameter_names)
        raise AuditError(f"parameter registry mismatch; missing={missing}, unused={unused}")
    marker_matches = list(FORMULA_MARKER.finditer(text))
    for index, match in enumerate(marker_matches):
        formula_id = match.group(1)
        end = marker_matches[index + 1].start() if index + 1 < len(marker_matches) else len(text)
        segment = text[match.end():end]
        if not re.search(r"\b(?:theorem|lemma|def|example)\b", segment):
            raise AuditError(f"formula {formula_id} has no formal declaration after its marker")
        code_segment = re.sub(r"/\*.*?\*/", " ", segment, flags=re.DOTALL)
        code_segment = re.sub(r"/-.*?-/", " ", code_segment, flags=re.DOTALL)
        code_segment = re.sub(r"--[^\n]*", " ", code_segment)
        code_segment = re.sub(r'"(?:\\.|[^"\\])*"', '""', code_segment)
        for name in formula_map[formula_id]["parameters"]:
            if len(re.findall(rf"\b{re.escape(name)}\b", code_segment)) < 2:
                raise AuditError(f"parameter {name} is declared but not actually used in formula {formula_id}")
    return markers, sorted(parameter_map)


def run_lean_formula_audit(
    root: str | os.PathLike[str],
    lean_file: str | os.PathLike[str],
    formula_manifest: dict[str, Any],
    *,
    runtime_root: str | os.PathLike[str] | None = None,
    timeout: float = 360,
) -> dict[str, Any]:
    if isinstance(lean_file, (list, tuple, set)):
        raise AuditError("the full manuscript formula audit requires exactly one Lean file")
    base = Path(root).expanduser().resolve()
    path = (base / lean_file).resolve() if not Path(lean_file).is_absolute() else Path(lean_file).resolve()
    try:
        relative = path.relative_to(base).as_posix()
    except ValueError as exc:
        raise AuditError("Lean audit file must stay inside project_root") from exc
    if path.suffix.lower() != ".lean" or not path.is_file():
        raise AuditError("Lean audit requires one existing .lean file")
    text = path.read_text(encoding="utf-8")
    if "import Mathlib" not in text:
        raise AuditError("Lean audit file must import the pinned Mathlib")
    if "set_option autoImplicit false" not in text:
        raise AuditError("Lean audit file must disable autoImplicit")
    forbidden = FORBIDDEN_LEAN.search(text)
    if forbidden:
        raise AuditError(f"forbidden Lean placeholder or declaration: {forbidden.group(0)}")
    formula_ids, parameters = _formula_contract(text, formula_manifest)
    runtime = _lean_runtime(runtime_root)
    _validate_runtime(runtime)
    from dependency_manager import DependencyError, require

    try:
        lean_receipt = require("lean-mathlib")
    except DependencyError as exc:
        raise AuditError(f"{exc.code}: {exc}") from exc
    lake = Path(str(lean_receipt.get("executables", {}).get("lake", "")))
    if not lake.is_file():
        raise AuditError("DEPENDENCY_MISSING: registered lake executable is unavailable")
    from resource_guard import ResourceGuardError, run_managed_lean
    try:
        completed = run_managed_lean(
            [str(lake), "env", "lean", str(path)], cwd=runtime, timeout=float(timeout),
        )
    except ResourceGuardError as exc:
        raise AuditError(f"RESOURCE_GUARD_BLOCKED: {exc}") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "unknown compiler error").strip()[-3000:]
        raise AuditError(f"Lean compilation failed: {detail}")
    result = {
        "status": "PASS",
        "checked_at": utc_now(),
        "lean_file": relative,
        "lean_sha256": _sha256(path),
        "formula_manifest_sha256": hashlib.sha256(
            json.dumps(formula_manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "formula_ids": formula_ids,
        "parameters": parameters,
        "resource_usage": getattr(completed, "resource_usage", {}),
        "toolchain": LEAN_TOOLCHAIN,
        "mathlib_tag": MATHLIB_TAG,
        "mathlib_commit": MATHLIB_COMMIT,
    }
    state = _load_state(base)
    state["lean_check"] = result
    previous = state.get("verification_results") if isinstance(state.get("verification_results"), dict) else {}
    state["verification_results"] = {**previous, "lean": dict(result)}
    tracked = {item["path"]: item for item in state["tracked_files"]}
    tracked[relative] = {"path": relative, "sha256": result["lean_sha256"], "kind": "formula"}
    state["tracked_files"] = sorted(tracked.values(), key=lambda item: item["path"])
    _atomic_json(_state_path(base), state)
    return result


VERIFICATION_CHANNELS = ("lean", "dimensional", "symbolic", "constraints", "numerical_protocol")


def run_formula_cross_verification(
    root: str | os.PathLike[str],
    verification_manifest: dict[str, Any],
    *,
    timeout: float = 180,
) -> dict[str, Any]:
    """Run Pint, SymPy, Z3 and numerical-protocol checks in one bounded worker.

    Lean deliberately remains a separate, manuscript-wide compilation step. Its
    current hash-bound result is joined here so callers always receive the five
    channels as separate records.
    """
    from dependency_manager import DependencyError, require
    from resource_guard import ResourceGuardError, run_managed

    base = Path(root).expanduser().resolve()
    state = _load_state(base)
    if not isinstance(verification_manifest, dict):
        raise AuditError("verification_manifest must be an object")
    applicability = verification_manifest.get("applicability")
    if not isinstance(applicability, dict) or set(applicability) != set(VERIFICATION_CHANNELS):
        raise AuditError(f"applicability must report exactly: {', '.join(VERIFICATION_CHANNELS)}")
    lean_applicability = applicability.get("lean")
    if not isinstance(lean_applicability, dict) or str(lean_applicability.get("status") or "").lower() != "required":
        raise AuditError("Lean logical-proposition verification cannot be marked not_applicable in a formula audit")
    lean_result = state.get("lean_check")
    if not isinstance(lean_result, dict) or lean_result.get("status") != "PASS":
        raise AuditError("Lean formula audit must PASS before the other four channels run")
    try:
        core = require("core-runtime")
    except DependencyError as exc:
        raise AuditError(f"{exc.code}: {exc}") from exc
    python = Path(str((core.get("executables") or {}).get("python") or "")).resolve()
    if not python.is_file():
        raise AuditError("DEPENDENCY_MISSING: registered core Python is unavailable")
    worker = Path(__file__).with_name("math_verification_worker.py")
    if not worker.is_file():
        raise AuditError("math verification worker is missing")
    output_root = base / ".research-guard" / "formula-verification"
    output_root.mkdir(parents=True, exist_ok=True)
    manifest_sha256 = hashlib.sha256(
        json.dumps(verification_manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    with tempfile.TemporaryDirectory(prefix="research-guard-math-", dir=output_root) as temporary:
        input_path = Path(temporary) / "input.json"
        output_path = Path(temporary) / "output.json"
        _atomic_json(input_path, {"project_root": str(base), "manifest": verification_manifest})
        # Installed releases use the bundled interpreter and are isolated from
        # user site-packages. Development receipts may explicitly register a
        # host interpreter, whose user-site packages are required by tests.
        isolated = (python.parent / "Lib" / "site-packages" / "pint").is_dir()
        interpreter_flags = ["-I"] if isolated else []
        try:
            completed = run_managed(
                [str(python), *interpreter_flags, "-X", "utf8", str(worker), str(input_path), str(output_path)],
                cwd=base, timeout=float(timeout),
            )
        except ResourceGuardError as exc:
            raise AuditError(f"RESOURCE_GUARD_BLOCKED: {exc}") from exc
        if completed.returncode != 0 or not output_path.is_file():
            detail = (completed.stderr or completed.stdout or "verification worker produced no result")[-3000:]
            if output_path.is_file():
                detail = output_path.read_text(encoding="utf-8")[-3000:]
            raise AuditError(f"formula cross-verification worker failed: {detail.strip()}")
        try:
            worker_result = json.loads(output_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AuditError(f"formula cross-verification result is invalid: {exc}") from exc
    if worker_result.get("manifest_sha256") != manifest_sha256:
        raise AuditError("formula cross-verification result is not bound to the submitted manifest")
    worker_channels = worker_result.get("results")
    if not isinstance(worker_channels, dict) or set(worker_channels) != set(VERIFICATION_CHANNELS[1:]):
        raise AuditError("formula cross-verification omitted a required result channel")
    results = {"lean": lean_result, **worker_channels}
    if set(results) != set(VERIFICATION_CHANNELS):
        raise AuditError("formula cross-verification did not produce all five separate records")
    receipt = {
        "schema_version": 1,
        "status": "PASS" if all(
            result.get("status") in {"PASS", "NOT_APPLICABLE"} for result in results.values()
        ) else "BLOCKED",
        "checked_at": utc_now(),
        "manifest_sha256": manifest_sha256,
        "results": results,
        "resource_usage": getattr(completed, "resource_usage", {}),
    }
    receipt["receipt_sha256"] = hashlib.sha256(
        json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    receipt_path = output_root / "latest.json"
    _atomic_json(receipt_path, receipt)
    tracked = {item["path"]: item for item in state["tracked_files"]}
    numerical = results.get("numerical_protocol") or {}
    model_path = numerical.get("model_script")
    if model_path:
        tracked[str(model_path)] = {
            "path": str(model_path), "sha256": str(numerical.get("model_sha256") or ""), "kind": "numerical_model",
        }
    state["tracked_files"] = sorted(tracked.values(), key=lambda item: item["path"])
    state["verification_manifest_sha256"] = manifest_sha256
    state["verification_results"] = results
    state["verification_receipt"] = receipt
    state["receipt"] = None
    state["status"] = "AUDIT_REQUIRED"
    state["reason"] = "cross-verification completed; selected roles must still submit their audit"
    _atomic_json(_state_path(base), state)
    return receipt


def _load_state(root: str | os.PathLike[str]) -> dict[str, Any]:
    path = _state_path(root)
    if not path.is_file():
        raise AuditError("paper audit has not been planned")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise AuditError(f"paper audit state is invalid: {exc}") from exc
    if not isinstance(value, dict):
        raise AuditError("paper audit state must be an object")
    return value


def attach_paper_auxiliary_audit(
    root: str | os.PathLike[str], channel: str, result: dict[str, Any],
) -> dict[str, Any]:
    """Attach canonical OpenReview/image receipts to an active paper audit."""
    base = Path(root).expanduser().resolve()
    state_path = _state_path(base)
    if not state_path.is_file():
        return result
    state = _load_state(base)
    if channel == "openreview_calibration":
        if result.get("status") not in {"PASS", "FIXTURE_ONLY"} or not result.get("receipt_sha256"):
            raise AuditError("OpenReview calibration did not produce a valid receipt")
    elif channel == "scientific_image_integrity":
        if result.get("status") not in {"REVIEW_REQUIRED", "PASS"} or not result.get("audit_sha256"):
            raise AuditError("scientific image integrity audit has hard failures")
    else:
        raise AuditError(f"unknown auxiliary paper audit channel: {channel}")
    state[channel] = result
    state["receipt"] = None
    state["status"] = "AUDIT_REQUIRED"
    state["reason"] = f"{channel} evidence attached; selected roles must still submit their audit"
    _atomic_json(state_path, state)
    return result


def _require_https(url: Any, label: str) -> str:
    value = str(url or "").strip()
    if not value.startswith("https://"):
        raise AuditError(f"{label} must contain a clickable https:// URL")
    return value


def _validate_online_checks(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list) or not values:
        raise AuditError("at least one current online verification check is required")
    result: list[dict[str, Any]] = []
    required = ("claim", "url", "accessed_at", "source_type", "status")
    for index, raw in enumerate(values):
        if not isinstance(raw, dict):
            raise AuditError(f"online check {index} must be an object")
        missing = [name for name in required if not str(raw.get(name) or "").strip()]
        if missing:
            raise AuditError(f"online check {index} is missing: {', '.join(missing)}")
        item = dict(raw)
        item["url"] = _require_https(item["url"], f"online check {index}")
        timestamp = str(item["accessed_at"]).strip()
        try:
            parsed = dt.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError as exc:
            raise AuditError(f"online check {index} accessed_at must be an ISO-8601 date or timestamp") from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        if parsed > dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1):
            raise AuditError(f"online check {index} accessed_at is in the future")
        if str(item["status"]).strip().lower() != "verified":
            raise AuditError(f"online check {index} status must be verified")
        item["status"] = "verified"
        result.append(item)
    return result


def _validate_literature_items(values: Any, required: bool) -> list[dict[str, Any]]:
    if values is None:
        if required:
            raise AuditError("domain literature review requires linked literature items")
        return []
    if not isinstance(values, list):
        raise AuditError("literature_items must be an array")
    if required and not values:
        raise AuditError("domain literature review requires linked literature items")
    result: list[dict[str, Any]] = []
    for index, raw in enumerate(values):
        if not isinstance(raw, dict) or not str(raw.get("title") or "").strip():
            raise AuditError(f"literature item {index} requires a title")
        item = dict(raw)
        links = item.get("citation_links")
        if links is None and item.get("citation_url"):
            links = [{"kind": "citation", "url": item["citation_url"]}]
        if not isinstance(links, list) or not links:
            raise AuditError(f"literature item {index} has no clickable citation hyperlink")
        normalized_links = []
        for link_index, link in enumerate(links):
            if not isinstance(link, dict):
                raise AuditError(f"literature item {index} link {link_index} must be an object")
            normalized_links.append({**link, "url": _require_https(link.get("url"), f"literature item {index} link {link_index}")})
        item["citation_links"] = normalized_links
        item["citation_url"] = _require_https(item.get("citation_url") or normalized_links[0]["url"], f"literature item {index}")
        result.append(item)
    return result


def _validate_claim_evidence(state: dict[str, Any], values: Any) -> list[dict[str, Any]]:
    inventory = state.get("claim_inventory") or {"status": "NOT_APPLICABLE", "claims": []}
    status = inventory.get("status")
    if status == "BLOCKED":
        blocked = ", ".join(inventory.get("blocked_files") or [])
        raise AuditError(f"claim evidence audit requires a UTF-8 text manuscript source: {blocked}")
    if status == "NOT_APPLICABLE":
        if values not in (None, []):
            raise AuditError("claim evidence was supplied but the frozen inventory has no auditable claims")
        return []
    if not isinstance(values, list) or not values:
        raise AuditError("claim evidence is required for every inventoried manuscript claim")

    expected = {str(claim["claim_id"]): claim for claim in inventory.get("claims", [])}
    supplied: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(values):
        if not isinstance(raw, dict):
            raise AuditError(f"claim evidence {index} must be an object")
        claim_id = str(raw.get("claim_id") or "").strip()
        if claim_id in supplied:
            raise AuditError(f"duplicate claim evidence: {claim_id or '<empty>'}")
        supplied[claim_id] = raw
    if set(supplied) != set(expected):
        missing = sorted(set(expected) - set(supplied))
        extra = sorted(set(supplied) - set(expected))
        raise AuditError(f"claim coverage mismatch; missing={missing}, extra={extra}")

    tracked_evidence = {item["path"] for item in state.get("tracked_files", []) if item.get("kind") == "evidence"}
    normalized: list[dict[str, Any]] = []
    for claim_id in expected:
        raw = supplied[claim_id]
        claim = expected[claim_id]
        claim_type = str(raw.get("claim_type") or "").strip()
        if claim_type != claim["claim_type"]:
            raise AuditError(f"claim {claim_id} type does not match the frozen inventory")
        if raw.get("support_status") != "supports":
            raise AuditError(f"claim {claim_id} support must be resolved to supports before PASS")
        if len(str(raw.get("support_basis") or "").strip()) < 20:
            raise AuditError(f"claim {claim_id} needs a concrete support basis")
        if not str(raw.get("evidence_locator") or "").strip():
            raise AuditError(f"claim {claim_id} needs an evidence locator")

        source_kind = str(raw.get("source_kind") or "").strip()
        if source_kind not in {"literature", "official_standard", "raw_result", "code_config"}:
            raise AuditError(f"claim {claim_id} has an invalid source_kind")
        item = dict(raw)
        if source_kind in {"literature", "official_standard"}:
            if not str(item.get("source_title") or "").strip():
                raise AuditError(f"claim {claim_id} literature evidence needs a source title")
            item["source_url"] = _require_https(item.get("source_url"), f"claim {claim_id} source")
            if item.get("metadata_status") != "verified":
                raise AuditError(f"claim {claim_id} literature metadata must be verified")
        else:
            evidence_files = item.get("evidence_files")
            if not isinstance(evidence_files, list) or not evidence_files:
                raise AuditError(f"claim {claim_id} raw/code evidence requires evidence_files")
            normalized_files = [str(path).replace("\\", "/") for path in evidence_files]
            unknown = sorted(set(normalized_files) - tracked_evidence)
            if unknown:
                raise AuditError(f"claim {claim_id} evidence was not hash-bound during planning: {', '.join(unknown)}")
            item["evidence_files"] = normalized_files

        if claim_type == "bibliographic":
            if source_kind != "literature":
                raise AuditError(f"claim {claim_id} bibliographic evidence must use a literature source")
            actual_keys = item.get("citation_keys")
            if not isinstance(actual_keys, list) or actual_keys != claim.get("citation_keys"):
                raise AuditError(f"claim {claim_id} citation keys do not match the frozen inventory")
        if claim_type == "quantitative":
            numeric = item.get("numeric_check")
            if not isinstance(numeric, dict):
                raise AuditError(f"claim {claim_id} requires a numeric check")
            missing = [name for name in ("paper_value", "evidence_value", "method", "status") if numeric.get(name) in (None, "")]
            if missing:
                raise AuditError(f"claim {claim_id} numeric check is missing: {', '.join(missing)}")
            if numeric.get("status") not in {"exact_match", "rounding_ok"}:
                raise AuditError(f"claim {claim_id} numeric check must resolve before PASS")
            number_pattern = re.compile(r"^\s*([-+]?(?:\d+(?:,\d{3})*(?:\.\d+)?|\.\d+))\s*(%|％)?\s*$")
            paper_match = number_pattern.fullmatch(str(numeric.get("paper_value")))
            evidence_match = number_pattern.fullmatch(str(numeric.get("evidence_value")))
            if not paper_match or not evidence_match:
                raise AuditError(f"claim {claim_id} numeric values must each contain one explicit number")
            paper_number = float(paper_match.group(1).replace(",", ""))
            evidence_number = float(evidence_match.group(1).replace(",", ""))
            paper_percent = bool(paper_match.group(2))
            evidence_percent = bool(evidence_match.group(2))
            observed = {" ".join(str(value).split()) for value in claim.get("observed_values", [])}
            if " ".join(str(numeric.get("paper_value")).split()) not in observed:
                raise AuditError(f"claim {claim_id} numeric paper_value is not present in the frozen manuscript claim")
            if paper_percent != evidence_percent:
                raise AuditError(f"claim {claim_id} numeric units do not match")
            if numeric.get("status") == "exact_match" and paper_number != evidence_number:
                raise AuditError(f"claim {claim_id} numeric exact_match values differ")
            if numeric.get("status") == "rounding_ok":
                try:
                    tolerance = float(numeric.get("tolerance"))
                except (TypeError, ValueError) as exc:
                    raise AuditError(f"claim {claim_id} rounding_ok requires a numeric tolerance") from exc
                if tolerance < 0 or abs(paper_number - evidence_number) > tolerance:
                    raise AuditError(f"claim {claim_id} numeric difference exceeds tolerance")
        normalized.append(item)
    return normalized


def submit_paper_audit(
    root: str | os.PathLike[str],
    *,
    role_reports: list[dict[str, Any]],
    online_checks: list[dict[str, Any]],
    literature_items: list[dict[str, Any]] | None = None,
    claim_evidence_items: list[dict[str, Any]] | None = None,
    experiment_check: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state = _load_state(root)
    changed = _tracked_changes(Path(root).expanduser().resolve(), state)
    if changed:
        raise AuditError(f"tracked audit inputs changed; replan before submission: {', '.join(changed)}")
    if not isinstance(role_reports, list):
        raise AuditError("role_reports must be an array")
    reports: dict[str, dict[str, Any]] = {}
    for report in role_reports:
        if not isinstance(report, dict):
            raise AuditError("every role report must be an object")
        role = str(report.get("role") or "")
        if role in reports:
            raise AuditError(f"duplicate role report: {role}")
        if role not in state["selected_roles"]:
            raise AuditError(f"unselected role report: {role}")
        if not report.get("findings"):
            raise AuditError(f"role {role} has no findings")
        if not report.get("numeric_checks"):
            raise AuditError(f"role {role} has no numeric checks")
        reports[role] = dict(report)
    if set(reports) != set(state["selected_roles"]):
        missing = sorted(set(state["selected_roles"]) - set(reports))
        raise AuditError(f"missing selected role reports: {', '.join(missing)}")
    checks = _validate_online_checks(online_checks)
    claim_evidence = _validate_claim_evidence(state, claim_evidence_items)
    literature = _validate_literature_items(literature_items, "domain_literature" in state["selected_roles"])
    if state["requirements"]["lean_required"] and (state.get("lean_check") or {}).get("status") != "PASS":
        raise AuditError("Lean formula audit is required and has not passed")
    if state["requirements"].get("cross_verification_required"):
        verification = state.get("verification_results")
        if not isinstance(verification, dict) or set(verification) != set(VERIFICATION_CHANNELS):
            raise AuditError("all five Lean/Pint/SymPy/Z3/numerical verification records are required")
        blocked = [
            channel for channel in VERIFICATION_CHANNELS
            if (verification.get(channel) or {}).get("status") not in {"PASS", "NOT_APPLICABLE"}
        ]
        if blocked:
            raise AuditError(f"required formula verification channels did not pass: {', '.join(blocked)}")
    if state["requirements"].get("openreview_calibration_required"):
        calibration = state.get("openreview_calibration")
        if not isinstance(calibration, dict) or calibration.get("status") != "PASS":
            raise AuditError("live official OpenReview calibration is required; a fixture cannot close the audit")
        try:
            current_calibration = get_openreview_calibration(root, str(calibration.get("calibration_id") or ""))
        except OpenReviewCalibrationError as exc:
            raise AuditError(f"OpenReview calibration is no longer valid: {exc}") from exc
        if current_calibration.get("receipt_sha256") != calibration.get("receipt_sha256"):
            raise AuditError("OpenReview calibration receipt changed after it was attached")
    if state["requirements"].get("scientific_image_integrity_required"):
        image_audit = state.get("scientific_image_integrity")
        if not isinstance(image_audit, dict) or image_audit.get("status") != "PASS":
            raise AuditError("scientific image integrity evidence requires a current expert-review PASS")
        try:
            current_image_audit = get_scientific_image_integrity_status(root, str(image_audit.get("audit_id") or ""))
        except FigureError as exc:
            raise AuditError(f"scientific image integrity evidence is no longer valid: {exc}") from exc
        if current_image_audit.get("status") != "PASS" or current_image_audit.get("audit_sha256") != image_audit.get("audit_sha256"):
            raise AuditError("scientific image integrity evidence changed after expert review")
    normalized_experiment = _validate_experiment_check(state, experiment_check)
    if state["requirements"].get("figure_receipts_required") and not state.get("figure_ids"):
        raise AuditError("figure audit requires figure_ids bound to verified academic_figure receipts")
    current_figure_receipts: list[dict[str, Any]] = []
    for expected in state.get("figure_receipts") or []:
        figure_id = str(expected.get("figure_id") or "")
        try:
            current = verify_academic_figure(root, figure_id)
        except FigureError as exc:
            raise AuditError(f"academic figure {figure_id} is no longer verified: {exc}") from exc
        if current.get("receipt_sha256") != expected.get("receipt_sha256"):
            raise AuditError(f"academic figure receipt changed: {figure_id}")
        current_figure_receipts.append(current)
    language_receipt_sha256 = None
    if state["requirements"].get("language_review_required"):
        paper_files = [item for item in state.get("tracked_files", []) if item.get("kind") == "paper"]
        claim_ids = [str(item["claim_id"]) for item in (state.get("claim_inventory") or {}).get("claims", [])]
        try:
            language_verification = verify_language_receipt(
                root,
                expected_files=paper_files,
                expected_claim_ids=claim_ids,
            )
        except LanguageError as exc:
            raise AuditError(f"language review must pass before paper submission: {exc}") from exc
        language_receipt_sha256 = language_verification["receipt_sha256"]
    receipt_payload = {
        "selected_roles": state["selected_roles"],
        "role_reports": [reports[role] for role in state["selected_roles"]],
        "online_checks": checks,
        "literature_items": literature,
        "claim_evidence_items": claim_evidence,
        "claim_inventory_sha256": (state.get("claim_inventory") or {}).get("inventory_sha256"),
        "experiment_check": normalized_experiment,
        "figure_receipts": current_figure_receipts,
        "tracked_files": state["tracked_files"],
        "lean_check": state.get("lean_check"),
        "verification_results": state.get("verification_results"),
        "verification_manifest_sha256": state.get("verification_manifest_sha256"),
        "openreview_calibration": state.get("openreview_calibration"),
        "scientific_image_integrity": state.get("scientific_image_integrity"),
        "language_receipt_sha256": language_receipt_sha256,
        "issued_at": utc_now(),
    }
    receipt_payload["receipt_sha256"] = hashlib.sha256(
        json.dumps(receipt_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    state.update({
        "status": "PASS",
        "reason": "all selected role and deterministic evidence gates passed",
        "receipt": receipt_payload,
    })
    _atomic_json(_state_path(root), state)
    return {"status": "PASS", **receipt_payload}


def _tracked_changes(root: Path, state: dict[str, Any]) -> list[str]:
    changes: list[str] = []
    for item in state.get("tracked_files", []):
        path = (root / str(item.get("path") or "")).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            changes.append(str(item.get("path") or "<outside-project>"))
            continue
        if not path.is_file() or _sha256(path) != item.get("sha256"):
            changes.append(str(item.get("path") or "<missing-path>"))
    return sorted(set(changes))


def _validate_experiment_check(state: dict[str, Any], value: Any) -> dict[str, Any] | None:
    if not state["requirements"]["experiment_evidence_required"]:
        return dict(value) if isinstance(value, dict) else None
    if not isinstance(value, dict):
        raise AuditError("code/experiment integrity evidence is required")
    required = (
        "evidence_files", "data_provenance", "configuration", "seeds", "numeric_recomputation",
        "dead_code", "evaluation_scope",
    )
    missing = [name for name in required if value.get(name) in (None, "", [], {})]
    if missing:
        raise AuditError(f"experiment check is missing: {', '.join(missing)}")
    evidence_files = value.get("evidence_files")
    if not isinstance(evidence_files, list) or not evidence_files:
        raise AuditError("experiment check requires evidence_files")
    tracked_evidence = {item["path"] for item in state.get("tracked_files", []) if item.get("kind") == "evidence"}
    unknown = sorted({str(path).replace("\\", "/") for path in evidence_files} - tracked_evidence)
    if unknown:
        raise AuditError(f"experiment evidence was not hash-bound during planning: {', '.join(unknown)}")
    return dict(value)


def get_paper_audit_status(root: str | os.PathLike[str]) -> dict[str, Any]:
    path = _state_path(root)
    if not path.is_file():
        return {"status": "NOT_PLANNED", "reason": "paper audit has not been planned"}
    state = _load_state(root)
    figure_changes: list[str] = []
    for expected in state.get("figure_receipts") or []:
        figure_id = str(expected.get("figure_id") or "")
        try:
            current = verify_academic_figure(root, figure_id)
        except FigureError:
            figure_changes.append(figure_id)
        else:
            if current.get("receipt_sha256") != expected.get("receipt_sha256"):
                figure_changes.append(figure_id)
    changes = _tracked_changes(Path(root).expanduser().resolve(), state)
    auxiliary_changes: list[str] = []
    calibration = state.get("openreview_calibration")
    if isinstance(calibration, dict):
        try:
            current = get_openreview_calibration(root, str(calibration.get("calibration_id") or ""))
        except OpenReviewCalibrationError:
            auxiliary_changes.append("OpenReview calibration receipt")
        else:
            if current.get("receipt_sha256") != calibration.get("receipt_sha256"):
                auxiliary_changes.append("OpenReview calibration receipt")
    image_audit = state.get("scientific_image_integrity")
    if isinstance(image_audit, dict):
        try:
            current_image = get_scientific_image_integrity_status(root, str(image_audit.get("audit_id") or ""))
        except FigureError:
            auxiliary_changes.append("scientific image integrity evidence")
        else:
            if current_image.get("status") != image_audit.get("status") or current_image.get("audit_sha256") != image_audit.get("audit_sha256"):
                auxiliary_changes.append("scientific image integrity evidence")
    if changes or figure_changes or auxiliary_changes:
        reasons: list[str] = []
        if changes:
            reasons.append(f"tracked audit inputs changed: {', '.join(changes)}")
        if figure_changes:
            reasons.append(f"academic figure receipts changed: {', '.join(figure_changes)}")
        if auxiliary_changes:
            reasons.append(f"auxiliary audit evidence changed: {', '.join(auxiliary_changes)}")
        state.update({
            "status": "AUDIT_REQUIRED",
            "reason": "; ".join(reasons),
            "receipt": None,
        })
        _atomic_json(path, state)
    elif state.get("status") == "PASS":
        receipt = state.get("receipt")
        if not isinstance(receipt, dict):
            state.update({"status": "AUDIT_REQUIRED", "reason": "paper audit receipt is missing or invalid", "receipt": None})
            _atomic_json(path, state)
        else:
            saved_hash = receipt.get("receipt_sha256")
            unsigned = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
            current_hash = hashlib.sha256(
                json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            if saved_hash != current_hash:
                state.update({"status": "AUDIT_REQUIRED", "reason": "paper audit receipt integrity check failed", "receipt": None})
                _atomic_json(path, state)
            elif state.get("requirements", {}).get("language_review_required"):
                paper_files = [item for item in state.get("tracked_files", []) if item.get("kind") == "paper"]
                claim_ids = [str(item["claim_id"]) for item in (state.get("claim_inventory") or {}).get("claims", [])]
                try:
                    language = verify_language_receipt(
                        root,
                        expected_files=paper_files,
                        expected_claim_ids=claim_ids,
                    )
                except LanguageError as exc:
                    state.update({
                        "status": "AUDIT_REQUIRED",
                        "reason": f"language receipt is no longer valid: {exc}",
                        "receipt": None,
                    })
                    _atomic_json(path, state)
                else:
                    if language["receipt_sha256"] != receipt.get("language_receipt_sha256"):
                        state.update({
                            "status": "AUDIT_REQUIRED",
                            "reason": "paper receipt does not match the current language receipt",
                            "receipt": None,
                        })
                        _atomic_json(path, state)
    return state
