from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import re
import sys
from pathlib import Path
from typing import Any


class VerificationError(ValueError):
    pass


CHANNELS = ("dimensional", "symbolic", "constraints", "numerical_protocol")
SAFE_EXPRESSION = re.compile(r"^[A-Za-z0-9_+\-*/^().,\s]+$")
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _applicability(manifest: dict[str, Any], channel: str) -> tuple[bool, dict[str, Any] | None]:
    value = (manifest.get("applicability") or {}).get(channel)
    if not isinstance(value, dict):
        raise VerificationError(f"applicability.{channel} must be an object")
    status = str(value.get("status") or "").strip().lower()
    if status == "required":
        return True, None
    if status == "not_applicable":
        reason = str(value.get("reason") or "").strip()
        source = str(value.get("source") or "").strip()
        if len(reason) < 20 or not source:
            raise VerificationError(f"applicability.{channel} needs a concrete reason and manuscript source")
        return False, {
            "status": "NOT_APPLICABLE", "reason": reason, "source": source, "checks": [],
        }
    raise VerificationError(f"applicability.{channel}.status must be required or not_applicable")


def _record_status(checks: list[dict[str, Any]]) -> str:
    states = {str(item.get("status")) for item in checks}
    if "FAIL" in states:
        return "FAIL"
    if "UNKNOWN" in states:
        return "UNKNOWN"
    return "PASS" if checks and states == {"PASS"} else "FAIL"


def _dimensional(manifest: dict[str, Any]) -> dict[str, Any]:
    required, omitted = _applicability(manifest, "dimensional")
    if not required:
        return omitted or {}
    from pint import UnitRegistry
    from pint.errors import PintError

    rows = manifest.get("dimensional_checks")
    if not isinstance(rows, list) or not rows:
        return {"status": "FAIL", "checks": [], "reason": "required dimensional_checks are missing"}
    registry = UnitRegistry()
    checks: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise VerificationError(f"dimensional_checks[{index}] must be an object")
        check_id = str(row.get("id") or "").strip()
        source = str(row.get("source") or "").strip()
        lhs = str(row.get("lhs_units") or "").strip()
        rhs = str(row.get("rhs_units") or "").strip()
        if not check_id or check_id in seen or not source or not lhs or not rhs:
            raise VerificationError(f"dimensional_checks[{index}] needs a unique id, source, lhs_units, and rhs_units")
        seen.add(check_id)
        if not SAFE_EXPRESSION.fullmatch(lhs) or not SAFE_EXPRESSION.fullmatch(rhs):
            raise VerificationError(f"dimensional check {check_id} contains unsupported unit syntax")
        try:
            lhs_dim = registry.parse_units(lhs).dimensionality
            rhs_dim = registry.parse_units(rhs).dimensionality
            compatible = lhs_dim == rhs_dim
            checks.append({
                "id": check_id, "source": source, "status": "PASS" if compatible else "FAIL",
                "lhs_units": lhs, "rhs_units": rhs,
                "lhs_dimensionality": str(lhs_dim), "rhs_dimensionality": str(rhs_dim),
            })
        except (PintError, ValueError, TypeError) as exc:
            checks.append({"id": check_id, "source": source, "status": "FAIL", "error": str(exc)})
    return {"status": _record_status(checks), "engine": "Pint", "checks": checks}


def _safe_sympy_expression(expression: str, symbols: dict[str, Any], sympy: Any) -> Any:
    if not expression or not SAFE_EXPRESSION.fullmatch(expression) or "__" in expression or "." in expression:
        raise VerificationError("symbolic expression contains unsupported syntax")
    functions = {
        "Abs": sympy.Abs, "Rational": sympy.Rational, "sqrt": sympy.sqrt,
        "sin": sympy.sin, "cos": sympy.cos, "tan": sympy.tan,
        "exp": sympy.exp, "log": sympy.log, "pi": sympy.pi, "E": sympy.E,
    }
    allowed = set(symbols) | set(functions)
    unknown = sorted(set(IDENTIFIER.findall(expression)) - allowed)
    if unknown:
        raise VerificationError(f"undeclared symbolic identifiers: {', '.join(unknown)}")
    local = {**functions, **symbols}
    safe_globals = {
        "__builtins__": {}, "Integer": sympy.Integer, "Float": sympy.Float,
        "Rational": sympy.Rational, "Symbol": sympy.Symbol,
    }
    from sympy.parsing.sympy_parser import parse_expr
    return parse_expr(expression.replace("^", "**"), local_dict=local, global_dict=safe_globals, evaluate=True)


def _symbolic(manifest: dict[str, Any]) -> dict[str, Any]:
    required, omitted = _applicability(manifest, "symbolic")
    if not required:
        return omitted or {}
    import sympy

    rows = manifest.get("symbolic_checks")
    if not isinstance(rows, list) or not rows:
        return {"status": "FAIL", "checks": [], "reason": "required symbolic_checks are missing"}
    checks: list[dict[str, Any]] = []
    seen: set[str] = set()
    allowed_assumptions = {"real", "positive", "negative", "nonzero", "integer", "finite", "nonnegative", "nonpositive"}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise VerificationError(f"symbolic_checks[{index}] must be an object")
        check_id = str(row.get("id") or "").strip()
        source = str(row.get("source") or "").strip()
        if not check_id or check_id in seen or not source:
            raise VerificationError(f"symbolic_checks[{index}] needs a unique id and source")
        seen.add(check_id)
        declarations = row.get("symbols")
        if not isinstance(declarations, list) or not declarations:
            raise VerificationError(f"symbolic check {check_id} requires declared symbols")
        symbols: dict[str, Any] = {}
        assumptions_record: dict[str, dict[str, bool]] = {}
        for declaration in declarations:
            if not isinstance(declaration, dict):
                raise VerificationError(f"symbolic check {check_id} has an invalid symbol declaration")
            name = str(declaration.get("name") or "").strip()
            assumptions = declaration.get("assumptions") or {}
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", name) or name in symbols:
                raise VerificationError(f"symbolic check {check_id} has an illegal or duplicate symbol")
            if not isinstance(assumptions, dict) or not set(assumptions) <= allowed_assumptions:
                raise VerificationError(f"symbolic check {check_id} has unsupported assumptions for {name}")
            normalized = {key: bool(value) for key, value in assumptions.items()}
            symbols[name] = sympy.Symbol(name, **normalized)
            assumptions_record[name] = normalized
        try:
            lhs = _safe_sympy_expression(str(row.get("lhs") or ""), symbols, sympy)
            rhs = _safe_sympy_expression(str(row.get("rhs") or ""), symbols, sympy)
            difference = sympy.cancel(sympy.together(lhs - rhs))
            simplified = sympy.simplify(difference)
            if simplified == 0:
                status, verdict = "PASS", "proven_equal_under_declared_assumptions"
            else:
                equality = simplified.equals(0)
                if equality is True:
                    status, verdict = "PASS", "proven_equal_under_declared_assumptions"
                elif equality is False:
                    status, verdict = "FAIL", "not_equivalent_under_declared_assumptions"
                else:
                    status, verdict = "UNKNOWN", "equivalence_not_established"
            denominators = sorted({str(sympy.denom(lhs)), str(sympy.denom(rhs))} - {"1"})
            checks.append({
                "id": check_id, "source": source, "status": status, "verdict": verdict,
                "difference": str(simplified), "assumptions": assumptions_record,
                "domain_exclusions_to_review": denominators,
            })
        except (VerificationError, TypeError, ValueError, SyntaxError) as exc:
            checks.append({"id": check_id, "source": source, "status": "FAIL", "error": str(exc)})
    return {"status": _record_status(checks), "engine": "SymPy", "checks": checks}


def _z3_expression(node: Any, variables: dict[str, Any], z3: Any) -> Any:
    if isinstance(node, bool) or isinstance(node, (int, float)):
        return node
    if isinstance(node, dict) and set(node) == {"var"}:
        name = str(node["var"])
        if name not in variables:
            raise VerificationError(f"constraint references undeclared parameter: {name}")
        return variables[name]
    if not isinstance(node, dict) or set(node) != {"op", "args"} or not isinstance(node["args"], list):
        raise VerificationError("constraints must use structured {op,args} expressions")
    op, raw_args = str(node["op"]), node["args"]
    args = [_z3_expression(value, variables, z3) for value in raw_args]
    arity = {"not": 1, "==": 2, "!=": 2, "<": 2, "<=": 2, ">": 2, ">=": 2, "/": 2, "**": 2}
    if op in arity and len(args) != arity[op]:
        raise VerificationError(f"constraint operator {op} has invalid arity")
    if op == "and": return z3.And(*args)
    if op == "or": return z3.Or(*args)
    if op == "not": return z3.Not(args[0])
    if op == "==": return args[0] == args[1]
    if op == "!=": return args[0] != args[1]
    if op == "<": return args[0] < args[1]
    if op == "<=": return args[0] <= args[1]
    if op == ">": return args[0] > args[1]
    if op == ">=": return args[0] >= args[1]
    if op == "+": return sum(args)
    if op == "-": return -args[0] if len(args) == 1 else args[0] - args[1]
    if op == "*":
        value = args[0]
        for item in args[1:]: value = value * item
        return value
    if op == "/": return args[0] / args[1]
    if op == "**": return args[0] ** args[1]
    raise VerificationError(f"unsupported constraint operator: {op}")


def _constraints(manifest: dict[str, Any]) -> dict[str, Any]:
    required, omitted = _applicability(manifest, "constraints")
    if not required:
        return omitted or {}
    import z3

    rows = manifest.get("constraint_checks")
    if not isinstance(rows, list) or not rows:
        return {"status": "FAIL", "checks": [], "reason": "required constraint_checks are missing"}
    checks: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise VerificationError(f"constraint_checks[{index}] must be an object")
        check_id = str(row.get("id") or "").strip()
        source = str(row.get("source") or "").strip()
        if not check_id or check_id in seen or not source:
            raise VerificationError(f"constraint_checks[{index}] needs a unique id and source")
        seen.add(check_id)
        declarations = row.get("parameters")
        constraints = row.get("constraints")
        if not isinstance(declarations, list) or not declarations or not isinstance(constraints, list) or not constraints:
            raise VerificationError(f"constraint check {check_id} needs parameters and constraints")
        variables: dict[str, Any] = {}
        types: dict[str, str] = {}
        for declaration in declarations:
            if not isinstance(declaration, dict):
                raise VerificationError(f"constraint check {check_id} has an invalid parameter")
            name, kind = str(declaration.get("name") or ""), str(declaration.get("type") or "").lower()
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", name) or name in variables or kind not in {"real", "integer", "boolean"}:
                raise VerificationError(f"constraint check {check_id} has an illegal parameter declaration")
            variables[name] = {"real": z3.Real, "integer": z3.Int, "boolean": z3.Bool}[kind](name)
            types[name] = kind
        solver = z3.Solver()
        try:
            solver.add(*[_z3_expression(node, variables, z3) for node in constraints])
            result = solver.check()
            if result == z3.sat:
                status, satisfiability = "PASS", "SAT"
                model = {name: str(solver.model().eval(value, model_completion=True)) for name, value in variables.items()}
            elif result == z3.unsat:
                status, satisfiability, model = "FAIL", "UNSAT", None
            else:
                status, satisfiability, model = "UNKNOWN", "UNKNOWN", None
            checks.append({
                "id": check_id, "source": source, "status": status,
                "satisfiability": satisfiability, "parameter_types": types, "model": model,
            })
        except (VerificationError, z3.Z3Exception, TypeError, ValueError) as exc:
            checks.append({"id": check_id, "source": source, "status": "FAIL", "error": str(exc)})
    return {"status": _record_status(checks), "engine": "Z3", "checks": checks}


def _safe_model_path(root: Path, value: Any) -> tuple[Path, str]:
    candidate = Path(str(value or ""))
    path = (root / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError as exc:
        raise VerificationError("numerical model_script must stay inside project_root") from exc
    if path.is_symlink() or not path.is_file() or path.suffix.lower() != ".py":
        raise VerificationError("numerical model_script must be one existing non-symlink Python file")
    return path, relative


def _admit_parameters(values: Any, specifications: Any) -> list[str]:
    if not isinstance(values, dict) or not isinstance(specifications, dict):
        return ["parameters and protocol parameter specifications must be objects"]
    issues: list[str] = []
    if set(values) != set(specifications):
        issues.append(f"parameter set mismatch: expected={sorted(specifications)}, actual={sorted(values)}")
        return issues
    for name, specification in specifications.items():
        if not isinstance(specification, dict):
            issues.append(f"parameter specification is invalid: {name}")
            continue
        value = values[name]
        kind = str(specification.get("type") or "").lower()
        valid_type = (
            kind == "number" and isinstance(value, (int, float)) and not isinstance(value, bool)
        ) or (kind == "integer" and isinstance(value, int) and not isinstance(value, bool)) or (
            kind == "boolean" and isinstance(value, bool)
        )
        if not valid_type:
            issues.append(f"parameter {name} violates declared type {kind}")
            continue
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if not math.isfinite(float(value)):
                issues.append(f"parameter {name} is non-finite")
            minimum, maximum = specification.get("minimum"), specification.get("maximum")
            if minimum is not None and value < minimum:
                issues.append(f"parameter {name} is below protocol minimum")
            if maximum is not None and value > maximum:
                issues.append(f"parameter {name} is above protocol maximum")
            if specification.get("exclusive_minimum") is not None and value <= specification["exclusive_minimum"]:
                issues.append(f"parameter {name} violates exclusive_minimum")
            if specification.get("exclusive_maximum") is not None and value >= specification["exclusive_maximum"]:
                issues.append(f"parameter {name} violates exclusive_maximum")
        if "allowed_values" in specification and value not in specification["allowed_values"]:
            issues.append(f"parameter {name} is not in allowed_values")
    return issues


def _plain_constraint(node: Any, values: dict[str, Any]) -> Any:
    if isinstance(node, (bool, int, float)):
        return node
    if isinstance(node, dict) and set(node) == {"var"}:
        name = str(node["var"])
        if name not in values:
            raise VerificationError(f"protocol constraint references unknown parameter: {name}")
        return values[name]
    if not isinstance(node, dict) or set(node) != {"op", "args"} or not isinstance(node["args"], list):
        raise VerificationError("protocol constraints must use structured {op,args} expressions")
    op, args = str(node["op"]), [_plain_constraint(item, values) for item in node["args"]]
    if op == "and": return all(args)
    if op == "or": return any(args)
    if op == "not": return not args[0]
    if op == "==": return args[0] == args[1]
    if op == "!=": return args[0] != args[1]
    if op == "<": return args[0] < args[1]
    if op == "<=": return args[0] <= args[1]
    if op == ">": return args[0] > args[1]
    if op == ">=": return args[0] >= args[1]
    if op == "+": return sum(args)
    if op == "-": return -args[0] if len(args) == 1 else args[0] - args[1]
    if op == "*": return math.prod(args)
    if op == "/": return args[0] / args[1]
    if op == "**": return args[0] ** args[1]
    raise VerificationError(f"unsupported protocol constraint operator: {op}")


def _run_model(function: Any, parameters: dict[str, Any]) -> tuple[str, float | None, str | None]:
    try:
        raw = function(dict(parameters))
        value = raw.get("value") if isinstance(raw, dict) else raw
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return "FAIL", None, "model must return a real scalar or {'value': real scalar}"
        numeric = float(value)
        if not math.isfinite(numeric):
            return "FAIL", numeric, "model returned a non-finite value"
        return "PASS", numeric, None
    except (ArithmeticError, OverflowError, FloatingPointError) as exc:
        return "FAIL", None, f"{type(exc).__name__}: {exc}"
    except Exception as exc:
        return "FAIL", None, f"model execution error: {type(exc).__name__}: {exc}"


def _expected_value(value: float, expected: Any) -> list[str]:
    if not isinstance(expected, dict):
        return ["expected result contract must be an object"]
    issues: list[str] = []
    if expected.get("finite") is not True:
        issues.append("every admitted numerical case must explicitly require finite=true")
    if "value" in expected:
        tolerance = float(expected.get("abs_tolerance", 0.0))
        if tolerance < 0 or abs(value - float(expected["value"])) > tolerance:
            issues.append("value differs from the protocol expectation")
    if "minimum" in expected and value < float(expected["minimum"]):
        issues.append("value is below the expected minimum")
    if "maximum" in expected and value > float(expected["maximum"]):
        issues.append("value is above the expected maximum")
    return issues


def _numerical(manifest: dict[str, Any], root: Path) -> dict[str, Any]:
    required, omitted = _applicability(manifest, "numerical_protocol")
    if not required:
        return omitted or {}
    protocol = manifest.get("numerical_protocol")
    if not isinstance(protocol, dict):
        return {"status": "FAIL", "checks": [], "reason": "required numerical_protocol is missing"}
    protocol_id = str(protocol.get("protocol_id") or "").strip()
    source = str(protocol.get("source") or "").strip()
    entrypoint = str(protocol.get("entrypoint") or "").strip()
    parameters = protocol.get("parameters")
    cases = protocol.get("cases")
    if not protocol_id or not source or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", entrypoint):
        raise VerificationError("numerical_protocol needs protocol_id, source, and a legal entrypoint")
    if not isinstance(parameters, dict) or not parameters or not isinstance(cases, list) or not cases:
        raise VerificationError("numerical_protocol needs parameter specifications and cases")
    kinds = {str(case.get("kind") or "") for case in cases if isinstance(case, dict)}
    if not {"boundary", "limit", "overflow"} <= kinds:
        raise VerificationError("numerical protocol must include boundary, limit, and overflow cases")
    model_path, relative = _safe_model_path(root, protocol.get("model_script"))
    model_hash = _sha256(model_path)
    expected_hash = str(protocol.get("model_sha256") or "").lower()
    if expected_hash and expected_hash != model_hash:
        raise VerificationError("numerical model_sha256 does not match model_script")
    module_spec = importlib.util.spec_from_file_location(f"research_guard_model_{model_hash[:12]}", model_path)
    if module_spec is None or module_spec.loader is None:
        raise VerificationError("could not load numerical model_script")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    function = getattr(module, entrypoint, None)
    if not callable(function):
        raise VerificationError("numerical model entrypoint is not callable")
    protocol_constraints = protocol.get("constraints") or []
    if not isinstance(protocol_constraints, list):
        raise VerificationError("numerical protocol constraints must be an array")
    checks: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise VerificationError(f"numerical case {index} must be an object")
        case_id, kind = str(case.get("id") or "").strip(), str(case.get("kind") or "").strip()
        if not case_id or case_id in seen or kind not in {"boundary", "limit", "overflow"}:
            raise VerificationError(f"numerical case {index} has an invalid id or kind")
        seen.add(case_id)
        samples = case.get("sequence") if kind == "limit" else [case.get("parameters")]
        if not isinstance(samples, list) or not samples:
            raise VerificationError(f"numerical case {case_id} has no samples")
        legality: list[dict[str, Any]] = []
        values: list[float] = []
        execution_errors: list[str] = []
        for sample_index, sample in enumerate(samples):
            sample_issues = _admit_parameters(sample, parameters)
            if not sample_issues:
                for constraint in protocol_constraints:
                    try:
                        if _plain_constraint(constraint, sample) is not True:
                            sample_issues.append("parameter combination violates a frozen protocol constraint")
                    except (VerificationError, ArithmeticError, TypeError, ValueError) as exc:
                        sample_issues.append(str(exc))
            legality.append({"sample": sample_index, "status": "ADMITTED" if not sample_issues else "PROTOCOL_VIOLATION", "issues": sample_issues})
            if sample_issues:
                continue
            execution_status, value, error = _run_model(function, sample)
            if execution_status == "PASS" and value is not None:
                values.append(value)
            else:
                execution_errors.append(f"sample {sample_index}: {error}")
        issues = [issue for item in legality for issue in item["issues"]] + execution_errors
        if not issues:
            if kind == "limit":
                expected = case.get("expected")
                if not isinstance(expected, dict) or "target" not in expected or "abs_tolerance" not in expected:
                    issues.append("limit case needs target and abs_tolerance")
                elif len(values) < 3:
                    issues.append("limit case requires at least three admitted samples")
                else:
                    target, tolerance = float(expected["target"]), float(expected["abs_tolerance"])
                    distances = [abs(value - target) for value in values]
                    if tolerance < 0 or distances[-1] > tolerance:
                        issues.append("limit sequence does not reach the declared target tolerance")
                    if any(right > left + 1e-15 for left, right in zip(distances, distances[1:])) or not any(
                        right < left - 1e-15 for left, right in zip(distances, distances[1:])
                    ):
                        issues.append("limit sequence does not demonstrate convergence toward the target")
            else:
                if kind == "boundary":
                    sample = samples[0]
                    hits_boundary = any(
                        sample[name] in {specification.get("minimum"), specification.get("maximum")}
                        for name, specification in parameters.items()
                        if isinstance(specification, dict) and ("minimum" in specification or "maximum" in specification)
                    )
                    if not hits_boundary:
                        issues.append("boundary case does not exercise a declared minimum or maximum")
                issues.extend(_expected_value(values[0], case.get("expected")))
        checks.append({
            "id": case_id, "kind": kind, "status": "PASS" if not issues else "FAIL",
            "protocol_legality": legality, "values": values, "issues": issues,
        })
    return {
        "status": _record_status(checks), "engine": "hash_bound_project_python_model",
        "protocol_id": protocol_id, "source": source, "model_script": relative,
        "model_sha256": model_hash, "checks": checks,
    }


def run(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict) or not isinstance(payload.get("manifest"), dict):
        raise VerificationError("input must contain a verification manifest")
    root = Path(str(payload.get("project_root") or "")).expanduser().resolve()
    if not root.is_dir():
        raise VerificationError("project_root is not a directory")
    manifest = payload["manifest"]
    results = {
        "dimensional": _dimensional(manifest),
        "symbolic": _symbolic(manifest),
        "constraints": _constraints(manifest),
        "numerical_protocol": _numerical(manifest, root),
    }
    return {
        "schema_version": 1,
        "manifest_sha256": hashlib.sha256(_canonical(manifest)).hexdigest(),
        "results": results,
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
    Path(arguments.output).write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if "worker_error" not in result else 2


if __name__ == "__main__":
    raise SystemExit(main())
