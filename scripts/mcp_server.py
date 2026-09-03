from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from research_guard_core import (  # noqa: E402
    GuardError,
    classify_domain,
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
    verify_index_membership,
    verify_publication,
)
from paper_audit_core import (  # noqa: E402
    compile_tex_document,
    attach_paper_auxiliary_audit,
    get_paper_audit_status,
    plan_paper_audit,
    run_formula_cross_verification,
    run_lean_formula_audit,
    submit_paper_audit,
)
from language_guard_core import (  # noqa: E402
    analyze_language,
    finalize_language_review,
    get_language_status,
    plan_language_review,
    register_rhetorical_card,
    resolve_language_issues,
    retrieve_rhetorical_cards,
    verify_language_receipt,
)
from venue_evidence_core import (  # noqa: E402
    get_venue_status,
    list_venue_profiles,
    register_venue_profile,
    resolve_venue_profile,
    verify_venue_receipt,
)
from research_design_core import (  # noqa: E402
    commit_candidate,
    decide_strategy_branch,
    get_research_design_status,
    plan_ideation,
    plan_strategy,
    register_candidates,
    register_experiment,
    register_hypothesis,
    register_strategy,
)
from experiment_metrics_core import (  # noqa: E402
    analyze_metrics,
    metric_status,
    optimize_metrics,
    register_metric_plan,
)
from llm_delegation_core import (  # noqa: E402
    llm_assistance_status,
    plan_llm_assistance,
    submit_llm_assistance,
    verify_llm_assistance,
)
from instruction_adherence_core import (  # noqa: E402
    instruction_adherence_status,
    record_instruction_requirement,
    register_instruction_contract,
    verify_instruction_contract,
    waive_instruction_requirement,
)
from resource_task_planner_core import (  # noqa: E402
    execute_resource_task,
    inventory_resources,
    plan_resource_tasks,
    record_resource_task,
    resource_task_plan_status,
    verify_resource_task_plan,
)
from direction_exploration_core import (  # noqa: E402
    activate_direction_candidate,
    bind_direction_collision,
    direction_exploration_status,
    finalize_direction_choices,
    plan_direction_exploration,
    record_direction_iteration,
    register_direction_candidates,
    revise_direction_candidate,
    verify_direction_exploration,
)
from academic_figure_core import (  # noqa: E402
    audit_academic_figure,
    audit_scientific_image_integrity,
    get_academic_figure_status,
    get_scientific_image_integrity_status,
    plan_academic_figure,
    record_scientific_image_review,
    record_visual_review,
    render_academic_figure,
    verify_academic_figure,
)
from openreview_calibration_core import calibrate_openreview, get_openreview_calibration  # noqa: E402
from ai_reviewer_robustness_core import (  # noqa: E402
    audit_ai_reviewer_robustness,
    get_ai_reviewer_robustness_status,
    get_ai_reviewer_optimization_status,
    plan_ai_reviewer_optimization,
    register_ai_reviewer_candidates,
    select_ai_reviewer_candidate,
)
from citation_guard_core import verify_and_format_citation  # noqa: E402
from paper_spine_core import (  # noqa: E402
    bind_paper_spine_collision,
    get_paper_spine_status,
    plan_paper_spine,
    register_paper_spine,
    verify_paper_spine,
)
from constructive_numerical_core import (  # noqa: E402
    get_constructive_numerical_audit,
    run_constructive_numerical_audit,
    verify_constructive_numerical_audit,
)
from domain_skill_core import (  # noqa: E402
    admit_domain_skill,
    discover_domain_skills,
    domain_skill_status,
    optimize_domain_skill,
    scan_domain_skill,
    stage_domain_skill,
)
from frontier_skill_research_core import (  # noqa: E402
    finalize_frontier_skill_research,
    frontier_skill_research_status,
    plan_frontier_skill_research,
    record_frontier_skill_source,
    record_frontier_skill_trial,
    register_frontier_skill_hypothesis,
    verify_frontier_skill_research,
)
from skill_portability_core import (  # noqa: E402
    finalize_skill_portability,
    plan_skill_portability,
    record_skill_portability_source,
    record_skill_portability_trial,
    skill_portability_status,
    verify_skill_portability,
)
from skill_composition_core import (  # noqa: E402
    finalize_skill_composition,
    plan_skill_composition,
    record_skill_composition_source,
    record_skill_composition_trial,
    skill_composition_status,
    verify_skill_composition,
)
from discipline_profile_core import (  # noqa: E402
    analyze_discipline,
    discipline_status,
    initialize_discipline,
)
from research_knowledge_core import (  # noqa: E402
    knowledge_status,
    register_knowledge,
    search_knowledge,
    sync_knowledge,
)
from research_artifact_core import (  # noqa: E402
    plan_research_artifact,
    research_artifact_status,
    submit_research_artifact,
)
from research_integrity_core import (  # noqa: E402
    audit_statistics,
    document_status,
    execute_reproducibility,
    ingest_document,
    integrity_status,
    monitor_record_health,
    rank_systematic_review,
    record_preregistration_deviation,
    register_claim_evidence,
    register_preregistration,
    register_reproducibility_plan,
    submit_reproducibility_result,
)
from self_evolution_core import (  # noqa: E402
    evolution_status,
    propose_evolution,
    record_evolution_observation,
)
from dependency_manager import (  # noqa: E402
    DependencyError,
    cancel_install,
    clean_state,
    component_need as dependency_need,
    decide as dependency_decide,
    decline as dependency_decline,
    inventory as dependency_inventory,
    resume_install,
)
from intent_router_core import list_research_modules, select_research_modules  # noqa: E402
from preset_audit import audit_repository  # noqa: E402


TOOLS = [
    {
        "name": "select_research_modules",
        "description": "Register the main agent's explicit 1-3 module selection. No keyword model or automatic router chooses modules. Set method_change=true whenever the main agent judges that the research method changed; this invalidates prior novelty evidence.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_root": {"type": "string"},
                "request_text": {"type": "string"},
                "selected_modules": {"type": "array", "minItems": 1, "maxItems": 3, "items": {"type": "string"}},
                "selection_rationale": {"type": "string", "minLength": 12},
                "selected_by": {"type": "string", "enum": ["main_agent"]},
                "method_change": {"type": "boolean"},
            },
            "required": ["project_root", "request_text", "selected_modules", "selection_rationale", "selected_by", "method_change"],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_research_modules",
        "description": "List research modules and their contracts without making a semantic selection.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "register_method",
        "description": "Register a canonical research method. Any changed hash creates a new version and invalidates prior novelty evidence; a pending user-declared adjustment cannot be cleared with the unchanged method.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_root": {"type": "string"},
                "method": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "problem": {"type": "string"},
                        "mechanism": {"type": "string"},
                        "contributions": {"type": ["string", "array"]},
                        "datasets": {"type": ["string", "array"]},
                        "evaluation": {"type": ["string", "array"]},
                        "required_sources": {"type": ["string", "array"]},
                        "source_requirements": {"type": ["string", "array"]},
                        "method_files": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["title", "problem", "mechanism"],
                    "additionalProperties": True,
                },
            },
            "required": ["project_root", "method"],
            "additionalProperties": False,
        },
    },
    {
        "name": "classify_domain",
        "description": "Register a multi-domain source route explicitly selected by the main agent. This tool never classifies text automatically.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_root": {"type": "string"},
                "primary_domain": {"type": "string"},
                "secondary_domains": {"type": "array", "maxItems": 2, "items": {"type": "string"}},
                "selected_by": {"type": "string", "enum": ["main_agent"]},
                "selection_rationale": {"type": "string", "minLength": 12},
                "evidence_urls": {"type": "array", "items": {"type": "string", "format": "uri"}},
                "discipline_profile_id": {"type": "string"},
            },
            "required": ["project_root", "primary_domain", "selected_by", "selection_rationale"],
            "additionalProperties": False,
        },
    },
    {
        "name": "build_search_plan",
        "description": "Return the version-bound field-aware query plan, required databases, and index checks.",
        "inputSchema": {"type": "object", "properties": {"project_root": {"type": "string"}}, "required": ["project_root"]},
    },
    {
        "name": "list_sources",
        "description": "List verified scholarly discovery sources with direct UI, API, documentation, registration, and automation status.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "access": {"type": "string"},
                "automation": {"type": "string"},
                "domain": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "request_manual_evidence",
        "description": "Return the exact user questions, official URLs, accepted captures, and statuses needed for missing manual or credential-blocked sources.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_root": {"type": "string"},
                "sources": {"type": ["string", "array"], "items": {"type": "string"}},
            },
            "required": ["project_root"],
            "additionalProperties": False,
        },
    },
    {
        "name": "register_manual_evidence",
        "description": "Validate, hash, version-bind, and register a user-supplied official HTTPS export or page capture for a manual literature or index check.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_root": {"type": "string"},
                "source": {"type": "string"},
                "purpose": {"type": "string", "enum": ["literature_search", "index_membership"]},
                "query": {"type": "string"},
                "status": {
                    "type": "string",
                    "enum": ["zero_results", "hits_present", "index_verified", "index_not_listed", "access_blocked", "inconclusive"]
                },
                "evidence_path": {"type": "string"},
                "evidence_url": {"type": "string"},
                "records": {"type": "array", "items": {"type": "object"}},
                "identifier": {"type": "string"},
                "notes": {"type": "string"},
                "expected_sha256": {"type": "string"},
                "query_ids": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["project_root", "source", "purpose", "query", "status", "evidence_path", "evidence_url"],
            "additionalProperties": False,
        },
    },
    {
        "name": "run_novelty_search",
        "description": "Advance a persistent collision search by a bounded scheduling slice. Each unit is checkpointed; there is no research deadline and a per-attempt transport timeout never decides when research stops. Continue until COMPLETE or a factual blocker is reported.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_root": {"type": "string"},
                "attempt_timeout_seconds": {"type": "number", "exclusiveMinimum": 0, "maximum": 900},
                "work_units_per_call": {"type": "integer", "minimum": 1, "maximum": 20},
                "retry_unit_ids": {"type": "array", "items": {"type": "string"}},
                "blocker_decision": {
                    "type": "object",
                    "properties": {
                        "decision": {"type": "string", "enum": ["stop_with_factual_blocker"]},
                        "selected_by": {"type": "string", "enum": ["main_agent"]},
                        "unit_ids": {"type": "array", "minItems": 1, "items": {"type": "string"}},
                        "rationale": {"type": "string", "minLength": 40},
                        "evidence_urls": {"type": "array", "items": {"type": "string", "pattern": "^https://"}}
                    },
                    "required": ["decision", "selected_by", "unit_ids", "rationale"],
                    "additionalProperties": False
                },
                "source_limit": {"type": "integer", "minimum": 1, "maximum": 100},
            },
            "required": ["project_root"],
            "additionalProperties": False,
        },
    },
    {
        "name": "record_collision_resolution",
        "description": "Record a hash-bound differentiation decision for a candidate collision. Exact-identity collisions cannot be waived; every accepted record requires a complete search rerun.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_root": {"type": "string"},
                "collision_id": {"type": "string"},
                "decision": {"type": "string", "enum": ["differentiated", "duplicate", "needs_review"]},
                "rationale": {"type": "string", "minLength": 40},
                "differentiating_components": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["project_root", "collision_id", "decision", "rationale"],
            "additionalProperties": False,
        },
    },
    {
        "name": "verify_publication",
        "description": "Verify DOI syntax and resolve current publisher metadata through Crossref. The optional timeout bounds one network attempt only.",
        "inputSchema": {"type": "object", "properties": {"doi": {"type": "string"}, "attempt_timeout_seconds": {"type": "number", "exclusiveMinimum": 0, "maximum": 900}}, "required": ["doi"], "additionalProperties": False},
    },
    {
        "name": "verify_index_membership",
        "description": "Fail-closed verification for CCF, IEEE, SCI, SSCI, CSSCI, or C-journal membership.",
        "inputSchema": {
            "type": "object",
            "properties": {"identifier": {"type": "string"}, "index": {"type": "string"}},
            "required": ["identifier", "index"],
        },
    },
    {
        "name": "get_collision_report",
        "description": "Return the latest version-bound collision candidates, queries, and source coverage evidence.",
        "inputSchema": {"type": "object", "properties": {"project_root": {"type": "string"}}, "required": ["project_root"]},
    },
    {
        "name": "get_gate_status",
        "description": "Return the current fail-closed novelty gate and active method hash/version.",
        "inputSchema": {"type": "object", "properties": {"project_root": {"type": "string"}}, "required": ["project_root"]},
    },
    {
        "name": "paper_audit",
        "description": "Plan, formally verify, construct source-located legal numerical intervals and jointly feasible anchors, submit, or inspect a fail-closed paper audit; optionally optimize truthful presentation for an explicit AI-reviewer panel; and plan/render/audit/verify academic figures through the same canonical multiplexer.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["plan", "lean_check", "submit", "status", "verify"]},
                "verification_action": {"type": "string", "enum": ["cross_verify"]},
                "numerical_action": {"type": "string", "enum": ["construct", "status", "verify"]},
                "review_action": {
                    "type": "string",
                    "enum": [
                        "calibrate", "status", "ai_robustness", "ai_robustness_status",
                        "ai_optimize_plan", "ai_optimize_register", "ai_optimize_select", "ai_optimize_status"
                    ],
                },
                "integrity_action": {
                    "type": "string",
                    "enum": ["ingest", "ingest_status", "claim_evidence", "statistics", "record_health", "status"],
                },
                "tex_action": {"type": "string", "enum": ["compile"]},
                "figure_action": {"type": "string", "enum": ["plan", "render", "audit", "visual_review", "status", "verify"]},
                "image_action": {"type": "string", "enum": ["audit", "review", "status"]},
                "citation_action": {"type": "string", "enum": ["verify_format"]},
                "project_root": {"type": "string"},
                "request_text": {"type": "string"},
                "paper_files": {"type": "array", "items": {"type": "string"}},
                "evidence_files": {"type": "array", "items": {"type": "string"}},
                "figure_ids": {"type": "array", "items": {"type": "string"}},
                "selected_roles": {"type": "array", "minItems": 2, "maxItems": 3, "items": {"type": "string"}},
                "audit_features": {
                    "type": "object",
                    "properties": {
                        "formula": {"type": "boolean"}, "experiment": {"type": "boolean"},
                        "constructive_numerical": {"type": "boolean"},
                        "literature": {"type": "boolean"}, "venue": {"type": "boolean"},
                        "impact": {"type": "boolean"}, "openreview": {"type": "boolean"},
                        "image_integrity": {"type": "boolean"}, "figures": {"type": "boolean"},
                        "ai_reviewer": {"type": "boolean"},
                        "ai_reviewer_optimization": {"type": "boolean"}
                    },
                    "additionalProperties": False
                },
                "selection_rationale": {"type": "string", "minLength": 12},
                "figure_id": {"type": "string"},
                "figure_kind": {"type": "string", "enum": ["statistical", "diagram"]},
                "source_files": {"type": "array", "items": {"type": "string"}},
                "width_mm": {"type": "number", "minimum": 20, "maximum": 400},
                "height_mm": {"type": "number", "minimum": 20, "maximum": 500},
                "formats": {"type": "array", "items": {"type": "string", "enum": ["svg", "pdf", "png"]}},
                "venue_contract": {"type": "object"},
                "spec": {"type": "object"},
                "rendered_png_sha256": {"type": "string"},
                "review_method": {"type": "string", "enum": ["actual_png_at_final_size"]},
                "checks": {"type": "object"},
                "issues": {"type": "array", "items": {"type": "string"}},
                "effort": {"type": "string", "enum": ["low", "medium", "high"]},
                "lean_file": {"type": "string"},
                "tex_file": {"type": "string"},
                "formula_manifest": {"type": "object"},
                "verification_manifest": {"type": "object"},
                "numeric_constraint_manifest": {"type": "object"},
                "numeric_audit_id": {"type": "string"},
                "runtime_root": {"type": "string"},
                "attempt_timeout_seconds": {"type": "number", "exclusiveMinimum": 0, "maximum": 900},
                "process_timeout_seconds": {"type": "number", "minimum": 1},
                "role_reports": {"type": "array", "items": {"type": "object"}},
                "online_checks": {"type": "array", "items": {"type": "object"}},
                "literature_items": {"type": "array", "items": {"type": "object"}},
                "claim_evidence_items": {"type": "array", "items": {"type": "object"}},
                "experiment_check": {"type": "object"},
                "doi": {"type": "string"},
                "citation_style": {"type": "string", "enum": ["apa", "mla", "ieee", "harvard"]},
                "citation_number": {"type": "integer", "minimum": 1},
                "document_path": {"type": "string"},
                "document_id": {"type": "string"},
                "parser_backend": {"type": "string", "enum": ["auto", "docling", "grobid", "mineru", "marker"]},
                "parser_output_path": {"type": "string"},
                "source_url": {"type": "string"},
                "graph_id": {"type": "string"},
                "claims": {"type": "array", "items": {"type": "object"}},
                "evidence": {"type": "array", "items": {"type": "object"}},
                "edges": {"type": "array", "items": {"type": "object"}},
                "selected_by": {"type": "string", "enum": ["user", "main_agent"]},
                "audit_id": {"type": "string"},
                "text": {"type": "string"},
                "source_path": {"type": "string"},
                "alpha": {"type": "number", "exclusiveMinimum": 0, "exclusiveMaximum": 1},
                "robustness_cases": {"type": "array", "items": {"type": "object"}},
                "watch_id": {"type": "string"},
                "fixture_record": {"type": "object"},
                "component": {"type": "string"},
                "identifier": {"type": "string"},
                "calibration_id": {"type": "string"},
                "forum_ids": {"type": "array", "items": {"type": "string"}},
                "fixture_payload": {"type": "object"},
                "categories": {"type": "object"},
                "image_audit_id": {"type": "string"},
                "images": {"type": "array", "items": {"type": "object"}},
                "transformations": {"type": "array", "items": {"type": "object"}},
                "approximate_image_distance": {"type": "integer", "minimum": 0, "maximum": 12},
                "approximate_region_distance": {"type": "integer", "minimum": 0, "maximum": 8},
                "audit_sha256": {"type": "string"},
                "image_review_method": {"type": "string", "enum": ["expert_original_resolution"]},
                "image_review_decisions": {"type": "array", "items": {"type": "object"}},
                "reviewer": {"type": "string"},
                "ai_review_audit_id": {"type": "string"},
                "ai_review_online_evidence": {"type": "array", "items": {"type": "object"}},
                "model_evaluations": {"type": "array", "items": {"type": "object"}},
                "ai_optimization_id": {"type": "string"},
                "optimization_goal": {"type": "string", "enum": ["maximize_ai_reviewer_score"]},
                "venue_reviewer_contract": {"type": "object"},
                "candidate_manuscripts": {"type": "array", "minItems": 1, "maxItems": 8, "items": {"type": "object"}},
                "optimization_model_evaluations": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["action", "project_root"],
            "additionalProperties": False,
        },
    },
    {
        "name": "research_design",
        "description": "Plan research ideas and strategy; preserve main-agent-decomposed multistep user requirements in an append-only, evidence-bound instruction ledger; after explicit user authorization, inventory local resources and coordinate collision-checked, managed coarse-test iterations into exactly five unranked directions for user choice; create hash-bound resource-aware DAGs, bind one READY managed task to the existing frozen reproducibility executor, and preserve native-subagent-first LLM assistance receipts; analyze or initialize version-bound discipline profiles; maintain domain Skills, target-harness frontier Skill evaluation, optional target-cell portability evidence, and exact ordered-composition utility, interference, order, and declared path-safety evidence; maintain compact research knowledge, validated research artifacts, and proposal-only evolution; register user-selected candidates, hypotheses, and experiments; freeze and analyze independent-run metrics; and perform validation-only constrained comparison. The instruction ledger never overrides higher-authority, safety, legal, privacy, or factual constraints. The tool never accepts a second command contract, silently falls back to an external LLM API, ranks ideas, chooses a final direction or branch, executes third-party Skills, applies its own evolution proposals, or exposes final-test rows during optimization.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "plan_ideation", "register_candidates", "commit_candidate",
                        "plan_strategy", "register_strategy", "decide_strategy_branch",
                        "register_hypothesis", "register_experiment", "status", "verify"
                    ],
                },
                "project_root": {"type": "string"},
                "request_text": {"type": "string"},
                "problem": {"type": "string"},
                "constraints": {"type": "array", "items": {"type": "string"}},
                "plan_hash": {"type": "string"},
                "candidates": {"type": "array", "items": {"type": "object"}},
                "candidate_id": {"type": "string"},
                "selected_by": {"type": "string", "enum": ["user"]},
                "method": {"type": "object"},
                "strategy_plan_hash": {"type": "string"},
                "strategy": {"type": "object"},
                "decision_id": {"type": "string"},
                "branch_id": {"type": "string"},
                "rationale": {"type": "string"},
                "hypothesis": {"type": "object"},
                "experiment": {"type": "object"},
                "instruction_action": {"type": "string", "enum": ["register", "record", "waive", "status", "verify"]},
                "instruction_contract_id": {"type": "string"},
                "instruction_request_text": {"type": "string"},
                "instruction_scope": {"type": "string"},
                "instruction_requirements": {"type": "array", "minItems": 1, "maxItems": 64, "items": {"type": "object"}},
                "instruction_selected_by": {"type": "string", "enum": ["main_agent", "user"]},
                "instruction_selection_rationale": {"type": "string"},
                "instruction_requirement_id": {"type": "string"},
                "instruction_outcome": {"type": "string", "enum": ["satisfied", "blocked", "user_decision_required"]},
                "instruction_evidence": {"type": "array", "items": {"type": "object"}},
                "instruction_note": {"type": "string"},
                "instruction_blocker_code": {"type": "string"},
                "instruction_user_message_sha256": {"type": "string"},
                "instruction_waiver_rationale": {"type": "string"},
                "metrics_action": {"type": "string", "enum": ["plan", "analyze", "optimize", "status", "verify"]},
                "resource_plan_action": {"type": "string", "enum": ["inventory", "plan", "execute", "record", "status", "verify"]},
                "resource_plan_id": {"type": "string"},
                "resource_task_goal": {"type": "string"},
                "resource_tasks": {"type": "array", "minItems": 1, "maxItems": 64, "items": {"type": "object"}},
                "resource_constraints": {"type": "object"},
                "resource_selected_by": {"type": "string", "enum": ["main_agent"]},
                "resource_task_id": {"type": "string"},
                "resource_task_status": {"type": "string", "enum": ["running", "completed", "failed", "blocked", "unknown"]},
                "resource_task_artifacts": {"type": "array", "items": {"type": "string"}},
                "resource_observation": {"type": "object"},
                "resource_task_note": {"type": "string"},
                "direction_action": {
                    "type": "string",
                    "enum": [
                        "plan", "register", "activate", "record_iteration",
                        "bind_collision", "revise", "finalize", "status", "verify"
                    ],
                },
                "direction_exploration_id": {"type": "string"},
                "direction_authorization_scope": {"type": "string"},
                "direction_problem": {"type": "string"},
                "direction_constraints": {"type": "array", "items": {"type": "string"}},
                "direction_authorized_by": {"type": "string", "enum": ["user"]},
                "direction_candidates": {"type": "array", "minItems": 5, "maxItems": 15, "items": {"type": "object"}},
                "direction_candidate_id": {"type": "string"},
                "direction_run_id": {"type": "string"},
                "direction_result_path": {"type": "string"},
                "direction_revised_candidate": {"type": "object"},
                "direction_change_summary": {"type": "string"},
                "direction_choice_ids": {"type": "array", "minItems": 5, "maxItems": 5, "items": {"type": "string"}},
                "direction_selected_by": {"type": "string", "enum": ["main_agent"]},
                "direction_selection_rationale": {"type": "string"},
                "delegation_action": {"type": "string", "enum": ["plan", "submit", "status", "verify"]},
                "delegation_task_id": {"type": "string"},
                "delegation_task_type": {
                    "type": "string",
                    "enum": [
                        "literature_synthesis", "idea_critique", "draft_review", "translation_review",
                        "metric_interpretation", "code_experiment_review", "ai_reviewer_evaluation", "other"
                    ],
                },
                "delegation_task_summary": {"type": "string"},
                "delegation_selected_by": {"type": "string", "enum": ["main_agent"]},
                "subagent_available": {"type": "boolean"},
                "external_requirement": {
                    "type": "string",
                    "enum": ["none", "user_requested_provider", "cross_provider_protocol"],
                },
                "requested_provider": {"type": "string"},
                "external_selected_by": {"type": "string", "enum": ["user"]},
                "external_rationale": {"type": "string"},
                "delegation_execution_mode": {
                    "type": "string",
                    "enum": ["native_subagent", "main_agent_local", "external_api_exception"],
                },
                "delegation_executor_id": {"type": "string"},
                "delegation_model_tier": {"type": "string", "enum": ["entry", "economy", "lowest_capable"]},
                "delegation_reasoning_effort": {"type": "string", "enum": ["low", "medium"]},
                "delegation_escalation_rationale": {"type": "string"},
                "delegation_artifact_path": {"type": "string"},
                "delegation_provider_model_id": {"type": "string"},
                "metric_plan": {"type": "object"},
                "metrics_selected_by": {"type": "string", "enum": ["user", "main_agent"]},
                "metrics_data_path": {"type": "string"},
                "analysis_id": {"type": "string"},
                "baseline_configuration": {"type": "string"},
                "optimization_id": {"type": "string"},
                "objectives": {"type": "array", "items": {"type": "string"}},
                "metric_constraints": {"type": "array", "items": {"type": "object"}},
                "objective_weights": {"type": "object"},
                "reference_scales": {"type": "object"},
                "optimization_selected_by": {"type": "string", "enum": ["user"]},
                "knowledge_action": {"type": "string", "enum": ["sync", "register", "search", "status"]},
                "domain_skill_action": {"type": "string", "enum": ["discover", "stage", "scan", "optimize", "admit", "status"]},
                "frontier_skill_action": {
                    "type": "string",
                    "enum": ["plan", "record_source", "register_hypothesis", "record_trial", "finalize", "status", "verify"],
                },
                "frontier_protocol_id": {"type": "string"},
                "frontier_protocol": {"type": "object"},
                "frontier_selected_by": {"type": "string", "enum": ["main_agent"]},
                "frontier_selection_rationale": {"type": "string", "minLength": 20},
                "frontier_source": {"type": "object"},
                "frontier_hypothesis": {"type": "object"},
                "frontier_trial_path": {"type": "string"},
                "skill_portability_action": {
                    "type": "string",
                    "enum": ["plan", "record_source", "record_trial", "finalize", "status", "verify"],
                },
                "skill_portability_id": {"type": "string"},
                "skill_portability_protocol": {"type": "object"},
                "skill_portability_selected_by": {"type": "string", "enum": ["main_agent"]},
                "skill_portability_selection_rationale": {"type": "string", "minLength": 20},
                "skill_portability_source": {"type": "object"},
                "skill_portability_trial_path": {"type": "string"},
                "skill_composition_action": {
                    "type": "string",
                    "enum": ["plan", "record_source", "record_trial", "finalize", "status", "verify"],
                },
                "skill_composition_id": {"type": "string"},
                "skill_composition_protocol": {"type": "object"},
                "skill_composition_selected_by": {"type": "string", "enum": ["main_agent"]},
                "skill_composition_selection_rationale": {"type": "string", "minLength": 20},
                "skill_composition_source": {"type": "object"},
                "skill_composition_trial_path": {"type": "string"},
                "discipline_action": {"type": "string", "enum": ["analyze", "initialize", "status", "verify"]},
                "artifact_action": {"type": "string", "enum": ["plan", "submit", "status", "verify"]},
                "evolution_action": {"type": "string", "enum": ["record", "propose", "status"]},
                "dependency_action": {"type": "string", "enum": ["inventory", "need", "reuse", "install", "not_now"]},
                "dependency_component": {"type": "string", "enum": ["portable-git", "tex-basic", "lean-mathlib"]},
                "dependency_selected_by": {"type": "string", "enum": ["user"]},
                "maintenance_action": {"type": "string", "enum": ["status", "install", "update", "resume", "cancel", "clean", "hard-clean", "preset-audit"]},
                "maintenance_project_root": {"type": "string"},
                "maintenance_home": {"type": "string"},
                "maintenance_dry_run": {"type": "boolean"},
                "maintenance_cancel": {"type": "boolean"},
                "maintenance_include_ignored": {"type": "boolean"},
                "maintenance_policy": {"type": "string"},
                "query": {"type": "string"},
                "discipline": {"type": "string"},
                "discipline_broad_domain": {"type": "string"},
                "discipline_selected_by": {"type": "string", "enum": ["main_agent"]},
                "discipline_selection_rationale": {"type": "string", "minLength": 12},
                "attempt_timeout_seconds": {"type": "number", "exclusiveMinimum": 0, "maximum": 900},
                "force": {"type": "boolean"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                "nodes": {"type": "array", "items": {"type": "object"}},
                "edges": {"type": "array", "items": {"type": "object"}},
                "repository": {"type": "string"},
                "skill_id": {"type": "string"},
                "skill_path": {"type": "string"},
                "commit": {"type": "string"},
                "rounds": {"type": "integer", "minimum": 2, "maximum": 3},
                "positive_prompts": {"type": "array", "items": {"type": "string"}},
                "negative_prompts": {"type": "array", "items": {"type": "string"}},
                "overlap_decision": {"type": "string", "enum": ["domain_only", "fuse_narrow_adapter"]},
                "canonical_owner": {"type": "string"},
                "artifact_type": {"type": "string", "enum": ["paper_card", "systematic_review", "experiment_log", "reviewer_response"]},
                "artifact_id": {"type": "string"},
                "source_files": {"type": "array", "items": {"type": "string"}},
                "protocol": {"type": "object"},
                "artifact": {"type": "object"},
                "category": {"type": "string", "enum": ["trigger_miss", "trigger_confusion", "tool_failure", "user_correction", "context_cost", "regression"]},
                "component": {"type": "string"},
                "expected": {"type": "string"},
                "observed": {"type": "string"},
                "evidence_urls": {"type": "array", "items": {"type": "string"}},
                "evidence_hash": {"type": "string"},
                "integrity_action": {
                    "type": "string",
                    "enum": ["preregister", "record_deviation", "repro_plan", "repro_execute", "repro_submit", "review_rank", "status"],
                },
                "prereg_id": {"type": "string"},
                "deviation": {"type": "object"},
                "run_id": {"type": "string"},
                "reproducibility_plan": {"type": "object"},
                "reproducibility_result": {"type": "object"},
                "review_id": {"type": "string"},
                "records": {"type": "array", "items": {"type": "object"}},
                "process_timeout_seconds": {"type": "number", "minimum": 1},
                "integrity_component": {"type": "string"},
                "identifier": {"type": "string"},
            },
            "required": ["action", "project_root"],
            "additionalProperties": False,
        },
    },
    {
        "name": "language_assist",
        "description": "Plan, analyze, resolve, and verify evidence-bounded academic language, translation, exact venue evidence, and macro-first paper spines. Missing venue assets require online acquisition instead of invented structure; limitation and ethics outcomes remain user decisions; collision evidence differentiates a formed method rather than narrowing idea generation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["plan", "analyze", "register_card", "retrieve", "resolve", "finalize", "status", "verify"],
                },
                "spine_action": {
                    "type": "string",
                    "enum": ["plan", "register", "bind_collision", "status", "verify"],
                },
                "venue_action": {"type": "string", "enum": ["list", "resolve", "register", "status", "verify"]},
                "project_root": {"type": "string"},
                "request_text": {"type": "string"},
                "manuscript_files": {"type": "array", "items": {"type": "string"}},
                "draft_text": {"type": "string"},
                "claim_ids": {"type": "array", "items": {"type": "string"}},
                "protected_spans": {"type": "array", "items": {"type": "object"}},
                "section": {"type": "string"},
                "discipline": {"type": "string"},
                "venue": {"type": "string"},
                "venue_year": {"type": "integer", "minimum": 1900, "maximum": 2200},
                "venue_track": {"type": "string"},
                "venue_stage": {"type": "string"},
                "venue_receipt_sha256": {"type": "string"},
                "venue_profile": {"type": "object"},
                "language": {"type": "string"},
                "task_mode": {"type": "string", "enum": ["academic_polish", "translation", "conference_writing"]},
                "source_text": {"type": "string"},
                "source_language": {"type": "string"},
                "target_language": {"type": "string"},
                "terminology": {"type": "array", "items": {"type": "object"}},
                "venue_contract": {"type": "object"},
                "card": {"type": "object"},
                "query": {"type": "string"},
                "paragraph_role": {"type": "string"},
                "evidence_type": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 4},
                "resolutions": {"type": "array", "items": {"type": "object"}},
                "decisions": {"type": "array", "items": {"type": "object"}},
                "spine_id": {"type": "string"},
                "spine_plan_hash": {"type": "string"},
                "spine_observation": {"type": "string"},
                "spine_domain_scope": {"type": "string"},
                "spine_selected_by": {"type": "string", "enum": ["main_agent"]},
                "spine": {"type": "object"},
            },
            "required": ["action", "project_root"],
            "additionalProperties": False,
        },
    },
]


def dispatch(name: str, arguments: dict[str, Any]) -> Any:
    if name == "list_research_modules":
        return list_research_modules()
    if name == "select_research_modules":
        return select_research_modules(
            arguments["project_root"], request_text=arguments["request_text"],
            selected_modules=arguments["selected_modules"],
            selection_rationale=arguments["selection_rationale"], selected_by=arguments["selected_by"],
            method_change=bool(arguments["method_change"]),
        )
    if name == "register_method":
        return register_method(arguments["project_root"], arguments["method"])
    if name == "classify_domain":
        return refresh_domain(
            arguments["project_root"], primary_domain=arguments["primary_domain"],
            secondary_domains=arguments.get("secondary_domains"), selected_by=arguments["selected_by"],
            selection_rationale=arguments["selection_rationale"], evidence_urls=arguments.get("evidence_urls"),
            discipline_profile_id=arguments.get("discipline_profile_id"),
        )
    if name == "build_search_plan":
        return get_search_plan(arguments["project_root"])
    if name == "list_sources":
        return list_sources(
            access=arguments.get("access"), automation=arguments.get("automation"), domain=arguments.get("domain"),
        )
    if name == "request_manual_evidence":
        return request_manual_evidence(arguments["project_root"], arguments.get("sources"))
    if name == "register_manual_evidence":
        return register_manual_evidence(
            arguments["project_root"], source=arguments["source"], purpose=arguments["purpose"],
            query=arguments["query"], status=arguments["status"], evidence_path=arguments["evidence_path"],
            evidence_url=arguments["evidence_url"], records=arguments.get("records"),
            identifier=arguments.get("identifier"), notes=arguments.get("notes"),
            expected_sha256=arguments.get("expected_sha256"), query_ids=arguments.get("query_ids"),
        )
    if name == "run_novelty_search":
        return run_novelty_search(
            arguments["project_root"],
            attempt_timeout_seconds=float(arguments.get("attempt_timeout_seconds", 20)),
            source_limit=arguments.get("source_limit"), work_units_per_call=arguments.get("work_units_per_call"),
            retry_unit_ids=arguments.get("retry_unit_ids"),
            blocker_decision=arguments.get("blocker_decision"),
        )
    if name == "record_collision_resolution":
        return record_collision_resolution(
            arguments["project_root"], collision_id=arguments["collision_id"],
            decision=arguments["decision"], rationale=arguments["rationale"],
            differentiating_components=arguments.get("differentiating_components"),
        )
    if name == "verify_publication":
        return verify_publication(arguments["doi"], timeout=float(arguments.get("attempt_timeout_seconds", 20)))
    if name == "verify_index_membership":
        return verify_index_membership(arguments["identifier"], arguments["index"])
    if name == "get_collision_report":
        return get_collision_report(arguments["project_root"])
    if name == "get_gate_status":
        return get_gate_status(arguments["project_root"])
    if name == "paper_audit":
        action = arguments["action"]
        integrity_action = arguments.get("integrity_action")
        figure_action = arguments.get("figure_action")
        image_action = arguments.get("image_action")
        citation_action = arguments.get("citation_action")
        tex_action = arguments.get("tex_action")
        verification_action = arguments.get("verification_action")
        numerical_action = arguments.get("numerical_action")
        review_action = arguments.get("review_action")
        if integrity_action == "ingest":
            return ingest_document(
                arguments["project_root"], arguments.get("document_path", ""), arguments.get("document_id", ""),
                parser_backend=arguments.get("parser_backend", "auto"),
                parser_output_path=arguments.get("parser_output_path"), source_url=arguments.get("source_url"),
            )
        if integrity_action == "ingest_status":
            return document_status(arguments["project_root"], arguments.get("document_id", ""))
        if integrity_action == "claim_evidence":
            return register_claim_evidence(
                arguments["project_root"], arguments.get("graph_id", ""),
                arguments.get("claims") or [], arguments.get("evidence") or [], arguments.get("edges") or [],
                selected_by=arguments.get("selected_by", ""),
            )
        if integrity_action == "statistics":
            return audit_statistics(
                arguments["project_root"], arguments.get("audit_id", ""), text=arguments.get("text"),
                source_path=arguments.get("source_path"), alpha=float(arguments.get("alpha", 0.05)),
                robustness_cases=arguments.get("robustness_cases"),
            )
        if integrity_action == "record_health":
            return monitor_record_health(
                arguments["project_root"], arguments.get("watch_id", ""), arguments.get("doi", ""),
                timeout=float(arguments.get("attempt_timeout_seconds", 20)), fixture_record=arguments.get("fixture_record"),
            )
        if integrity_action == "status":
            return integrity_status(
                arguments["project_root"], arguments.get("component"), arguments.get("identifier"),
            )
        if citation_action == "verify_format":
            return verify_and_format_citation(
                arguments.get("doi", ""), arguments.get("citation_style", ""),
                number=arguments.get("citation_number", 1), timeout=float(arguments.get("attempt_timeout_seconds", 20)),
            )
        if tex_action == "compile":
            return compile_tex_document(
                arguments["project_root"], arguments.get("tex_file", ""),
                timeout=float(arguments.get("process_timeout_seconds", 180)),
            )
        if figure_action == "plan":
            return plan_academic_figure(
                arguments["project_root"], figure_id=arguments.get("figure_id", ""),
                request_text=arguments.get("request_text", ""), figure_kind=arguments.get("figure_kind", ""),
                source_files=arguments.get("source_files"), width_mm=arguments.get("width_mm"),
                height_mm=arguments.get("height_mm"), formats=arguments.get("formats"),
                effort=arguments.get("effort", "medium"), venue_contract=arguments.get("venue_contract"),
                selected_roles=arguments.get("selected_roles"), selected_by=arguments.get("selected_by", ""),
                selection_rationale=arguments.get("selection_rationale", ""),
            )
        if figure_action == "render":
            return render_academic_figure(arguments["project_root"], arguments.get("figure_id", ""), arguments.get("spec") or {})
        if figure_action == "audit":
            return audit_academic_figure(arguments["project_root"], arguments.get("figure_id", ""))
        if figure_action == "visual_review":
            return record_visual_review(
                arguments["project_root"], arguments.get("figure_id", ""),
                rendered_png_sha256=arguments.get("rendered_png_sha256", ""),
                review_method=arguments.get("review_method", ""), checks=arguments.get("checks") or {},
                issues=arguments.get("issues"),
            )
        if figure_action == "status":
            return get_academic_figure_status(arguments["project_root"], arguments.get("figure_id", ""))
        if figure_action == "verify":
            return verify_academic_figure(arguments["project_root"], arguments.get("figure_id", ""))
        if image_action == "audit":
            image_result = audit_scientific_image_integrity(
                arguments["project_root"], arguments.get("image_audit_id", ""),
                images=arguments.get("images") or [], transformations=arguments.get("transformations") or [],
                approximate_image_distance=arguments.get("approximate_image_distance", 5),
                approximate_region_distance=arguments.get("approximate_region_distance", 3),
            )
            return attach_paper_auxiliary_audit(arguments["project_root"], "scientific_image_integrity", image_result)
        if image_action == "status":
            return get_scientific_image_integrity_status(
                arguments["project_root"], arguments.get("image_audit_id", ""),
            )
        if image_action == "review":
            reviewed = record_scientific_image_review(
                arguments["project_root"], arguments.get("image_audit_id", ""),
                audit_sha256=arguments.get("audit_sha256", ""),
                review_method=arguments.get("image_review_method", ""),
                decisions=arguments.get("image_review_decisions") or [], reviewer=arguments.get("reviewer", ""),
            )
            return attach_paper_auxiliary_audit(arguments["project_root"], "scientific_image_integrity", reviewed)
        if action == "plan":
            return plan_paper_audit(
                arguments["project_root"], arguments.get("request_text", ""),
                paper_files=arguments.get("paper_files"), evidence_files=arguments.get("evidence_files"),
                figure_ids=arguments.get("figure_ids"),
                selected_roles=arguments.get("selected_roles"), audit_features=arguments.get("audit_features"),
                selected_by=arguments.get("selected_by", ""),
                selection_rationale=arguments.get("selection_rationale", ""),
                effort=arguments.get("effort", "medium"),
            )
        if action == "lean_check":
            return run_lean_formula_audit(
                arguments["project_root"], arguments.get("lean_file", ""),
                arguments.get("formula_manifest") or {}, runtime_root=arguments.get("runtime_root"),
                timeout=float(arguments.get("process_timeout_seconds", 360)),
            )
        if verification_action == "cross_verify":
            return run_formula_cross_verification(
                arguments["project_root"], arguments.get("verification_manifest") or {},
                timeout=float(arguments.get("process_timeout_seconds", 180)),
            )
        if numerical_action == "construct":
            numerical = run_constructive_numerical_audit(
                arguments["project_root"], arguments.get("numeric_constraint_manifest") or {},
                timeout=float(arguments.get("process_timeout_seconds", 180)),
            )
            return attach_paper_auxiliary_audit(
                arguments["project_root"], "constructive_numerical_audit", numerical,
            )
        if numerical_action == "status":
            return get_constructive_numerical_audit(
                arguments["project_root"], arguments.get("numeric_audit_id", ""),
            )
        if numerical_action == "verify":
            return verify_constructive_numerical_audit(
                arguments["project_root"], arguments.get("numeric_audit_id", ""),
            )
        if review_action == "calibrate":
            calibration = calibrate_openreview(
                arguments["project_root"], arguments.get("calibration_id", ""),
                forum_ids=arguments.get("forum_ids"), fixture_payload=arguments.get("fixture_payload"),
                categories=arguments.get("categories"), timeout=float(arguments.get("attempt_timeout_seconds", 30)),
            )
            return attach_paper_auxiliary_audit(arguments["project_root"], "openreview_calibration", calibration)
        if review_action == "status":
            return get_openreview_calibration(arguments["project_root"], arguments.get("calibration_id", ""))
        if review_action == "ai_robustness":
            ai_review = audit_ai_reviewer_robustness(
                arguments["project_root"], arguments.get("ai_review_audit_id", ""),
                manuscript_files=arguments.get("paper_files"),
                online_evidence=arguments.get("ai_review_online_evidence"),
                model_evaluations=arguments.get("model_evaluations"),
            )
            return attach_paper_auxiliary_audit(arguments["project_root"], "ai_reviewer_robustness", ai_review)
        if review_action == "ai_robustness_status":
            return get_ai_reviewer_robustness_status(
                arguments["project_root"], arguments.get("ai_review_audit_id", ""),
            )
        if review_action == "ai_optimize_plan":
            return plan_ai_reviewer_optimization(
                arguments["project_root"], arguments.get("ai_optimization_id", ""),
                manuscript_files=arguments.get("paper_files"),
                online_evidence=arguments.get("ai_review_online_evidence"),
                venue_reviewer_contract=arguments.get("venue_reviewer_contract"),
                selected_by=arguments.get("selected_by", ""),
                optimization_goal=arguments.get("optimization_goal", "maximize_ai_reviewer_score"),
            )
        if review_action == "ai_optimize_register":
            return register_ai_reviewer_candidates(
                arguments["project_root"], arguments.get("ai_optimization_id", ""),
                candidates=arguments.get("candidate_manuscripts"),
            )
        if review_action == "ai_optimize_select":
            optimized = select_ai_reviewer_candidate(
                arguments["project_root"], arguments.get("ai_optimization_id", ""),
                model_evaluations=arguments.get("optimization_model_evaluations"),
            )
            return attach_paper_auxiliary_audit(arguments["project_root"], "ai_reviewer_optimization", optimized)
        if review_action == "ai_optimize_status":
            return get_ai_reviewer_optimization_status(
                arguments["project_root"], arguments.get("ai_optimization_id", ""),
            )
        if action == "submit":
            return submit_paper_audit(
                arguments["project_root"], role_reports=arguments.get("role_reports") or [],
                online_checks=arguments.get("online_checks") or [],
                literature_items=arguments.get("literature_items"),
                claim_evidence_items=arguments.get("claim_evidence_items"),
                experiment_check=arguments.get("experiment_check"),
            )
        if action in {"status", "verify"}:
            return get_paper_audit_status(arguments["project_root"])
    if name == "research_design":
        action = arguments["action"]
        integrity_action = arguments.get("integrity_action")
        knowledge_action = arguments.get("knowledge_action")
        domain_skill_action = arguments.get("domain_skill_action")
        frontier_skill_action = arguments.get("frontier_skill_action")
        skill_portability_action = arguments.get("skill_portability_action")
        skill_composition_action = arguments.get("skill_composition_action")
        discipline_action = arguments.get("discipline_action")
        artifact_action = arguments.get("artifact_action")
        evolution_action = arguments.get("evolution_action")
        dependency_action = arguments.get("dependency_action")
        maintenance_action = arguments.get("maintenance_action")
        metrics_action = arguments.get("metrics_action")
        resource_plan_action = arguments.get("resource_plan_action")
        delegation_action = arguments.get("delegation_action")
        direction_action = arguments.get("direction_action")
        instruction_action = arguments.get("instruction_action")
        if maintenance_action:
            # Lifecycle maintenance is intentionally a short, explicit
            # subroute of research_design: install/update are one idempotent
            # optional-component operation, while clean/hard-clean remove only
            # named generated state.  No repository-wide lock or long-lived
            # transaction is introduced here.
            maintenance_root = arguments.get("maintenance_project_root") or arguments.get("project_root")
            maintenance_home = arguments.get("maintenance_home")
            if maintenance_action == "status":
                return dependency_inventory()
            if maintenance_action == "preset-audit":
                return audit_repository(
                    maintenance_root,
                    policy_path=arguments.get("maintenance_policy"),
                    include_ignored=bool(arguments.get("maintenance_include_ignored", True)),
                )
            if maintenance_action in {"clean", "hard-clean"}:
                return clean_state(
                    maintenance_root,
                    home=maintenance_home,
                    hard=maintenance_action == "hard-clean",
                    dry_run=bool(arguments.get("maintenance_dry_run", False)),
                    cancel=bool(arguments.get("maintenance_cancel", False)),
                )
            if maintenance_action == "resume":
                return resume_install()
            if maintenance_action == "cancel":
                return cancel_install()
            if maintenance_action in {"install", "update"}:
                if arguments.get("dependency_selected_by") != "user":
                    raise DependencyError(
                        "DEPENDENCY_USER_SELECTION_REQUIRED",
                        "maintenance install/update requires dependency_selected_by=user after the user chooses the component",
                    )
                component_id = arguments.get("dependency_component", "")
                if not component_id:
                    raise DependencyError(
                        "DEPENDENCY_COMPONENT_REQUIRED",
                        "maintenance install/update requires dependency_component",
                    )
                value = dependency_decide([component_id], [])
                value["operation"] = "install"
                value["requested_command"] = maintenance_action
                return value
        if instruction_action == "register":
            return register_instruction_contract(
                arguments["project_root"], contract_id=arguments.get("instruction_contract_id", ""),
                request_text=arguments.get("instruction_request_text", ""),
                scope=arguments.get("instruction_scope", ""),
                requirements=arguments.get("instruction_requirements") or [],
                selected_by=arguments.get("instruction_selected_by", ""),
                selection_rationale=arguments.get("instruction_selection_rationale", ""),
            )
        if instruction_action == "record":
            return record_instruction_requirement(
                arguments["project_root"], contract_id=arguments.get("instruction_contract_id", ""),
                requirement_id=arguments.get("instruction_requirement_id", ""),
                outcome=arguments.get("instruction_outcome", ""),
                evidence=arguments.get("instruction_evidence"),
                note=arguments.get("instruction_note", ""),
                blocker_code=arguments.get("instruction_blocker_code"),
                selected_by=arguments.get("instruction_selected_by", ""),
            )
        if instruction_action == "waive":
            return waive_instruction_requirement(
                arguments["project_root"], contract_id=arguments.get("instruction_contract_id", ""),
                requirement_id=arguments.get("instruction_requirement_id", ""),
                rationale=arguments.get("instruction_waiver_rationale", ""),
                user_message_sha256=arguments.get("instruction_user_message_sha256", ""),
                selected_by=arguments.get("instruction_selected_by", ""),
            )
        if instruction_action == "status":
            return instruction_adherence_status(
                arguments["project_root"], arguments.get("instruction_contract_id"),
            )
        if instruction_action == "verify":
            return verify_instruction_contract(
                arguments["project_root"], arguments.get("instruction_contract_id"),
            )
        if direction_action == "plan":
            return plan_direction_exploration(
                arguments["project_root"], exploration_id=arguments.get("direction_exploration_id", ""),
                authorization_scope=arguments.get("direction_authorization_scope", ""),
                problem=arguments.get("direction_problem", ""),
                constraints=arguments.get("direction_constraints"),
                authorized_by=arguments.get("direction_authorized_by", ""),
            )
        if direction_action == "register":
            return register_direction_candidates(
                arguments["project_root"], exploration_id=arguments.get("direction_exploration_id", ""),
                candidates=arguments.get("direction_candidates") or [],
                selected_by=arguments.get("direction_selected_by", ""),
                selection_rationale=arguments.get("direction_selection_rationale", ""),
            )
        if direction_action == "activate":
            return activate_direction_candidate(
                arguments["project_root"], exploration_id=arguments.get("direction_exploration_id", ""),
                candidate_id=arguments.get("direction_candidate_id", ""),
            )
        if direction_action == "record_iteration":
            return record_direction_iteration(
                arguments["project_root"], exploration_id=arguments.get("direction_exploration_id", ""),
                candidate_id=arguments.get("direction_candidate_id", ""),
                run_id=arguments.get("direction_run_id", ""),
                result_path=arguments.get("direction_result_path", ""),
            )
        if direction_action == "bind_collision":
            return bind_direction_collision(
                arguments["project_root"], exploration_id=arguments.get("direction_exploration_id", ""),
                candidate_id=arguments.get("direction_candidate_id", ""),
            )
        if direction_action == "revise":
            return revise_direction_candidate(
                arguments["project_root"], exploration_id=arguments.get("direction_exploration_id", ""),
                candidate_id=arguments.get("direction_candidate_id", ""),
                candidate=arguments.get("direction_revised_candidate") or {},
                selected_by=arguments.get("direction_selected_by", ""),
                change_summary=arguments.get("direction_change_summary", ""),
            )
        if direction_action == "finalize":
            return finalize_direction_choices(
                arguments["project_root"], exploration_id=arguments.get("direction_exploration_id", ""),
                choice_ids=arguments.get("direction_choice_ids") or [],
                selected_by=arguments.get("direction_selected_by", ""),
                selection_rationale=arguments.get("direction_selection_rationale", ""),
            )
        if direction_action == "status":
            return direction_exploration_status(
                arguments["project_root"], arguments.get("direction_exploration_id"),
            )
        if direction_action == "verify":
            return verify_direction_exploration(
                arguments["project_root"], arguments.get("direction_exploration_id", ""),
            )
        if resource_plan_action == "inventory":
            return inventory_resources(arguments["project_root"])
        if resource_plan_action == "plan":
            return plan_resource_tasks(
                arguments["project_root"], plan_id=arguments.get("resource_plan_id", ""),
                task_goal=arguments.get("resource_task_goal", ""),
                tasks=arguments.get("resource_tasks") or [],
                constraints=arguments.get("resource_constraints"),
                selected_by=arguments.get("resource_selected_by", ""),
            )
        if resource_plan_action == "record":
            return record_resource_task(
                arguments["project_root"], plan_id=arguments.get("resource_plan_id", ""),
                task_id=arguments.get("resource_task_id", ""),
                task_status=arguments.get("resource_task_status", ""),
                artifacts=arguments.get("resource_task_artifacts"),
                observation=arguments.get("resource_observation"),
                note=arguments.get("resource_task_note"),
            )
        if resource_plan_action == "execute":
            return execute_resource_task(
                arguments["project_root"], plan_id=arguments.get("resource_plan_id", ""),
                task_id=arguments.get("resource_task_id", ""),
                process_timeout_seconds=float(arguments.get("process_timeout_seconds", 1800)),
            )
        if resource_plan_action == "status":
            return resource_task_plan_status(arguments["project_root"], arguments.get("resource_plan_id"))
        if resource_plan_action == "verify":
            return verify_resource_task_plan(arguments["project_root"], arguments.get("resource_plan_id", ""))
        if delegation_action == "plan":
            return plan_llm_assistance(
                arguments["project_root"], task_id=arguments.get("delegation_task_id", ""),
                task_type=arguments.get("delegation_task_type", ""),
                task_summary=arguments.get("delegation_task_summary", ""),
                selected_by=arguments.get("delegation_selected_by", ""),
                subagent_available=arguments.get("subagent_available"),
                external_requirement=arguments.get("external_requirement", "none"),
                requested_provider=arguments.get("requested_provider"),
                external_selected_by=arguments.get("external_selected_by"),
                external_rationale=arguments.get("external_rationale"),
            )
        if delegation_action == "submit":
            return submit_llm_assistance(
                arguments["project_root"], task_id=arguments.get("delegation_task_id", ""),
                execution_mode=arguments.get("delegation_execution_mode", ""),
                artifact_path=arguments.get("delegation_artifact_path", ""),
                executor_id=arguments.get("delegation_executor_id", ""),
                model_tier=arguments.get("delegation_model_tier"),
                reasoning_effort=arguments.get("delegation_reasoning_effort"),
                escalation_rationale=arguments.get("delegation_escalation_rationale"),
                provider_model_id=arguments.get("delegation_provider_model_id"),
            )
        if delegation_action == "status":
            return llm_assistance_status(arguments["project_root"], arguments.get("delegation_task_id"))
        if delegation_action == "verify":
            return verify_llm_assistance(arguments["project_root"], arguments.get("delegation_task_id"))
        if metrics_action == "plan":
            return register_metric_plan(
                arguments["project_root"], arguments.get("metric_plan") or {},
                selected_by=arguments.get("metrics_selected_by", ""),
            )
        if metrics_action == "analyze":
            return analyze_metrics(
                arguments["project_root"], data_path=arguments.get("metrics_data_path", ""),
                analysis_id=arguments.get("analysis_id", ""),
                baseline_configuration=arguments.get("baseline_configuration"),
            )
        if metrics_action == "optimize":
            return optimize_metrics(
                arguments["project_root"], analysis_id=arguments.get("analysis_id", ""),
                optimization_id=arguments.get("optimization_id", ""),
                objectives=arguments.get("objectives") or [],
                constraints=arguments.get("metric_constraints") or [],
                weights=arguments.get("objective_weights"),
                reference_scales=arguments.get("reference_scales"),
                selected_by=arguments.get("optimization_selected_by"),
            )
        if metrics_action in {"status", "verify"}:
            return metric_status(arguments["project_root"], verify=metrics_action == "verify")
        if dependency_action == "inventory":
            return dependency_inventory()
        if dependency_action == "need":
            return dependency_need(arguments.get("dependency_component", ""))
        if dependency_action in {"reuse", "install", "not_now"} and arguments.get("dependency_selected_by") != "user":
            raise DependencyError(
                "DEPENDENCY_USER_SELECTION_REQUIRED",
                "dependency_selected_by=user is required after the user explicitly chooses reuse, install, or not_now",
            )
        if dependency_action == "reuse":
            return dependency_decide([], [arguments.get("dependency_component", "")])
        if dependency_action == "install":
            return dependency_decide([arguments.get("dependency_component", "")], [])
        if dependency_action == "not_now":
            return dependency_decline(arguments.get("dependency_component", ""))
        if discipline_action == "analyze":
            return analyze_discipline(
                arguments["project_root"], request_text=arguments.get("request_text", ""),
                discipline=arguments.get("discipline"), broad_domain=arguments.get("discipline_broad_domain"),
                selected_by=arguments.get("discipline_selected_by", ""),
                selection_rationale=arguments.get("discipline_selection_rationale", ""),
            )
        if discipline_action == "initialize":
            return initialize_discipline(
                arguments["project_root"], discipline=arguments.get("discipline", ""),
                request_text=arguments.get("request_text", ""),
                broad_domain=arguments.get("discipline_broad_domain"),
                selected_by=arguments.get("discipline_selected_by", ""),
                selection_rationale=arguments.get("discipline_selection_rationale", ""),
                force=bool(arguments.get("force", False)),
                attempt_timeout_seconds=float(arguments.get("attempt_timeout_seconds", 30)),
            )
        if discipline_action in {"status", "verify"}:
            return discipline_status(
                arguments["project_root"], discipline=arguments.get("discipline"),
                verify=discipline_action == "verify",
            )
        if integrity_action == "preregister":
            return register_preregistration(
                arguments["project_root"], arguments.get("prereg_id", ""), arguments.get("protocol") or {},
                selected_by=arguments.get("selected_by", ""),
            )
        if integrity_action == "record_deviation":
            return record_preregistration_deviation(
                arguments["project_root"], arguments.get("prereg_id", ""), arguments.get("deviation") or {},
                selected_by=arguments.get("selected_by", ""),
            )
        if integrity_action == "repro_plan":
            return register_reproducibility_plan(
                arguments["project_root"], arguments.get("run_id", ""),
                arguments.get("reproducibility_plan") or {}, selected_by=arguments.get("selected_by", ""),
            )
        if integrity_action == "repro_execute":
            return execute_reproducibility(
                arguments["project_root"], arguments.get("run_id", ""),
                timeout=float(arguments.get("process_timeout_seconds", 1800)),
            )
        if integrity_action == "repro_submit":
            return submit_reproducibility_result(
                arguments["project_root"], arguments.get("run_id", ""),
                arguments.get("reproducibility_result") or {},
            )
        if integrity_action == "review_rank":
            return rank_systematic_review(
                arguments["project_root"], arguments.get("review_id", ""), arguments.get("records") or [],
            )
        if integrity_action == "status":
            return integrity_status(
                arguments["project_root"], arguments.get("integrity_component"), arguments.get("identifier"),
            )
        if knowledge_action == "sync":
            return sync_knowledge(arguments["project_root"])
        if knowledge_action == "register":
            return register_knowledge(arguments["project_root"], arguments.get("nodes") or [], arguments.get("edges"))
        if knowledge_action == "search":
            return search_knowledge(arguments["project_root"], arguments.get("query", ""), arguments.get("limit", 10))
        if knowledge_action == "status":
            return knowledge_status(arguments["project_root"])
        if frontier_skill_action == "plan":
            return plan_frontier_skill_research(
                arguments["project_root"], protocol_id=arguments.get("frontier_protocol_id", ""),
                protocol=arguments.get("frontier_protocol") or {},
                selected_by=arguments.get("frontier_selected_by", ""),
                selection_rationale=arguments.get("frontier_selection_rationale", ""),
            )
        if frontier_skill_action == "record_source":
            return record_frontier_skill_source(
                arguments["project_root"], protocol_id=arguments.get("frontier_protocol_id", ""),
                source=arguments.get("frontier_source") or {},
            )
        if frontier_skill_action == "register_hypothesis":
            return register_frontier_skill_hypothesis(
                arguments["project_root"], protocol_id=arguments.get("frontier_protocol_id", ""),
                hypothesis=arguments.get("frontier_hypothesis") or {},
            )
        if frontier_skill_action == "record_trial":
            return record_frontier_skill_trial(
                arguments["project_root"], protocol_id=arguments.get("frontier_protocol_id", ""),
                trial_path=arguments.get("frontier_trial_path", ""),
            )
        if frontier_skill_action == "finalize":
            return finalize_frontier_skill_research(
                arguments["project_root"], protocol_id=arguments.get("frontier_protocol_id", ""),
            )
        if frontier_skill_action == "status":
            return frontier_skill_research_status(
                arguments["project_root"], arguments.get("frontier_protocol_id", ""),
            )
        if frontier_skill_action == "verify":
            return verify_frontier_skill_research(
                arguments["project_root"], arguments.get("frontier_protocol_id", ""),
            )
        if skill_portability_action == "plan":
            return plan_skill_portability(
                arguments["project_root"], portability_id=arguments.get("skill_portability_id", ""),
                protocol=arguments.get("skill_portability_protocol") or {},
                selected_by=arguments.get("skill_portability_selected_by", ""),
                selection_rationale=arguments.get("skill_portability_selection_rationale", ""),
            )
        if skill_portability_action == "record_source":
            return record_skill_portability_source(
                arguments["project_root"], portability_id=arguments.get("skill_portability_id", ""),
                source=arguments.get("skill_portability_source") or {},
            )
        if skill_portability_action == "record_trial":
            return record_skill_portability_trial(
                arguments["project_root"], portability_id=arguments.get("skill_portability_id", ""),
                trial_path=arguments.get("skill_portability_trial_path", ""),
            )
        if skill_portability_action == "finalize":
            return finalize_skill_portability(
                arguments["project_root"], portability_id=arguments.get("skill_portability_id", ""),
            )
        if skill_portability_action == "status":
            return skill_portability_status(
                arguments["project_root"], arguments.get("skill_portability_id", ""),
            )
        if skill_portability_action == "verify":
            return verify_skill_portability(
                arguments["project_root"], arguments.get("skill_portability_id", ""),
            )
        if skill_composition_action == "plan":
            return plan_skill_composition(
                arguments["project_root"], composition_id=arguments.get("skill_composition_id", ""),
                protocol=arguments.get("skill_composition_protocol") or {},
                selected_by=arguments.get("skill_composition_selected_by", ""),
                selection_rationale=arguments.get("skill_composition_selection_rationale", ""),
            )
        if skill_composition_action == "record_source":
            return record_skill_composition_source(
                arguments["project_root"], composition_id=arguments.get("skill_composition_id", ""),
                source=arguments.get("skill_composition_source") or {},
            )
        if skill_composition_action == "record_trial":
            return record_skill_composition_trial(
                arguments["project_root"], composition_id=arguments.get("skill_composition_id", ""),
                trial_path=arguments.get("skill_composition_trial_path", ""),
            )
        if skill_composition_action == "finalize":
            return finalize_skill_composition(
                arguments["project_root"], composition_id=arguments.get("skill_composition_id", ""),
            )
        if skill_composition_action == "status":
            return skill_composition_status(
                arguments["project_root"], arguments.get("skill_composition_id", ""),
            )
        if skill_composition_action == "verify":
            return verify_skill_composition(
                arguments["project_root"], arguments.get("skill_composition_id", ""),
            )
        if domain_skill_action == "discover":
            return discover_domain_skills(arguments.get("query", ""), arguments.get("limit", 10))
        if domain_skill_action == "stage":
            return stage_domain_skill(
                arguments["project_root"], arguments.get("repository", ""), arguments.get("skill_id", ""),
                arguments.get("skill_path"),
            )
        if domain_skill_action == "scan":
            return scan_domain_skill(arguments["project_root"], arguments.get("skill_id", ""), arguments.get("commit"))
        if domain_skill_action == "optimize":
            return optimize_domain_skill(
                arguments["project_root"], arguments.get("skill_id", ""), arguments.get("query", ""),
                rounds=arguments.get("rounds", 3), positive_prompts=arguments.get("positive_prompts"),
                negative_prompts=arguments.get("negative_prompts"),
            )
        if domain_skill_action == "admit":
            return admit_domain_skill(
                arguments["project_root"], arguments.get("skill_id", ""),
                arguments.get("overlap_decision", ""), arguments.get("canonical_owner", ""),
                arguments.get("frontier_protocol_id"),
            )
        if domain_skill_action == "status":
            return domain_skill_status(arguments["project_root"])
        if artifact_action == "plan":
            return plan_research_artifact(
                arguments["project_root"], arguments.get("artifact_type", ""), arguments.get("artifact_id", ""),
                arguments.get("source_files"), arguments.get("protocol"),
            )
        if artifact_action == "submit":
            return submit_research_artifact(
                arguments["project_root"], arguments.get("artifact_id", ""), arguments.get("plan_hash", ""),
                arguments.get("artifact") or {},
            )
        if artifact_action in {"status", "verify"}:
            return research_artifact_status(
                arguments["project_root"], arguments.get("artifact_id", ""), verify=artifact_action == "verify",
            )
        if evolution_action == "record":
            return record_evolution_observation(
                arguments["project_root"], arguments.get("category", ""), arguments.get("component", ""),
                arguments.get("expected", ""), arguments.get("observed", ""), arguments.get("evidence_urls"),
                arguments.get("evidence_hash"),
            )
        if evolution_action == "propose":
            return propose_evolution(arguments["project_root"], arguments.get("component", ""))
        if evolution_action == "status":
            return evolution_status(arguments["project_root"])
        if action == "plan_ideation":
            return plan_ideation(
                arguments["project_root"], request_text=arguments.get("request_text", ""),
                problem=arguments.get("problem", ""), constraints=arguments.get("constraints"),
            )
        if action == "register_candidates":
            return register_candidates(
                arguments["project_root"], plan_hash=arguments.get("plan_hash", ""),
                candidates=arguments.get("candidates") or [],
            )
        if action == "commit_candidate":
            return commit_candidate(
                arguments["project_root"], candidate_id=arguments.get("candidate_id", ""),
                selected_by=arguments.get("selected_by", ""), method=arguments.get("method") or {},
            )
        if action == "plan_strategy":
            return plan_strategy(arguments["project_root"], request_text=arguments.get("request_text", ""))
        if action == "register_strategy":
            return register_strategy(
                arguments["project_root"], strategy_plan_hash=arguments.get("strategy_plan_hash", ""),
                strategy=arguments.get("strategy") or {},
            )
        if action == "decide_strategy_branch":
            return decide_strategy_branch(
                arguments["project_root"], decision_id=arguments.get("decision_id", ""),
                branch_id=arguments.get("branch_id", ""), selected_by=arguments.get("selected_by", ""),
                rationale=arguments.get("rationale", ""),
            )
        if action == "register_hypothesis":
            return register_hypothesis(arguments["project_root"], arguments.get("hypothesis") or {})
        if action == "register_experiment":
            return register_experiment(arguments["project_root"], arguments.get("experiment") or {})
        if action in {"status", "verify"}:
            return get_research_design_status(arguments["project_root"], verify=action == "verify")
    if name == "language_assist":
        action = arguments["action"]
        spine_action = arguments.get("spine_action")
        if spine_action == "plan":
            return plan_paper_spine(
                arguments["project_root"], spine_id=arguments.get("spine_id", ""),
                request_text=arguments.get("request_text", ""),
                local_observation=arguments.get("spine_observation", ""),
                domain_scope=arguments.get("spine_domain_scope", ""),
            )
        if spine_action == "register":
            return register_paper_spine(
                arguments["project_root"], spine_id=arguments.get("spine_id", ""),
                plan_hash=arguments.get("spine_plan_hash", ""), spine=arguments.get("spine") or {},
                selected_by=arguments.get("spine_selected_by", "main_agent"),
            )
        if spine_action == "bind_collision":
            return bind_paper_spine_collision(
                arguments["project_root"], spine_id=arguments.get("spine_id", ""),
            )
        if spine_action == "status":
            return get_paper_spine_status(arguments["project_root"], spine_id=arguments.get("spine_id"))
        if spine_action == "verify":
            return verify_paper_spine(arguments["project_root"], spine_id=arguments.get("spine_id"))
        venue_action = arguments.get("venue_action")
        if venue_action == "list":
            return list_venue_profiles(arguments["project_root"])
        if venue_action == "resolve":
            return resolve_venue_profile(
                arguments["project_root"], arguments.get("venue", ""), arguments.get("venue_year"),
                arguments.get("venue_track", "main"), arguments.get("venue_stage", "submission"),
            )
        if venue_action == "register":
            return register_venue_profile(arguments["project_root"], arguments.get("venue_profile") or {})
        if venue_action == "status":
            return get_venue_status(arguments["project_root"])
        if venue_action == "verify":
            return verify_venue_receipt(arguments["project_root"], arguments.get("venue_receipt_sha256"))
        if action == "plan":
            return plan_language_review(
                arguments["project_root"], arguments.get("request_text", ""),
                manuscript_files=arguments.get("manuscript_files"), draft_text=arguments.get("draft_text"),
                claim_ids=arguments.get("claim_ids"), protected_spans=arguments.get("protected_spans"),
                section=arguments.get("section"), discipline=arguments.get("discipline"),
                venue=arguments.get("venue"), language=arguments.get("language"),
                task_mode=arguments.get("task_mode", "academic_polish"),
                source_text=arguments.get("source_text"),
                source_language=arguments.get("source_language"), target_language=arguments.get("target_language"),
                terminology=arguments.get("terminology"), venue_contract=arguments.get("venue_contract"),
                venue_year=arguments.get("venue_year"), venue_track=arguments.get("venue_track", "main"),
                venue_stage=arguments.get("venue_stage", "submission"),
                venue_receipt_sha256=arguments.get("venue_receipt_sha256"),
            )
        if action == "analyze":
            return analyze_language(
                arguments["project_root"], draft_text=arguments.get("draft_text"),
                source_text=arguments.get("source_text"),
            )
        if action == "register_card":
            return register_rhetorical_card(arguments["project_root"], arguments.get("card") or {})
        if action == "retrieve":
            return retrieve_rhetorical_cards(
                arguments["project_root"], arguments.get("query", ""),
                discipline=arguments.get("discipline"), venue=arguments.get("venue"),
                section=arguments.get("section"), paragraph_role=arguments.get("paragraph_role"),
                evidence_type=arguments.get("evidence_type"), limit=arguments.get("limit", 3),
            )
        if action == "resolve":
            return resolve_language_issues(
                arguments["project_root"], arguments.get("resolutions") or [],
                decisions=arguments.get("decisions"),
            )
        if action == "finalize":
            return finalize_language_review(arguments["project_root"])
        if action == "status":
            return get_language_status(arguments["project_root"])
        if action == "verify":
            return verify_language_receipt(arguments["project_root"])
    raise GuardError(f"Unknown tool: {name}")


def response(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def handle(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    request_id = message.get("id")
    if method == "initialize":
        requested = message.get("params", {}).get("protocolVersion", "2025-03-26")
        return response(request_id, {
            "protocolVersion": requested,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "research-guard", "version": "0.7.0"},
        })
    if method in ("notifications/initialized", "notifications/cancelled"):
        return None
    if method == "ping":
        return response(request_id, {})
    if method == "tools/list":
        return response(request_id, {"tools": TOOLS})
    if method == "tools/call":
        params = message.get("params", {})
        try:
            dependency_state = dependency_inventory()
            if dependency_state["first_load_pending"]:
                if params.get("name") == "list_sources":
                    # The first read-only path exposes onboarding information,
                    # but optional choices no longer block core research work.
                    value = {
                        "selection_required": False,
                        "optional_selection_mode": "on-demand",
                        "core_work_allowed": True,
                        "dependency_inventory": dependency_state,
                        "sources": dispatch("list_sources", params.get("arguments") or {}),
                    }
                    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
                    return response(request_id, {
                        "content": [{"type": "text", "text": text}],
                        "structuredContent": value, "isError": False,
                    })
            value = dispatch(params.get("name", ""), params.get("arguments") or {})
            text = json.dumps(value, ensure_ascii=False, sort_keys=True)
            return response(request_id, {"content": [{"type": "text", "text": text}], "structuredContent": value, "isError": False})
        except Exception as exc:
            error = {
                "error": exc.code if isinstance(exc, DependencyError) else type(exc).__name__,
                "message": str(exc),
            }
            return response(request_id, {
                "content": [{"type": "text", "text": json.dumps(error, ensure_ascii=False)}],
                "structuredContent": error, "isError": True,
            })
    if request_id is None:
        return None
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}


def main() -> int:
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            outgoing = handle(json.loads(raw))
        except Exception as exc:
            traceback.print_exc(file=sys.stderr)
            outgoing = {"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": str(exc)}}
        if outgoing is not None:
            sys.stdout.write(json.dumps(outgoing, ensure_ascii=False, separators=(",", ":")) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
