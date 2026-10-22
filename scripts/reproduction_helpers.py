"""Explicit-runtime observations and local replay; never convert historical failures to PASS."""
from __future__ import annotations

import argparse
import json
import subprocess
import os
import shutil
import tarfile
import urllib.request
from pathlib import Path
from typing import Any

LEAN_BASIC_VERSION = "4.8.0"
LEAN_BASIC_URL = "https://github.com/leanprover/lean4/releases/download/v4.8.0/lean-4.8.0-windows.tar.zst"
LEAN_BASIC_SHA256 = "dba75dd57b1a80150667b655ac712a1bbb9896220cee237e947ddbc06e574bfc"
LEAN_BASIC_BYTES = 189611926


def lean_basic_profile(root: str | Path) -> dict[str, Any]:
    root = Path(root).resolve()
    profile_file = root / "lean-basic-profile.json"
    profile = json.loads(profile_file.read_text(encoding="utf8")) if profile_file.is_file() else {}
    executable = root / "bin" / "lean.exe"
    if not executable.is_file():
        executable = root / "bin" / "lean"
    if not executable.is_file():
        raise ValueError("Lean executable is unavailable in runtime_root/bin")
    return {**profile, "profile": "lean-basic", "runtime_root": str(root),
            "lean_executable": str(executable), "library_path": str(root / "lib/lean")}


def install_lean_basic(destination: str | Path, *, archive: str | Path | None = None, proxy: str | None = None) -> dict[str, Any]:
    """Install a standalone Windows Init profile, never the Mathlib component."""
    if os.name != "nt":
        raise ValueError("This Lean-basic material targets Windows x64; no other platform was verified")
    from compression.zstd import ZstdFile

    root = Path(destination).resolve()
    source = Path(archive).resolve() if archive else root.parent / "downloads" / "lean-4.8.0-windows.tar.zst"
    if not source.is_file():
        if archive:
            raise ValueError("The explicitly supplied local Lean archive does not exist")
        source.parent.mkdir(parents=True, exist_ok=True)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({"http": proxy, "https": proxy} if proxy else {}))
        request = urllib.request.Request(LEAN_BASIC_URL, headers={"User-Agent": "ResearchGuardLeanBasic/1.0"})
        partial = source.with_suffix(".part")
        with opener.open(request, timeout=30) as response, partial.open("wb") as handle:
            shutil.copyfileobj(response, handle, 1024 * 1024)
        partial.replace(source)
    root.mkdir(parents=True, exist_ok=True)
    selected = []
    with ZstdFile(source, "rb") as compressed, tarfile.open(fileobj=compressed, mode="r|") as members:
        for member in members:
            if not member.isfile():
                continue
            relative = Path(*Path(member.name).parts[1:])
            name = relative.as_posix()
            keep = name in {"bin/lean.exe", "bin/libleanshared.dll", "bin/libInit_shared.dll", "lib/lean/Init.olean"} or (name.startswith("lib/lean/Init/") and name.endswith(".olean"))
            if not keep:
                continue
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with members.extractfile(member) as reader, target.open("wb") as writer:
                shutil.copyfileobj(reader, writer, 1024 * 1024)
            selected.append({"path": name, "bytes": member.size})
    sample = root / "examples" / "basic-proof.lean"
    sample.parent.mkdir(exist_ok=True)
    sample.write_text("import Init\nset_option autoImplicit false\n-- FORMULA_ID: identity\ntheorem identity_example (sampleCount : Nat) : sampleCount = sampleCount := by rfl\n#eval (List.range 6).foldl (fun x y => x + y) 0\n", encoding="utf8")
    command = [str(root / "bin/lean.exe"), "-o", str(sample.with_suffix(".olean")), str(sample)]
    run = subprocess.run(command, cwd=sample.parent, capture_output=True, text=True, encoding="utf8", errors="replace", timeout=60)
    profile = {"schema_version": 1, "profile": "lean-basic", "status": "INSTALLED" if run.returncode == 0 else "COMPILATION_FAILED", "version": LEAN_BASIC_VERSION,
               "toolchain": "leanprover/lean4:v4.8.0", "mathlib": False, "scope": "Standalone Init-only supplied formulas; not lean-mathlib",
               "source_url": LEAN_BASIC_URL, "archive_bytes": source.stat().st_size,
               "files": selected, "installed_bytes": sum(item["bytes"] for item in selected), "sample": "examples/basic-proof.lean",
               "sample_compile": {"command": command, "returncode": run.returncode, "stdout": run.stdout, "stderr": run.stderr},
               "requirements": "Windows x64/UCRT; installer requires Python 3.14 compression.zstd; no Mathlib, Elan, or global PATH change."}
    (root / "lean-basic-profile.json").write_text(json.dumps(profile, indent=2), encoding="utf8")
    if run.returncode:
        raise ValueError("Lean-basic sample compilation failed: " + (run.stderr or run.stdout)[-2000:])
    return lean_basic_profile(root)


RUNTIME_PROBE = """import sys,sysconfig,json,importlib,importlib.metadata
names={'matplotlib':'matplotlib','networkx':'networkx','numpy':'numpy','optuna':'optuna','Pillow':'PIL','pint':'pint','psutil':'psutil','pypdf':'pypdf','PyYAML':'yaml','sympy':'sympy','z3-solver':'z3'}
observed={}
for distribution,module in names.items():
 try:
  loaded=importlib.import_module(module)
  observed[distribution]={'status':'PASS','version':importlib.metadata.version(distribution),'origin':getattr(loaded,'__file__',None)}
 except Exception as error: observed[distribution]={'status':'FAIL','error':type(error).__name__+': '+str(error)}
print(json.dumps({'executable':sys.executable,'python':sys.version,'python_major_minor':list(sys.version_info[:2]),'platform':sysconfig.get_platform(),'cache_tag':sys.implementation.cache_tag,'packages':observed,'status':'PASS' if all(v['status']=='PASS' for v in observed.values()) else 'FAIL'}))
"""


def runtime_snapshot(python: str | Path) -> dict[str, Any]:
    command = [str(Path(python).resolve()), "-I", "-X", "utf8", "-c", RUNTIME_PROBE]
    try:
        run = subprocess.run(command, capture_output=True, text=True, encoding="utf8", errors="replace")
    except OSError as error:
        return {"status": "FAIL", "command": command, "error": type(error).__name__ + ": " + str(error)}
    if run.returncode:
        return {"status": "FAIL", "command": command, "returncode": run.returncode, "stdout": run.stdout, "stderr": run.stderr}
    return {**json.loads(run.stdout), "command": command, "returncode": run.returncode, "stderr": run.stderr,
            "scope": "Observed exact interpreter and installed versions; no automatic install or global interpreter selection."}


def verify_runtime(python: str | Path, lock_file: str | Path) -> dict[str, Any]:
    """Compare against a saved observation; a lock check does not install packages."""
    expected = json.loads(Path(lock_file).read_text(encoding="utf8"))
    actual = runtime_snapshot(python)
    differences = []
    if expected.get("status") != "PASS" or actual.get("status") != "PASS":
        differences.append("Both saved observation and current imports must be PASS")
    for key in ["python", "platform", "cache_tag"]:
        if expected.get(key) != actual.get(key):
            differences.append(f"Runtime differs: {key}")
    for name, package in expected.get("packages", {}).items():
        current = actual.get("packages", {}).get(name, {})
        if current.get("status") != "PASS" or current.get("version") != package.get("version"):
            differences.append(f"Package differs: {name}")
    return {"status": "PASS" if not differences else "MISMATCH", "differences": differences,
            "lock_file": str(Path(lock_file).resolve()), "actual": actual,
            "scope": "Exact observed Python build/platform/cache tag and package versions; no solver or installation was performed."}


def replay_saved_search(project_root: str | Path, manifest_path: str | Path) -> dict[str, Any]:
    from evidence_kernel import io_path, verify_evidence_manifest

    root = Path(project_root).resolve()
    path = Path(manifest_path)
    path = path if path.is_absolute() else root / path
    path.resolve().relative_to(root)
    manifest = json.loads(io_path(path).read_text(encoding="utf8"))
    errors = verify_evidence_manifest(root, path.relative_to(root).as_posix(), manifest=manifest)
    observations = [{"source": item.get("source"), "query_id": item.get("query_id"), "status_code": item.get("status_code"),
                     "media_type": item.get("media_type"), "raw_path": item.get("raw_path"), "error": item.get("error")} for item in manifest.get("attempts", [])]
    return {"status": "PASS" if not errors else "INVALID", "scope": "Saved-response replay only; no new requests or novelty/index claim.",
            "scientific_status": "HISTORICAL_EVIDENCE_ONLY", "errors": errors, "attempts": observations,
            "manifest": str(path)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    runtime = commands.add_parser("runtime-snapshot")
    runtime.add_argument("--python", type=Path, required=True)
    runtime.add_argument("--output", type=Path)
    verify = commands.add_parser("verify-runtime")
    verify.add_argument("--python", type=Path, required=True)
    verify.add_argument("--lock", type=Path, required=True)
    verify.add_argument("--output", type=Path)
    replay = commands.add_parser("replay-search")
    replay.add_argument("--project-root", type=Path, required=True)
    replay.add_argument("--manifest", type=Path, required=True)
    replay.add_argument("--output", type=Path)
    lean = commands.add_parser("install-lean-basic")
    lean.add_argument("--destination", type=Path, required=True)
    lean.add_argument("--archive", type=Path)
    lean.add_argument("--proxy")
    lean.add_argument("--output", type=Path)
    profile = commands.add_parser("lean-basic-profile")
    profile.add_argument("--runtime-root", type=Path, required=True)
    profile.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.action == "runtime-snapshot":
        result = runtime_snapshot(args.python)
    elif args.action == "verify-runtime":
        result = verify_runtime(args.python, args.lock)
    elif args.action == "replay-search":
        result = replay_saved_search(args.project_root, args.manifest)
    elif args.action == "install-lean-basic":
        result = install_lean_basic(args.destination, archive=args.archive, proxy=args.proxy)
    else:
        result = lean_basic_profile(args.runtime_root)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] in {"PASS", "INSTALLED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
