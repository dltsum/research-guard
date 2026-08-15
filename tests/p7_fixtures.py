from __future__ import annotations

import sys
from pathlib import Path


PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))


def candidate() -> dict:
    return {
        "candidate_id": "I1",
        "title": "Boundary-separated adaptation",
        "problem": "Boundary detection and adaptation are confounded.",
        "mechanism": "A detector gates a separate low-rank update.",
        "falsifier": "Matched controls show no boundary-specific effect.",
        "minimum_viable_experiment": "Compare gated and ungated updates on two shifts.",
        "differentiator": "Separates boundary detection from adaptation.",
        "feasibility": "Uses existing data and bounded compute.",
        "lens_id": "boundary_probe",
        "prior_work": [],
    }


def commit(root: Path) -> dict:
    from research_design_core import commit_candidate, plan_ideation, register_candidates

    plan = plan_ideation(
        root,
        request_text="Design a bounded boundary-specific mechanism",
        problem="Boundary detection and adaptation are confounded.",
    )
    item = candidate()
    register_candidates(root, plan_hash=plan["plan_hash"], candidates=[item])
    return commit_candidate(
        root,
        candidate_id="I1",
        selected_by="user",
        method={key: item[key] for key in ("title", "problem", "mechanism")},
    )


def plan_strategy(root: Path, request: str | None = None) -> dict:
    from research_design_core import plan_strategy as implementation

    return implementation(
        root,
        request_text=request or (
            "Define success and stakeholder criteria, audit assumptions and risk, map fixed and floating parameters, "
            "build a go/no-go decision tree, prepare adversity fallbacks, and invert the problem if blocked"
        ),
    )


def strategy() -> dict:
    return {
        "defined_by": "user",
        "objective": {
            "framework": "method-development",
            "success_definition": "Reduce cross-regime interference without increasing matched compute.",
            "stakeholders": ["researchers deploying models across declared distribution boundaries"],
            "time_horizon": "the registered confirmatory experiment",
            "criteria": [{
                "criterion_id": "C1",
                "name": "boundary robustness",
                "definition": "A prespecified reduction in cross-regime loss at matched compute.",
                "priority": "primary",
                "priority_source": "user",
            }],
            "literature_benchmarks": [{
                "title": "Primary boundary-method record",
                "url": "https://doi.org/10.1000/boundary",
            }],
        },
        "assumptions": [{
            "assumption_id": "A1",
            "type": "technical",
            "statement": "The detector identifies the prespecified boundary above chance.",
            "epistemic_status": "evidence_supported",
            "evidence_items": [{
                "title": "Primary detector validation",
                "url": "https://doi.org/10.1000/detector",
            }],
            "validation_test": "Evaluate on a frozen labelled boundary set.",
            "pass_criterion": "Meet the user-prespecified discrimination interval.",
            "failure_response": "Do not interpret the adaptation comparison as a mechanism test.",
            "depends_on": [],
            "likelihood": {
                "label": "uncertain",
                "selected_by": "user",
                "rationale": "The user treats the prior evidence as adjacent rather than system-matched.",
            },
        }],
        "parameters": [{
            "parameter_id": "P1",
            "category": "method",
            "value": "detector-gated low-rank update",
            "status": "fixed",
            "rationale": "This is the user-selected mechanism being tested.",
            "reconsider_when": "The detector fails criterion C1's prerequisite checks.",
            "set_by": "user",
        }],
        "decisions": [{
            "decision_id": "D1",
            "question": "Does the detector pass its frozen validation test?",
            "trigger": "Detector validation completes.",
            "evidence_needed": ["Frozen validation output and uncertainty interval"],
            "requires_current_choice": True,
            "branches": [
                {
                    "branch_id": "B_continue",
                    "label": "continue registered method",
                    "condition": "The user judges the prespecified detector criterion met.",
                    "action": "Proceed to the matched adaptation comparison.",
                    "changes_method": False,
                    "assumption_ids": ["A1"],
                    "parameter_ids": ["P1"],
                },
                {
                    "branch_id": "B_change",
                    "label": "replace detector",
                    "condition": "The user judges the prespecified detector criterion unmet.",
                    "action": "Revise the detector and register the complete adjusted method.",
                    "changes_method": True,
                    "assumption_ids": ["A1"],
                    "parameter_ids": ["P1"],
                },
            ],
        }],
        "adversities": [{
            "scenario_id": "V1",
            "trigger": "The detector fails on a prespecified subgroup.",
            "assumption_ids": ["A1"],
            "mitigation": "Measure the subgroup boundary before changing the mechanism.",
            "residual_risk": "The available labels may not identify the failure mechanism.",
            "fallback_branch_id": "B_change",
        }],
        "inversions": [{
            "inversion_id": "I1",
            "kind": "unfix_parameter",
            "current_constraint": "The current detector form is treated as fixed.",
            "parameter_ids": ["P1"],
            "alternative_question_or_goal": "Which detector family best isolates the same registered boundary?",
            "evidence_needed": "A matched detector-only comparison.",
            "branch_id": "B_change",
        }],
    }


def hypothesis() -> dict:
    return {
        "hypothesis_id": "H1",
        "status": "candidate",
        "observation": {"statement": "Ungated updates degrade after a shift.", "provenance": "Frozen pilot log."},
        "research_question": "Does gated adaptation reduce interference?",
        "statement": "Gating reduces cross-regime interference.",
        "mechanism": "The gate isolates regime-specific gradients.",
        "rivals": [{"rival_id": "H2", "statement": "Only update magnitude matters.", "mechanism": "Gating lowers update norm."}],
        "predictions": [{
            "prediction_id": "PR1", "statement": "Gating wins at matched norm.",
            "observable": "Cross-regime loss", "expected_pattern": "Lower loss change",
            "falsifier": "No difference at matched norm", "discriminates_against": ["H2"],
        }],
        "operationalizations": [{
            "construct": "interference", "variable": "delta_loss", "role": "primary_outcome",
            "definition": "Held-out loss change", "measurement_method": "Frozen evaluator",
            "unit": "loss units", "timing": "After each update block",
        }],
        "evidence_boundary": "Pilot evidence is motivating only.",
        "literature_items": [],
    }


def experiment() -> dict:
    return {
        "experiment_id": "E1",
        "design_type": "randomized computational experiment",
        "claims_tested": ["PR1"],
        "experimental_unit": "independent seeded run",
        "analysis_unit": "independent seeded run",
        "independence_justification": "Seeds, initialization, and data order are independent.",
        "assignment": "Use a frozen balanced seeded schedule.",
        "controls": ["matched compute", "matched update norm"],
        "primary_outcomes": ["delta_loss"],
        "estimand": "Mean gated-minus-ungated loss change.",
        "power": {
            "mode": "simulation", "basis": "User-declared minimum relevant effect.",
            "target_power_or_precision": "Prespecified interval precision.",
            "sample_size": "Selected by blinded simulation.",
            "sensitivity_plan": "Vary plausible variance and attrition.",
        },
        "missing_data_plan": "Report failed runs and prespecified exclusions.",
        "multiplicity_plan": "One confirmatory outcome; others exploratory.",
        "stopping_rule": "Stop at the frozen run count or a declared resource block.",
        "success_criteria": "The prespecified interval criterion is met.",
        "failure_interpretation": "Separate mechanism evidence from imprecision and implementation failure.",
        "run_order": [{"run_id": "R1", "purpose": "Primary comparison", "priority": "must_run", "stop_go": "Run after detector checks."}],
        "ablations": [],
        "ablation_not_applicable_reason": "The strategy gate precedes component ablations.",
        "ethics_and_feasibility": {"status": "cleared", "required_reviews": [], "unresolved_blocks": []},
    }
