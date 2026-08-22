from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path
from typing import Any


IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,79}$")
PARAMETER = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
CONFUSING_PARAMETERS = {"I", "O", "l"}
RELATIONS = {"<=", "<", "==", ">=", ">"}


class ConstructionError(ValueError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _text(value: Any, field: str, *, minimum: int = 1) -> str:
    result = " ".join(str(value or "").split())
    if len(result) < minimum:
        raise ConstructionError(f"{field} must contain at least {minimum} characters")
    return result


def _fraction(value: Any, field: str) -> Fraction:
    if isinstance(value, bool) or value is None:
        raise ConstructionError(f"{field} must be an exact integer, decimal, or rational string")
    if isinstance(value, int):
        return Fraction(value)
    raw = str(value).strip()
    try:
        if "/" in raw:
            if raw.count("/") != 1:
                raise ValueError
            numerator, denominator = raw.split("/", 1)
            return Fraction(int(numerator.strip()), int(denominator.strip()))
        return Fraction(Decimal(raw))
    except (InvalidOperation, ValueError, ZeroDivisionError) as exc:
        raise ConstructionError(f"{field} is not an exact finite rational value") from exc


def _exact(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def _decimal(value: Fraction, places: int = 12) -> str:
    context_value = Decimal(value.numerator) / Decimal(value.denominator)
    rendered = format(context_value, f".{places}g")
    return rendered.replace("E", "e")


def _z3_number(value: Fraction, z3: Any) -> Any:
    return z3.RealVal(_exact(value))


def _z3_fraction(value: Any, z3: Any) -> Fraction:
    if z3.is_int_value(value):
        return Fraction(value.as_long())
    if z3.is_rational_value(value):
        return Fraction(value.numerator_as_long(), value.denominator_as_long())
    raise ConstructionError(f"Z3 returned a non-rational linear model value: {value}")


def _relation(lhs: Any, relation: str, rhs: Any) -> Any:
    if relation == "<=":
        return lhs <= rhs
    if relation == "<":
        return lhs < rhs
    if relation == "==":
        return lhs == rhs
    if relation == ">=":
        return lhs >= rhs
    if relation == ">":
        return lhs > rhs
    raise ConstructionError(f"unsupported relation: {relation}")


def _normalize_manifest(manifest: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    allowed_manifest = {"audit_id", "protocol_id", "source", "variables", "constraints", "anchor_count", "notes"}
    if set(manifest) - allowed_manifest:
        raise ConstructionError(f"unknown constructive numerical fields: {sorted(set(manifest) - allowed_manifest)}")
    audit_id = str(manifest.get("audit_id") or "").strip()
    if not IDENTIFIER.fullmatch(audit_id):
        raise ConstructionError("audit_id is invalid")
    protocol_id = _text(manifest.get("protocol_id"), "protocol_id", minimum=3)
    protocol_source = _text(manifest.get("source"), "source", minimum=3)
    anchor_count = manifest.get("anchor_count", 3)
    if not isinstance(anchor_count, int) or isinstance(anchor_count, bool) or not 1 <= anchor_count <= 5:
        raise ConstructionError("anchor_count must be an integer from 1 to 5")
    raw_variables = manifest.get("variables")
    raw_constraints = manifest.get("constraints")
    if not isinstance(raw_variables, list) or not 1 <= len(raw_variables) <= 32:
        raise ConstructionError("variables must contain 1-32 parameter declarations")
    if not isinstance(raw_constraints, list) or not 1 <= len(raw_constraints) <= 64:
        raise ConstructionError("constraints must contain 1-64 linear relations")

    from pint import UnitRegistry
    from pint.errors import PintError

    registry = UnitRegistry(non_int_type=Decimal)
    variables: list[dict[str, Any]] = []
    variable_map: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(raw_variables):
        allowed = {
            "name", "type", "unit", "minimum", "maximum", "minimum_inclusive",
            "maximum_inclusive", "source", "purpose",
        }
        if not isinstance(raw, dict) or set(raw) - allowed:
            raise ConstructionError(f"variables[{index}] has unknown or invalid fields")
        name = str(raw.get("name") or "").strip()
        kind = str(raw.get("type") or "").strip().lower()
        if not PARAMETER.fullmatch(name) or name in CONFUSING_PARAMETERS or name in variable_map:
            raise ConstructionError(f"variables[{index}] has an illegal, confusing, or duplicate name")
        if kind not in {"real", "integer"}:
            raise ConstructionError(f"variable {name} type must be real or integer")
        unit = _text(raw.get("unit"), f"variable {name} unit")
        try:
            parsed_unit = registry.parse_units(unit)
        except (PintError, ValueError, TypeError) as exc:
            raise ConstructionError(f"variable {name} has an invalid Pint unit: {exc}") from exc
        lower = _fraction(raw["minimum"], f"variable {name} minimum") if "minimum" in raw else None
        upper = _fraction(raw["maximum"], f"variable {name} maximum") if "maximum" in raw else None
        lower_inclusive = raw.get("minimum_inclusive", True)
        upper_inclusive = raw.get("maximum_inclusive", True)
        if not isinstance(lower_inclusive, bool) or not isinstance(upper_inclusive, bool):
            raise ConstructionError(f"variable {name} bound inclusivity must be boolean")
        if lower is None and "minimum_inclusive" in raw:
            raise ConstructionError(f"variable {name} minimum_inclusive has no minimum")
        if upper is None and "maximum_inclusive" in raw:
            raise ConstructionError(f"variable {name} maximum_inclusive has no maximum")
        record = {
            "name": name,
            "type": kind,
            "unit": str(parsed_unit),
            "dimensionality": str(parsed_unit.dimensionality),
            "minimum": _exact(lower) if lower is not None else None,
            "maximum": _exact(upper) if upper is not None else None,
            "minimum_inclusive": lower_inclusive if lower is not None else None,
            "maximum_inclusive": upper_inclusive if upper is not None else None,
            "source": _text(raw.get("source"), f"variable {name} source", minimum=3),
            "purpose": _text(raw.get("purpose"), f"variable {name} purpose", minimum=6),
            "_unit": parsed_unit,
            "_lower": lower,
            "_upper": upper,
        }
        variables.append(record)
        variable_map[name] = record

    constraints: list[dict[str, Any]] = []
    pint_checks: list[dict[str, Any]] = []
    seen_constraints: set[str] = set()
    used_variables: set[str] = set()
    for index, raw in enumerate(raw_constraints):
        if not isinstance(raw, dict) or set(raw) - {"id", "source", "relation", "terms", "rhs", "description"}:
            raise ConstructionError(f"constraints[{index}] has unknown or invalid fields")
        identifier = str(raw.get("id") or "").strip()
        relation = str(raw.get("relation") or "").strip()
        if not IDENTIFIER.fullmatch(identifier) or identifier in seen_constraints:
            raise ConstructionError(f"constraints[{index}] has an illegal or duplicate id")
        seen_constraints.add(identifier)
        if relation not in RELATIONS:
            raise ConstructionError(f"constraint {identifier} has an unsupported relation")
        terms = raw.get("terms")
        rhs = raw.get("rhs")
        if not isinstance(terms, list) or not 1 <= len(terms) <= 32:
            raise ConstructionError(f"constraint {identifier} needs 1-32 terms")
        if not isinstance(rhs, dict) or set(rhs) != {"value", "unit"}:
            raise ConstructionError(f"constraint {identifier} rhs must contain exactly value and unit")
        rhs_value = _fraction(rhs["value"], f"constraint {identifier} rhs value")
        rhs_unit_text = _text(rhs["unit"], f"constraint {identifier} rhs unit")
        try:
            rhs_unit = registry.parse_units(rhs_unit_text)
        except (PintError, ValueError, TypeError) as exc:
            raise ConstructionError(f"constraint {identifier} has an invalid rhs unit: {exc}") from exc
        normalized_terms: list[dict[str, Any]] = []
        term_variables: set[str] = set()
        dimension_issues: list[str] = []
        for term_index, term in enumerate(terms):
            if not isinstance(term, dict) or set(term) - {"variable", "coefficient", "coefficient_unit"}:
                raise ConstructionError(f"constraint {identifier} term {term_index} is invalid")
            variable = str(term.get("variable") or "").strip()
            if variable not in variable_map or variable in term_variables:
                raise ConstructionError(f"constraint {identifier} has an unknown or duplicate variable term")
            term_variables.add(variable)
            used_variables.add(variable)
            coefficient = _fraction(term.get("coefficient"), f"constraint {identifier} coefficient for {variable}")
            if coefficient == 0:
                raise ConstructionError(f"constraint {identifier} has a zero coefficient for {variable}")
            coefficient_unit_text = str(term.get("coefficient_unit") or "dimensionless").strip()
            try:
                coefficient_unit = registry.parse_units(coefficient_unit_text)
                term_unit = coefficient_unit * variable_map[variable]["_unit"]
                zero = registry.Quantity(Decimal(0), term_unit).to(rhs_unit).magnitude
                one = registry.Quantity(Decimal(1), term_unit).to(rhs_unit).magnitude
                if zero != 0:
                    raise ValueError("affine or offset unit conversions are not legal linear coefficients; use delta units")
                conversion = one - zero
                conversion_fraction = Fraction(conversion)
            except (PintError, ValueError, TypeError) as exc:
                dimension_issues.append(f"{variable}: {exc}")
                conversion_fraction = None
                term_unit = coefficient_unit_text
            normalized_terms.append({
                "variable": variable,
                "coefficient": _exact(coefficient),
                "coefficient_unit": str(coefficient_unit_text),
                "term_unit": str(term_unit),
                "conversion_to_rhs_unit": _exact(conversion_fraction) if conversion_fraction is not None else None,
                "normalized_coefficient": _exact(coefficient * conversion_fraction) if conversion_fraction is not None else None,
                "_coefficient": coefficient * conversion_fraction if conversion_fraction is not None else None,
            })
        check = {
            "id": identifier,
            "source": _text(raw.get("source"), f"constraint {identifier} source", minimum=3),
            "status": "PASS" if not dimension_issues else "FAIL",
            "rhs_unit": str(rhs_unit),
            "rhs_dimensionality": str(rhs_unit.dimensionality),
            "issues": dimension_issues,
        }
        pint_checks.append(check)
        constraints.append({
            "id": identifier,
            "source": check["source"],
            "description": " ".join(str(raw.get("description") or "").split()) or None,
            "relation": relation,
            "terms": normalized_terms,
            "rhs": {"value": _exact(rhs_value), "unit": str(rhs_unit)},
            "_rhs": rhs_value,
        })
    unused = sorted(set(variable_map) - used_variables)
    if unused:
        raise ConstructionError(f"declared variables are not used by any constraint: {', '.join(unused)}")

    public_variables = [{key: value for key, value in item.items() if not key.startswith("_")} for item in variables]
    public_constraints = []
    for item in constraints:
        public_constraints.append({
            **{key: value for key, value in item.items() if not key.startswith("_") and key != "terms"},
            "terms": [{key: value for key, value in term.items() if not key.startswith("_")} for term in item["terms"]],
        })
    public = {
        "audit_id": audit_id,
        "protocol_id": protocol_id,
        "source": protocol_source,
        "anchor_count": anchor_count,
        "variables": public_variables,
        "constraints": public_constraints,
        "notes": " ".join(str(manifest.get("notes") or "").split()) or None,
    }
    internal = {
        "registry": registry,
        "variables": variables,
        "variable_map": variable_map,
        "constraints": constraints,
        "pint_checks": pint_checks,
    }
    return public, internal


def _build_solver(internal: dict[str, Any]) -> tuple[Any, dict[str, Any], list[tuple[str, Any]], Any]:
    import z3

    variables = {
        item["name"]: (z3.Int(item["name"]) if item["type"] == "integer" else z3.Real(item["name"]))
        for item in internal["variables"]
    }
    assertions: list[tuple[str, Any]] = []
    for item in internal["variables"]:
        variable = variables[item["name"]]
        if item["_lower"] is not None:
            rhs = _z3_number(item["_lower"], z3)
            assertions.append((
                f"bound.{item['name']}.minimum",
                variable >= rhs if item["minimum_inclusive"] else variable > rhs,
            ))
        if item["_upper"] is not None:
            rhs = _z3_number(item["_upper"], z3)
            assertions.append((
                f"bound.{item['name']}.maximum",
                variable <= rhs if item["maximum_inclusive"] else variable < rhs,
            ))
    for item in internal["constraints"]:
        lhs = sum(
            (_z3_number(term["_coefficient"], z3) * variables[term["variable"]] for term in item["terms"]),
            _z3_number(Fraction(0), z3),
        )
        assertions.append((f"constraint.{item['id']}", _relation(lhs, item["relation"], _z3_number(item["_rhs"], z3))))
    solver = z3.Solver()
    tracking: dict[str, str] = {}
    for index, (label, assertion) in enumerate(assertions):
        token = z3.Bool(f"rg_track_{index}")
        tracking[str(token)] = label
        solver.assert_and_track(assertion, token)
    return solver, variables, assertions, tracking


def _objective_bound(assertions: list[tuple[str, Any]], variable: Any, *, minimize: bool, z3: Any) -> dict[str, Any]:
    optimizer = z3.Optimize()
    optimizer.add(*[assertion for _, assertion in assertions])
    handle = optimizer.minimize(variable) if minimize else optimizer.maximize(variable)
    if optimizer.check() != z3.sat:
        return {"status": "UNKNOWN", "finite": None, "value": None, "inclusive": None}
    values = handle.lower_values() if minimize else handle.upper_values()
    infinity = _z3_fraction(values[0], z3)
    if infinity != 0:
        return {
            "status": "PASS", "finite": False, "value": None, "inclusive": False,
            "direction": "-infinity" if infinity < 0 else "+infinity",
        }
    base = _z3_fraction(values[1], z3)
    epsilon = _z3_fraction(values[2], z3)
    return {
        "status": "PASS", "finite": True, "value": _exact(base),
        "decimal": _decimal(base), "inclusive": epsilon == 0,
        "epsilon_direction": _exact(epsilon),
    }


def _assignment(model: Any, variables: dict[str, Any], z3: Any) -> dict[str, Fraction]:
    return {
        name: _z3_fraction(model.eval(variable, model_completion=True), z3)
        for name, variable in variables.items()
    }


def _anchor_model(
    assertions: list[tuple[str, Any]], variables: dict[str, Any], targets: dict[str, Fraction], z3: Any,
) -> dict[str, Fraction]:
    optimizer = z3.Optimize()
    optimizer.set(priority="lex")
    optimizer.add(*[assertion for _, assertion in assertions])
    for index, (name, variable) in enumerate(variables.items()):
        deviation = z3.Real(f"rg_anchor_deviation_{index}")
        target = _z3_number(targets[name], z3)
        optimizer.add(deviation >= variable - target, deviation >= target - variable, deviation >= 0)
        optimizer.minimize(deviation)
    if optimizer.check() != z3.sat:
        raise ConstructionError("Z3 could not construct an anchor for a SAT system")
    return _assignment(optimizer.model(), variables, z3)


def _relation_check(lhs: Fraction, relation: str, rhs: Fraction) -> tuple[bool, Fraction]:
    if relation == "<=":
        return lhs <= rhs, rhs - lhs
    if relation == "<":
        return lhs < rhs, rhs - lhs
    if relation == "==":
        return lhs == rhs, -abs(lhs - rhs)
    if relation == ">=":
        return lhs >= rhs, lhs - rhs
    if relation == ">":
        return lhs > rhs, lhs - rhs
    raise ConstructionError(f"unsupported relation: {relation}")


def _float_safety(value: Fraction) -> tuple[bool, str | None]:
    try:
        numeric = float(value)
    except (OverflowError, ValueError):
        return False, "overflow_on_binary64_conversion"
    if not math.isfinite(numeric):
        return False, "non_finite_binary64_conversion"
    if value != 0 and numeric == 0.0:
        return False, "underflow_to_zero_on_binary64_conversion"
    return True, None


def _validate_anchor(
    anchor_id: str, assignment: dict[str, Fraction], internal: dict[str, Any], quantile: Fraction,
) -> dict[str, Any]:
    variable_checks: list[dict[str, Any]] = []
    relation_checks: list[dict[str, Any]] = []
    issues: list[str] = []
    values: dict[str, dict[str, Any]] = {}
    for item in internal["variables"]:
        value = assignment[item["name"]]
        admitted = True
        if item["_lower"] is not None:
            admitted = admitted and (value >= item["_lower"] if item["minimum_inclusive"] else value > item["_lower"])
        if item["_upper"] is not None:
            admitted = admitted and (value <= item["_upper"] if item["maximum_inclusive"] else value < item["_upper"])
        if item["type"] == "integer":
            admitted = admitted and value.denominator == 1
        safe, risk = _float_safety(value)
        if not admitted:
            issues.append(f"{item['name']} violates its declared protocol bounds or type")
        if not safe:
            issues.append(f"{item['name']}: {risk}")
        values[item["name"]] = {
            "exact": _exact(value), "decimal": _decimal(value), "unit": item["unit"],
        }
        variable_checks.append({
            "variable": item["name"], "status": "PASS" if admitted and safe else "FAIL",
            "protocol_admitted": admitted, "binary64_safe": safe, "risk": risk,
        })
    for constraint in internal["constraints"]:
        lhs = sum((term["_coefficient"] * assignment[term["variable"]] for term in constraint["terms"]), Fraction(0))
        passed, slack = _relation_check(lhs, constraint["relation"], constraint["_rhs"])
        if not passed:
            issues.append(f"constraint {constraint['id']} is violated")
        relation_checks.append({
            "constraint_id": constraint["id"], "status": "PASS" if passed else "FAIL",
            "lhs_exact": _exact(lhs), "relation": constraint["relation"],
            "rhs_exact": _exact(constraint["_rhs"]), "slack_exact": _exact(slack),
            "normalized_unit": constraint["rhs"]["unit"], "source": constraint["source"],
        })
    return {
        "anchor_id": anchor_id,
        "target_quantile": _exact(quantile),
        "status": "PASS" if not issues else "FAIL",
        "joint_assignment": values,
        "variable_checks": variable_checks,
        "constraint_checks": relation_checks,
        "issues": issues,
    }


def run(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict) or not isinstance(payload.get("manifest"), dict):
        raise ConstructionError("input must contain a constructive numerical manifest")
    manifest = payload["manifest"]
    manifest_sha256 = hashlib.sha256(_canonical(manifest)).hexdigest()
    public, internal = _normalize_manifest(manifest)
    pint_result = {
        "status": "PASS" if all(item["status"] == "PASS" for item in internal["pint_checks"]) else "FAIL",
        "engine": "Pint",
        "checks": internal["pint_checks"],
    }
    if pint_result["status"] != "PASS":
        return {
            "schema_version": 1,
            "audit_id": public["audit_id"],
            "status": "BLOCKED",
            "manifest_sha256": manifest_sha256,
            "constraint_system": public,
            "results": {
                "dimensional": pint_result,
                "symbolic": {"status": "NOT_RUN", "reason": "dimensional normalization failed"},
                "constraints": {"status": "NOT_RUN", "reason": "dimensional normalization failed"},
                "numerical_protocol": {"status": "NOT_RUN", "reason": "no dimensionally legal system"},
            },
            "marginal_intervals": [],
            "joint_anchors": [],
            "warnings": ["No solver or anchor result is certified after a Pint failure."],
        }

    import sympy
    import z3

    sympy_symbols = {
        item["name"]: sympy.Symbol(item["name"], real=True, integer=item["type"] == "integer")
        for item in internal["variables"]
    }
    symbolic_relations: list[dict[str, Any]] = []
    equality_expressions: list[Any] = []
    for constraint in internal["constraints"]:
        expression = sum(
            (sympy.Rational(term["_coefficient"].numerator, term["_coefficient"].denominator) * sympy_symbols[term["variable"]] for term in constraint["terms"]),
            sympy.Integer(0),
        ) - sympy.Rational(constraint["_rhs"].numerator, constraint["_rhs"].denominator)
        symbolic_relations.append({
            "id": constraint["id"], "source": constraint["source"],
            "normalized_expression": str(expression), "relation_to_zero": constraint["relation"],
        })
        if constraint["relation"] == "==":
            equality_expressions.append(expression)
    symbol_order = [sympy_symbols[item["name"]] for item in internal["variables"]]
    if equality_expressions:
        matrix, vector = sympy.linear_eq_to_matrix(equality_expressions, symbol_order)
        equality_summary = {
            "equation_count": len(equality_expressions),
            "coefficient_rank": int(matrix.rank()),
            "augmented_rank": int(matrix.row_join(vector).rank()),
            "rref": [[str(value) for value in row] for row in matrix.row_join(vector).rref()[0].tolist()],
        }
    else:
        equality_summary = {"equation_count": 0, "coefficient_rank": 0, "augmented_rank": 0, "rref": []}
    symbolic_result = {
        "status": "PASS", "engine": "SymPy", "model_class": "linear_rational",
        "variable_order": [item["name"] for item in internal["variables"]],
        "relations": symbolic_relations, "equality_system": equality_summary,
    }

    solver, variables, assertions, tracking = _build_solver(internal)
    satisfiability = solver.check()
    if satisfiability == z3.unsat:
        core = [tracking.get(str(item), str(item)) for item in solver.unsat_core()]
        z3_result = {
            "status": "FAIL", "engine": "Z3", "satisfiability": "UNSAT",
            "unsat_core": core,
        }
        return {
            "schema_version": 1, "audit_id": public["audit_id"], "status": "BLOCKED",
            "manifest_sha256": manifest_sha256, "constraint_system": public,
            "results": {
                "dimensional": pint_result, "symbolic": symbolic_result,
                "constraints": z3_result,
                "numerical_protocol": {"status": "NOT_RUN", "reason": "the registered system is UNSAT"},
            },
            "marginal_intervals": [], "joint_anchors": [],
            "warnings": ["The UNSAT core is a solver conflict subset, not a scientific diagnosis."],
        }
    if satisfiability != z3.sat:
        return {
            "schema_version": 1, "audit_id": public["audit_id"], "status": "NOT_CERTIFIED",
            "manifest_sha256": manifest_sha256, "constraint_system": public,
            "results": {
                "dimensional": pint_result, "symbolic": symbolic_result,
                "constraints": {"status": "UNKNOWN", "engine": "Z3", "satisfiability": "UNKNOWN"},
                "numerical_protocol": {"status": "NOT_RUN", "reason": "Z3 returned UNKNOWN"},
            },
            "marginal_intervals": [], "joint_anchors": [],
            "warnings": ["No interval or anchor is certified after an UNKNOWN solver result."],
        }

    baseline = _assignment(solver.model(), variables, z3)
    intervals: list[dict[str, Any]] = []
    interval_map: dict[str, dict[str, Any]] = {}
    for item in internal["variables"]:
        lower = _objective_bound(assertions, variables[item["name"]], minimize=True, z3=z3)
        upper = _objective_bound(assertions, variables[item["name"]], minimize=False, z3=z3)
        interval = {
            "variable": item["name"], "type": item["type"], "unit": item["unit"],
            "lower": lower, "upper": upper,
            "semantics": "marginal_projection_subject_to_all_registered_constraints",
        }
        intervals.append(interval)
        interval_map[item["name"]] = interval
    z3_result = {
        "status": "PASS", "engine": "Z3", "satisfiability": "SAT",
        "baseline_model": {name: _exact(value) for name, value in baseline.items()},
        "unsat_core": [],
    }

    requested = public["anchor_count"]
    quantiles = [Fraction(index, requested + 1) for index in range(1, requested + 1)]
    anchors: list[dict[str, Any]] = []
    seen_assignments: set[tuple[tuple[str, str], ...]] = set()
    warnings = [
        "Marginal intervals are projections; their Cartesian product is not guaranteed feasible.",
        "Anchors are deterministic feasible design points, not observations, optima, or recommended scientific settings.",
    ]
    for quantile in quantiles:
        targets: dict[str, Fraction] = {}
        for name in variables:
            interval = interval_map[name]
            lower, upper = interval["lower"], interval["upper"]
            if lower.get("finite") is True and upper.get("finite") is True:
                low = _fraction(lower["value"], f"{name} lower interval")
                high = _fraction(upper["value"], f"{name} upper interval")
                targets[name] = low + quantile * (high - low)
            else:
                targets[name] = baseline[name]
        assignment = _anchor_model(assertions, variables, targets, z3)
        key = tuple((name, _exact(value)) for name, value in assignment.items())
        if key in seen_assignments:
            continue
        seen_assignments.add(key)
        anchors.append(_validate_anchor(f"anchor-{len(anchors) + 1:02d}", assignment, internal, quantile))
    if len(anchors) < requested:
        warnings.append(
            f"Only {len(anchors)} unique joint assignments were produced for {requested} requested anchors; "
            "equalities, integer discreteness, or unbounded projections collapsed targets."
        )
    numerical_status = "PASS" if anchors and all(item["status"] == "PASS" for item in anchors) else "FAIL"
    numerical_result = {
        "status": numerical_status,
        "engine": "exact_rational_anchor_recheck",
        "anchor_count_requested": requested,
        "anchor_count_produced": len(anchors),
        "all_anchors_jointly_checked": bool(anchors),
        "anchors": anchors,
    }
    status = "PASS" if numerical_status == "PASS" else "BLOCKED"
    return {
        "schema_version": 1,
        "audit_id": public["audit_id"],
        "status": status,
        "manifest_sha256": manifest_sha256,
        "constraint_system": public,
        "results": {
            "dimensional": pint_result,
            "symbolic": symbolic_result,
            "constraints": z3_result,
            "numerical_protocol": numerical_result,
        },
        "marginal_intervals": intervals,
        "joint_anchors": anchors,
        "warnings": warnings,
        "scope_boundary": "linear rational registered constraints only; this does not replace Lean theorem checking or execute the manuscript model",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("output")
    arguments = parser.parse_args()
    try:
        payload = json.loads(Path(arguments.input).read_text(encoding="utf-8"))
        result = run(payload)
    except Exception as exc:
        result = {"worker_error": type(exc).__name__, "message": str(exc)}
    Path(arguments.output).write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    return 0 if "worker_error" not in result else 2


if __name__ == "__main__":
    raise SystemExit(main())
