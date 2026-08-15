from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import stat
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

try:
    import optuna
except ImportError:  # pragma: no cover - reported when optimization is requested
    optuna = None  # type: ignore[assignment]


STATE_DIR = ".research-guard/domain-skills"
MAX_ARCHIVE_BYTES = 50 * 1024 * 1024
MAX_EXPANDED_BYTES = 25 * 1024 * 1024
MAX_FILES = 600
ALLOWED_LICENSES = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "MPL-2.0"}
TEXT_SUFFIXES = {".md", ".txt", ".py", ".json", ".yaml", ".yml", ".toml", ".tex", ".bib", ".csv", ".tsv", ".js", ".mjs", ".ts", ".sh", ".ps1"}
EXECUTABLE_SUFFIXES = {".py", ".js", ".mjs", ".ts", ".sh", ".ps1"}
BLOCK_PATTERNS = {
    "remote_shell_pipe": re.compile(r"(?:curl|wget)[^\n|]{0,300}\|\s*(?:ba)?sh\b", re.I),
    "credential_harvest": re.compile(r"(?:os\.environ|process\.env|Get-ChildItem\s+Env:).{0,300}(?:requests?\.|fetch\(|Invoke-WebRequest|curl\s)", re.I | re.S),
    "broad_recursive_delete": re.compile(r"(?:rm\s+-rf\s+(?:/|~|\$HOME)|Remove-Item[^\n]{0,120}-Recurse[^\n]{0,120}(?:\\$|~|HOME))", re.I),
    "encoded_exec": re.compile(r"(?:base64\s+(?:-d|--decode)|FromBase64String).{0,300}(?:exec|eval|powershell|cmd|sh\b)", re.I | re.S),
}


class DomainSkillError(ValueError):
    pass


def _rmtree_writable(path: Path) -> None:
    target = path.resolve()
    if ".research-guard" not in target.parts or "quarantine" not in target.parts:
        raise DomainSkillError(f"refusing to remove non-quarantine path: {target}")

    def repair(function, failing_path, _error):
        os.chmod(failing_path, stat.S_IWRITE)
        function(failing_path)

    shutil.rmtree(target, onexc=repair)


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted((p for p in root.rglob("*") if p.is_file()), key=lambda p: p.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(_sha(path).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _root(value: str | os.PathLike[str]) -> Path:
    root = Path(value).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _state_root(value: str | os.PathLike[str]) -> Path:
    root = _root(value) / STATE_DIR
    root.mkdir(parents=True, exist_ok=True)
    return root


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    if not slug or len(slug) > 96:
        raise DomainSkillError("skill identifier is invalid")
    return slug


def _repo(value: str) -> str:
    text = str(value or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", text):
        raise DomainSkillError("repository must be owner/repo")
    return text


def _opener():
    proxy = os.environ.get("RESEARCH_GUARD_FOREIGN_PROXY", "http://127.0.0.1:7897")
    return urllib.request.build_opener(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))


def _json_url(url: str, timeout: float = 30) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "ResearchGuardDomainSkill/1.0"})
    try:
        with _opener().open(request, timeout=float(timeout)) as response:
            value = json.load(response)
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise DomainSkillError(f"remote discovery failed: {exc}") from exc
    if not isinstance(value, dict):
        raise DomainSkillError("remote discovery returned a non-object response")
    return value


def discover_domain_skills(query: str, limit: int = 10) -> dict[str, Any]:
    text = " ".join(str(query or "").split())
    if len(text) < 3:
        raise DomainSkillError("a specific professional-domain query is required")
    limit = max(1, min(int(limit), 20))
    skillhub_url = f"https://skills.sh/api/search?{urllib.parse.urlencode({'q': text, 'limit': limit})}"
    source_status: list[dict[str, Any]] = []
    try:
        skillhub = _json_url(skillhub_url).get("skills") or []
        source_status.append({"source": "skills.sh", "url": skillhub_url, "status": "PASS", "registration_required": False})
    except DomainSkillError as exc:
        skillhub = []
        source_status.append({"source": "skills.sh", "url": skillhub_url, "status": "ERROR", "error": str(exc), "registration_required": False})
    results: list[dict[str, Any]] = []
    for item in skillhub:
        source = str(item.get("source") or "")
        if not re.fullmatch(r"[^/]+/[^/]+", source):
            continue
        results.append({
            "source": "skills.sh", "name": item.get("name"), "skill_id": item.get("skillId"),
            "repository": source, "installs": item.get("installs"),
            "skill_url": f"https://skills.sh/{item.get('id')}", "repository_url": f"https://github.com/{source}",
        })
    github_url = "https://api.github.com/search/repositories?" + urllib.parse.urlencode(
        {"q": f"{text} research skill in:name,description,readme", "sort": "stars", "per_page": min(limit, 10)}
    )
    try:
        github = _json_url(github_url).get("items") or []
        source_status.append({"source": "github-public-api", "url": github_url, "status": "PASS", "registration_required": False})
    except DomainSkillError as exc:
        github = []
        source_status.append({"source": "github-public-api", "url": github_url, "status": "ERROR", "error": str(exc), "registration_required": False})
    for item in github:
        results.append({
            "source": "github", "name": item.get("name"), "repository": item.get("full_name"),
            "stars": item.get("stargazers_count"), "description": item.get("description"),
            "repository_url": item.get("html_url"),
        })
    if not results:
        raise DomainSkillError(f"all no-registration discovery routes failed: {source_status}")
    return {
        "status": "DISCOVERY_COMPLETE", "query": text, "results": results,
        "sources": source_status,
        "next_action": "Select one narrow candidate, then stage it in quarantine. Search popularity is not admission evidence.",
    }


def _download(url: str, target: Path, timeout: float = 60) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "ResearchGuardDomainSkill/1.0"})
    try:
        with _opener().open(request, timeout=float(timeout)) as response, target.open("wb") as handle:
            total = 0
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                total += len(block)
                if total > MAX_ARCHIVE_BYTES:
                    raise DomainSkillError("repository archive exceeds the quarantine size limit")
                handle.write(block)
    except (OSError, urllib.error.URLError) as exc:
        raise DomainSkillError(f"repository download failed: {exc}") from exc


def _registered_git() -> str:
    from dependency_manager import DependencyError, require

    try:
        receipt = require("portable-git")
    except DependencyError as exc:
        raise DomainSkillError(f"{exc.code}: {exc}") from exc
    executable = Path(str((receipt.get("executables") or {}).get("git") or "")).resolve()
    if not executable.is_file():
        raise DomainSkillError("DEPENDENCY_MISSING: registered Git executable is unavailable")
    return str(executable)


def _remote_head(repository: str, timeout: float = 45) -> str:
    proxy = os.environ.get("RESEARCH_GUARD_FOREIGN_PROXY", "http://127.0.0.1:7897")
    command = [
        _registered_git(), "-c", f"http.proxy={proxy}", "ls-remote",
        f"https://github.com/{repository}.git", "HEAD",
    ]
    try:
        run = subprocess.run(command, text=True, capture_output=True, timeout=float(timeout), check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DomainSkillError(f"git ls-remote failed: {exc}") from exc
    match = re.match(r"([0-9a-f]{40})\s+HEAD", run.stdout.strip())
    if run.returncode or not match:
        raise DomainSkillError(f"git ls-remote did not return an immutable HEAD: {run.stderr.strip()}")
    return match.group(1)


def _git(repository: str, *arguments: str, cwd: Path | None = None, timeout: float = 90) -> str:
    proxy = os.environ.get("RESEARCH_GUARD_FOREIGN_PROXY", "http://127.0.0.1:7897")
    command = [_registered_git(), "-c", f"http.proxy={proxy}", *arguments]
    try:
        run = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=float(timeout), check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DomainSkillError(f"git operation failed: {exc}") from exc
    if run.returncode:
        raise DomainSkillError(f"git operation failed: {run.stderr.strip()}")
    return run.stdout


def _detect_license(skill_text: str, archive: zipfile.ZipFile, members: list[zipfile.ZipInfo]) -> str:
    frontmatter = re.match(r"^---\s*\n([\s\S]+?)\n---", skill_text)
    declared = ""
    if frontmatter:
        match = re.search(r"^license:\s*[\"']?([^\n\"']+)", frontmatter.group(1), flags=re.I | re.M)
        declared = str(match.group(1) if match else "").casefold()
    license_members = [
        member for member in members
        if not member.is_dir() and PurePosixPath(member.filename).name.casefold() in {"license", "license.md", "license.txt", "copying"}
        and len(PurePosixPath(member.filename).parts) <= 2
    ]
    license_text = declared
    for member in license_members[:2]:
        license_text += "\n" + archive.read(member).decode("utf-8", errors="replace").casefold()
    if "apache license" in license_text and "version 2.0" in license_text:
        return "Apache-2.0"
    if "permission is hereby granted, free of charge" in license_text or re.search(r"\bmit\b", declared):
        return "MIT"
    if "3-clause bsd" in license_text or "bsd 3-clause" in license_text or "3-clause bsd license" in declared:
        return "BSD-3-Clause"
    if "2-clause bsd" in license_text or "bsd 2-clause" in license_text:
        return "BSD-2-Clause"
    if "mozilla public license" in license_text and "2.0" in license_text:
        return "MPL-2.0"
    if re.search(r"\bisc\b", declared):
        return "ISC"
    if "creative commons attribution-noncommercial 4.0" in license_text or "cc-by-nc-4.0" in license_text:
        return "CC-BY-NC-4.0"
    return "NOASSERTION"


def _safe_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    members = archive.infolist()
    if len(members) > MAX_FILES * 20:
        raise DomainSkillError("repository archive contains too many files")
    total = 0
    for member in members:
        pure = PurePosixPath(member.filename.replace("\\", "/"))
        if pure.is_absolute() or ".." in pure.parts or re.match(r"^[A-Za-z]:", member.filename):
            raise DomainSkillError(f"unsafe archive path: {member.filename}")
        total += member.file_size
        if total > MAX_EXPANDED_BYTES * 20:
            raise DomainSkillError("repository archive expands beyond the inspection limit")
    return members


def stage_domain_skill(project_root: str, repository: str, skill_id: str, skill_path: str | None = None) -> dict[str, Any]:
    repo = _repo(repository)
    slug = _slug(skill_id)
    commit = _remote_head(repo)
    base = _state_root(project_root) / "quarantine" / slug / commit
    if base.exists() and (base / "manifest.json").is_file():
        _, existing = _manifest(project_root, slug, commit)
        return {**existing, "quarantine_path": str(base), "reused": True}
    if base.exists():
        _rmtree_writable(base)
    base.mkdir(parents=True)
    clone = base / "repository"
    _git(repo, "clone", "--depth", "1", "--filter=blob:none", "--no-checkout", f"https://github.com/{repo}.git", str(clone), timeout=120)
    actual_commit = _git(repo, "-C", str(clone), "rev-parse", "HEAD").strip()
    if actual_commit != commit:
        raise DomainSkillError("repository HEAD changed between discovery and sparse checkout; retry explicitly")
    tree_files = [line.strip() for line in _git(repo, "-C", str(clone), "ls-tree", "-r", "--name-only", "HEAD").splitlines() if line.strip()]
    skill_files = [name for name in tree_files if name.casefold().endswith("/skill.md") or name.casefold() == "skill.md"]
    if skill_path:
        wanted = str(skill_path).replace("\\", "/").strip("/").casefold() + "/skill.md"
        matches = [name for name in skill_files if name.casefold() == wanted]
    else:
        matches = [name for name in skill_files if PurePosixPath(name).parent.name.casefold() == slug]
        if not matches and len(skill_files) == 1:
            matches = skill_files
    if len(matches) != 1:
        raise DomainSkillError(f"could not identify one Skill directory; candidates={skill_files[:30]}")
    prefix = PurePosixPath(matches[0]).parent
    selected_names = [name for name in tree_files if PurePosixPath(name).is_relative_to(prefix)]
    license_names = [name for name in tree_files if "/" not in name and name.casefold() in {"license", "license.md", "license.txt", "copying"}]
    sparse = [prefix.as_posix(), *license_names]
    _git(repo, "-C", str(clone), "sparse-checkout", "init", "--cone")
    _git(repo, "-C", str(clone), "sparse-checkout", "set", *sparse)
    _git(repo, "-C", str(clone), "checkout", "--detach", commit, timeout=120)
    skill_source = clone.joinpath(*prefix.parts)
    files = [path for path in skill_source.rglob("*") if path.is_file()]
    if len(files) > MAX_FILES or sum(path.stat().st_size for path in files) > MAX_EXPANDED_BYTES:
        raise DomainSkillError("selected Skill exceeds quarantine limits")
    skill_text = (skill_source / "SKILL.md").read_text(encoding="utf-8", errors="replace")
    declared = re.search(r"^license:\s*[\"']?([^\n\"']+)", skill_text, flags=re.I | re.M)
    license_text = str(declared.group(1) if declared else "")
    for name in license_names:
        path = clone / name
        if path.is_file():
            license_text += "\n" + path.read_text(encoding="utf-8", errors="replace")
    lowered = license_text.casefold()
    declared_text = str(declared.group(1) if declared else "").casefold()
    if "3-clause bsd" in declared_text or "bsd 3-clause" in declared_text:
        license_id = "BSD-3-Clause"
    elif "2-clause bsd" in declared_text or "bsd 2-clause" in declared_text:
        license_id = "BSD-2-Clause"
    elif "apache-2.0" in declared_text or "apache 2.0" in declared_text:
        license_id = "Apache-2.0"
    elif re.search(r"\bmit\b", declared_text):
        license_id = "MIT"
    elif "apache license" in lowered and "version 2.0" in lowered:
        license_id = "Apache-2.0"
    elif "permission is hereby granted, free of charge" in lowered or re.search(r"\bmit\b", str(declared.group(1) if declared else ""), re.I):
        license_id = "MIT"
    elif "3-clause bsd" in lowered or "bsd 3-clause" in lowered or "3-clause bsd license" in lowered:
        license_id = "BSD-3-Clause"
    elif "2-clause bsd" in lowered or "bsd 2-clause" in lowered:
        license_id = "BSD-2-Clause"
    elif "mozilla public license" in lowered and "2.0" in lowered:
        license_id = "MPL-2.0"
    elif re.search(r"\bisc\b", str(declared.group(1) if declared else ""), re.I):
        license_id = "ISC"
    else:
        license_id = "NOASSERTION"
    content_root = base / "content"
    shutil.copytree(skill_source, content_root)
    _rmtree_writable(clone)
    manifest = {
        "schema_version": 1, "status": "STAGED", "skill_id": slug, "repository": repo,
        "repository_url": f"https://github.com/{repo}", "commit": commit, "license": license_id,
        "license_allowed": license_id in ALLOWED_LICENSES, "skill_path": prefix.as_posix(),
        "content_hash": _tree_hash(content_root), "staged_at": _now(), "optimization_rounds": [],
    }
    (base / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    scan = scan_domain_skill(project_root, slug, commit)
    return {**manifest, "scan": scan, "quarantine_path": str(base)}


def _manifest(project_root: str, skill_id: str, commit: str | None = None) -> tuple[Path, dict[str, Any]]:
    root = _state_root(project_root) / "quarantine" / _slug(skill_id)
    if commit:
        base = root / commit
    else:
        candidates = sorted((p for p in root.glob("*") if p.is_dir()), key=lambda p: p.name)
        if len(candidates) != 1:
            raise DomainSkillError("provide commit when zero or multiple staged versions exist")
        base = candidates[0]
    path = base / "manifest.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DomainSkillError(f"staged Skill manifest is invalid: {exc}") from exc
    if value.get("content_hash") != _tree_hash(base / "content"):
        raise DomainSkillError("staged Skill changed after its manifest was written")
    return base, value


def scan_domain_skill(project_root: str, skill_id: str, commit: str | None = None) -> dict[str, Any]:
    base, manifest = _manifest(project_root, skill_id, commit)
    findings: list[dict[str, str]] = []
    files: list[dict[str, Any]] = []
    for path in sorted((p for p in (base / "content").rglob("*") if p.is_file())):
        relative = path.relative_to(base / "content").as_posix()
        suffix = path.suffix.casefold()
        files.append({"path": relative, "bytes": path.stat().st_size, "sha256": _sha(path)})
        if suffix not in TEXT_SUFFIXES or path.stat().st_size > 2 * 1024 * 1024:
            findings.append({"severity": "block", "kind": "unsupported_or_large_file", "path": relative})
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for kind, pattern in BLOCK_PATTERNS.items():
            if pattern.search(text):
                severity = "block" if suffix in EXECUTABLE_SUFFIXES else "review"
                findings.append({"severity": severity, "kind": kind, "path": relative})
    skill_path = base / "content" / "SKILL.md"
    if not skill_path.is_file():
        findings.append({"severity": "block", "kind": "missing_skill_md", "path": "SKILL.md"})
    else:
        body = skill_path.read_text(encoding="utf-8", errors="replace")
        if not re.match(r"^---\s*\n[\s\S]+?\n---\s*\n", body):
            findings.append({"severity": "block", "kind": "invalid_frontmatter", "path": "SKILL.md"})
    result = {
        "status": "PASS" if manifest.get("license_allowed") and not any(f["severity"] == "block" for f in findings) else "BLOCKED",
        "license": manifest.get("license"), "license_allowed": manifest.get("license_allowed"),
        "content_hash": manifest["content_hash"], "files": files, "findings": findings, "scanned_at": _now(),
        "execution_allowed": False,
    }
    manifest["scan"] = result
    (base / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9][a-z0-9_.+-]{1,}|[\u4e00-\u9fff]{2,}", value.casefold()))


def optimize_domain_skill(
    project_root: str, skill_id: str, query: str, rounds: int = 3,
    positive_prompts: list[str] | None = None, negative_prompts: list[str] | None = None,
) -> dict[str, Any]:
    if optuna is None:
        raise DomainSkillError("Optuna is required for domain Skill optimization")
    # Optimization results are persisted below; Optuna's per-trial INFO stream is
    # intentionally suppressed so MCP/CLI responses remain bounded and auditable.
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    if rounds not in {2, 3}:
        raise DomainSkillError("domain Skill optimization requires exactly 2 or 3 rounds")
    base, manifest = _manifest(project_root, skill_id)
    scan = manifest.get("scan") or scan_domain_skill(project_root, skill_id, manifest.get("commit"))
    if scan.get("status") != "PASS":
        raise DomainSkillError("a blocked Skill cannot be optimized")
    positives = positive_prompts or [query, f"Help me conduct rigorous research about {query}", f"Find domain-specific methods and evidence for {query}"]
    negatives = negative_prompts or ["build a landing page", "fix a generic unit test", "organize vacation photos"]
    heldout_positives = [f"Provide a specialist evidence-based deep dive into {query}", f"Which professional tools apply to {query}?"]
    heldout_negatives = ["write a product launch announcement", "plan a weekend travel itinerary"]
    if len(positives) < 2 or len(negatives) < 2:
        raise DomainSkillError("optimization needs at least two positive and two negative prompts")
    content = base / "content"
    files = [p for p in content.rglob("*") if p.is_file() and p.suffix.casefold() in TEXT_SUFFIXES]
    descriptions = {p: p.read_text(encoding="utf-8", errors="replace") for p in files}
    query_tokens = _tokens(query)
    ranked_refs = sorted(
        (p for p in files if p.name != "SKILL.md"),
        key=lambda p: (-len(_tokens(descriptions[p]) & query_tokens), len(descriptions[p]), p.as_posix()),
    )
    accepted: list[dict[str, Any]] = []
    prior_score = float("-inf")
    for round_index in range(rounds):
        sampler = optuna.samplers.TPESampler(seed=20260813 + round_index)
        study = optuna.create_study(direction="maximize", sampler=sampler)

        def objective(trial):
            max_refs = trial.suggest_int("max_reference_files", 0, min(5, len(ranked_refs)))
            include_scripts = trial.suggest_categorical("include_scripts", [False, True])
            threshold = trial.suggest_int("trigger_token_threshold", 1, 4)
            selected = [content / "SKILL.md"] + ranked_refs[:max_refs]
            if not include_scripts:
                selected = [p for p in selected if p.suffix.casefold() not in EXECUTABLE_SUFFIXES or p.name == "SKILL.md"]
            corpus = "\n".join(descriptions[p] for p in selected)
            corpus_tokens = _tokens(corpus)
            positive_hits = sum(len(_tokens(prompt) & corpus_tokens) >= threshold for prompt in positives) / len(positives)
            negative_hits = sum(len(_tokens(prompt) & corpus_tokens) >= threshold for prompt in negatives) / len(negatives)
            query_coverage = len(query_tokens & corpus_tokens) / max(1, len(query_tokens))
            context_penalty = min(1.0, len(corpus) / 60000)
            return 5 * positive_hits + 3 * query_coverage - 4 * negative_hits - context_penalty

        study.optimize(objective, n_trials=18, show_progress_bar=False)
        config = dict(study.best_params)
        selected = ["SKILL.md"] + [p.relative_to(content).as_posix() for p in ranked_refs[: int(config["max_reference_files"])]]
        if not config["include_scripts"]:
            selected = [p for p in selected if Path(p).suffix.casefold() not in EXECUTABLE_SUFFIXES or p == "SKILL.md"]
        score = float(study.best_value)
        selected_corpus = "\n".join(descriptions[content / path] for path in selected)
        selected_tokens = _tokens(selected_corpus)
        heldout_positive_hits = [len(_tokens(prompt) & selected_tokens) >= int(config["trigger_token_threshold"]) for prompt in heldout_positives]
        heldout_negative_hits = [len(_tokens(prompt) & selected_tokens) >= int(config["trigger_token_threshold"]) for prompt in heldout_negatives]
        heldout_pass = all(heldout_positive_hits) and not any(heldout_negative_hits)
        accepted_round = score + 1e-12 >= prior_score and heldout_pass
        record = {
            "round": round_index + 1, "optimizer": "optuna.tpe", "trials": len(study.trials),
            "objective": "positive-domain coverage + query coverage - false triggers - context cost",
            "score": score, "accepted": accepted_round, "configuration": config,
            "selected_files": selected, "positive_prompts": positives, "negative_prompts": negatives,
            "heldout": {
                "positive_prompts": heldout_positives, "negative_prompts": heldout_negatives,
                "positive_hits": heldout_positive_hits, "negative_hits": heldout_negative_hits,
                "status": "PASS" if heldout_pass else "FAIL",
            },
        }
        accepted.append(record)
        if accepted_round:
            prior_score = score
    manifest["optimization_rounds"] = accepted
    manifest["optimized_at"] = _now()
    manifest["status"] = "OPTIMIZED" if len(accepted) in {2, 3} and all(r["accepted"] for r in accepted) else "OPTIMIZATION_FAILED"
    (base / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"status": manifest["status"], "skill_id": skill_id, "content_hash": manifest["content_hash"], "rounds": accepted}


def admit_domain_skill(project_root: str, skill_id: str, overlap_decision: str, canonical_owner: str) -> dict[str, Any]:
    if overlap_decision not in {"domain_only", "fuse_narrow_adapter"}:
        raise DomainSkillError("overlap_decision must retain a narrow domain-only boundary")
    if not str(canonical_owner or "").strip():
        raise DomainSkillError("canonical_owner is required")
    base, manifest = _manifest(project_root, skill_id)
    if (manifest.get("scan") or {}).get("status") != "PASS":
        raise DomainSkillError("Skill scan has not passed")
    rounds = manifest.get("optimization_rounds") or []
    if len(rounds) not in {2, 3} or not all(item.get("accepted") for item in rounds):
        raise DomainSkillError("Skill admission requires exactly 2 or 3 accepted optimization rounds")
    admitted = _state_root(project_root) / "admitted" / _slug(skill_id)
    if admitted.exists():
        raise DomainSkillError("an admitted Skill is append-only; use a new identifier for a changed version")
    shutil.copytree(base / "content", admitted / "content")
    receipt = {
        **{key: manifest[key] for key in ("skill_id", "repository", "repository_url", "commit", "license", "content_hash")},
        "status": "ADMITTED", "overlap_decision": overlap_decision, "canonical_owner": canonical_owner,
        "selected_files": rounds[-1]["selected_files"], "optimization_rounds": rounds, "admitted_at": _now(),
        "execution_policy": "read selected files on demand; never execute third-party scripts automatically",
    }
    (admitted / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {**receipt, "admitted_path": str(admitted)}


def domain_skill_status(project_root: str) -> dict[str, Any]:
    root = _state_root(project_root)
    admitted: list[dict[str, Any]] = []
    for path in sorted((root / "admitted").glob("*/receipt.json")) if (root / "admitted").is_dir() else []:
        value = json.loads(path.read_text(encoding="utf-8"))
        content = path.parent / "content"
        value["current_content_hash"] = _tree_hash(content)
        value["integrity"] = "PASS" if value["current_content_hash"] == value.get("content_hash") else "INVALID"
        admitted.append(value)
    return {"status": "PASS", "admitted": admitted, "count": len(admitted)}
