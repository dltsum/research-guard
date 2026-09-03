"""Audit the complete checkout for host-specific presets.

The audit is deliberately deterministic and stdlib-only.  It does not hash
source files, inspect credentials, or infer a user's domain.  It scans ignored
development/evidence files as well as package files, classifies intentional
fixtures and measured runtime evidence, and fails only on a concrete preset
that could silently bind another installation to this host.
"""

from __future__ import annotations

import argparse
import codecs
import json
import os
import re
import sys
import tarfile
import zipfile
from pathlib import Path
from typing import Any, Iterable


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = PLUGIN_ROOT / "assets" / "preset-audit-policy.json"
DEFAULT_BINARY_EXTENSIONS = {
    ".7z", ".bin", ".dll", ".dylib", ".exe", ".gz", ".lib", ".pdb",
    ".pdf", ".png", ".pyc", ".pyd", ".so", ".whl", ".zip",
}
TEXT_SUFFIXES = {
    ".cff", ".cmd", ".conf", ".css", ".csv", ".ini", ".js", ".json",
    ".jsonl", ".md", ".ps1", ".py", ".rev", ".sample", ".sh", ".svg",
    ".txt", ".yaml", ".yml",
}
TEXT_NAMES = {".editorconfig", ".gitattributes", ".gitignore", ".mcp.json", "LICENSE"}
ARCHIVE_SUFFIXES = {
    ".zip", ".whl", ".egg", ".jar", ".vsix", ".nupkg",
    ".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz",
}

WINDOWS_USER_PATH = re.compile(
    r"(?i)(?P<value>[A-Za-z]:[\\/]+(?:Users|Documents and Settings)[\\/]+(?P<user>[^\\/\s\"'<>]+))"
)
POSIX_USER_PATH = re.compile(
    r"(?<![\w:])(?P<value>/(?:Users|home)/(?P<user>[^/\s\"'<>]+))"
)
WINDOWS_ABSOLUTE_PATH = re.compile(
    r"(?<![\w])(?P<value>[A-Za-z]:[\\/]+(?:[^\\/\s\"'<>]+[\\/])*[^\\/\s\"'<>]+)"
)
UNC_PATH = re.compile(
    r"(?P<value>\\\\[A-Za-z0-9._-]+[\\/][A-Za-z0-9._$ -]+(?:[\\/][A-Za-z0-9._$ -]+)*)"
)
POSIX_ABSOLUTE_PATH = re.compile(
    r"(?<![\w:/])(?P<value>/(?:Users|home|tmp|var|opt|usr|private|Volumes|mnt|etc|Library|System)(?:/[^/\s\"'<>]+)+)"
)
LOOPBACK_ENDPOINT = re.compile(
    r"(?i)(?<![\w.-])(?P<value>(?:(?:https?://)(?:127\.0\.0\.1|localhost|0\.0\.0\.0|\[::1\])(?::(?P<port>\d{1,5}))?|(?:127\.0\.0\.1|localhost|0\.0\.0\.0|\[::1\]):(?P<bare_port>\d{1,5})))"
)
PRIVATE_IPV4 = re.compile(
    r"(?<![\d.])(?P<value>(?:10\.(?:\d{1,3}\.){2}\d{1,3}|192\.168\.(?:\d{1,3}\.)\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.(?:\d{1,3}\.)\d{1,3}|169\.254\.(?:\d{1,3}\.)\d{1,3}))(?::\d{1,5})?(?![\d.])"
)
AMBIENT_PROXY_READ = re.compile(
    r"(?i)(?:os\.(?:getenv|environ\.get)|environ\s*\[|GetEnvironmentVariable|Environment\.GetEnvironmentVariable)[^\n]{0,160}(?:HTTP_PROXY|HTTPS_PROXY|ALL_PROXY|NO_PROXY|http_proxy|https_proxy|all_proxy|no_proxy)"
)
AMBIENT_PACKAGE_INDEX_READ = re.compile(
    r"(?i)(?:os\.(?:getenv|environ\.get)|environ\s*\[|GetEnvironmentVariable|Environment\.GetEnvironmentVariable)[^\n]{0,160}(?:PIP_INDEX_URL|PIP_EXTRA_INDEX_URL|PIP_TRUSTED_HOST|PIP_NO_INDEX|PIP_FIND_LINKS|PIP_CONFIG_FILE|PIP_CERT|PIP_CLIENT_CERT|UV_INDEX_URL|UV_EXTRA_INDEX_URL|UV_FIND_LINKS)"
)
AMBIENT_CREDENTIAL_READ = re.compile(
    r"(?i)(?:os\.(?:getenv|environ\.get)|environ\s*\[|GetEnvironmentVariable|Environment\.GetEnvironmentVariable)[^\n]{0,160}(?:[A-Z][A-Z0-9_]*?(?:API[_-]?KEY|TOKEN|EMAIL|SECRET|ACCESS[_-]?KEY))"
)
HARDCODED_PROXY_VALUE = re.compile(
    r"(?i)(?:HTTP_PROXY|HTTPS_PROXY|ALL_PROXY|PIP_INDEX_URL|PIP_EXTRA_INDEX_URL|foreign[_-]?proxy|proxy[_-]?url)\s*(?:=|:)\s*[\"'](?:https?|socks)://"
)
AMBIENT_ENVIRONMENT_INHERITANCE = re.compile(
    r"(?i)(?:dict\s*\(\s*os\.environ\s*\)|os\.environ\.copy\(\)|\{\s*\*\*\s*os\.environ\s*\}|for\s+[^\n]*\s+in\s+os\.environ(?:\.items\(\)|\.keys\(\))?)"
)
HOST_FONT_PRESET = re.compile(
    r"(?i)(?:Arial|Helvetica|Segoe\s+UI|PingFang\s+SC|Microsoft\s+YaHei|"
    r"Palatino\s+Linotype|Iowan\s+Old\s+Style|Songti\s+SC|Cascadia\s+Mono|"
    r"SFMono-Regular|Consolas|Times\s+New\s+Roman|SimHei)"
)
HOST_LOCALE_INFERENCE = re.compile(
    r"(?i)(?:locale\.(?:getdefaultlocale|getlocale)|navigator\.language|"
    r"Intl\.DateTimeFormat\s*\(|time\.tzname|time\.tzset\s*\(|\bTZ\s*=\s*[A-Za-z])"
)

# This is an inventory, not an automatic domain classifier.  It makes every
# host-sensitive mechanism visible in the receipt so a reviewer can inspect
# the source owner and policy boundary.  Findings are still decided by the
# forbidden categories below; the inventory never turns a measured fact into
# a preset by itself.
MECHANISM_PATTERNS: dict[str, tuple[tuple[str, re.Pattern[str]], ...]] = {
    "path_resolution": (
        ("path-home-or-expanduser", re.compile(r"(?i)(?:Path\.home\s*\(|\.expanduser\s*\(|Path\.cwd\s*\(|os\.getcwd\s*\()")),
        ("path-environment-override", re.compile(r"(?i)(?:RESEARCH_GUARD_HOME|RESEARCH_GUARD_CODEX_ROOT|CODEX_HOME|USERPROFILE|LOCALAPPDATA|APPDATA|XDG_CONFIG_HOME|HOME)")),
    ),
    "platform_detection": (
        ("platform-api", re.compile(r"(?i)(?:platform\.(?:system|release|machine|python_version|python_implementation)\s*\(|sys\.platform|os\.name\b|os\.cpu_count\s*\()")),
        ("executable-discovery", re.compile(r"(?i)(?:shutil\.which\s*\(|Get-Command\s+)")),
    ),
    "locale_timezone": (
        ("locale-or-timezone-api", HOST_LOCALE_INFERENCE),
    ),
    "font_selection": (
        ("named-or-generic-font", HOST_FONT_PRESET),
    ),
    "environment_override": (
        ("environment-read", re.compile(r"(?i)(?:os\.getenv\s*\(|os\.environ(?:\.get|\s*\[)|GetEnvironmentVariable|\$env:)")),
    ),
    "network_client": (
        ("python-http-client", re.compile(r"(?i)(?:urllib\.request|urlopen\s*\(|requests\.|httpx\.|aiohttp\.|socket\.)")),
        ("remote-command-client", re.compile(r"(?i)(?:git\s+(?:clone|fetch|ls-remote)|pip\s+install|lake\s+(?:update|exe\s+cache)|Invoke-(?:WebRequest|RestMethod))")),
    ),
    "network_route_control": (
        ("explicit-route-helper", re.compile(r"(?i)(?:request_routes|route_openers|ProxyHandler|network_environment|RESEARCH_GUARD_FOREIGN_PROXY|--proxy)")),
    ),
    "package_index_control": (
        ("explicit-package-index", re.compile(r"(?i)(?:--index-url|--extra-index-url|PIP_(?:INDEX_URL|EXTRA_INDEX_URL|CONFIG_FILE|FIND_LINKS)|UV_(?:INDEX_URL|EXTRA_INDEX_URL|FIND_LINKS))")),
    ),
    "credential_input": (
        ("optional-scholar-credential", re.compile(r"(?i)(?:API[_-]?KEY|ACCESS[_-]?KEY|TOKEN|SECRET|UNPAYWALL_EMAIL|CONTACT_EMAIL)")),
    ),
    "subprocess_launch": (
        ("child-process-launch", re.compile(r"(?i)(?:subprocess\.(?:run|Popen|check_call|check_output)\s*\(|Start-Process|&\s*\$[A-Za-z_][A-Za-z0-9_]*|run_managed(?:_light|_install|_lean)?\s*\()")),
    ),
    "resource_control": (
        ("resource-boundary", re.compile(r"(?i)(?:resource_guard|maximum_parallel_workers|owned_task_budget_bytes|memory_snapshot|MPLBACKEND|(?:OPENBLAS|OMP|MKL|NUMEXPR)_NUM_THREADS|CUDA_VISIBLE_DEVICES|Get-CimInstance\s+Win32_OperatingSystem)")),
    ),
    "archive_lifecycle": (
        ("archive-or-cleanup", re.compile(r"(?i)(?:zipfile|tarfile|ExtractToDirectory|copytree|rmtree|clean_state|hard[-_]clean|\bclean\b)")),
    ),
    "provenance_receipt": (
        ("receipt-or-digest", re.compile(r"(?i)(?:sha256|hash|digest|receipt|provenance|manifest)")),
    ),
}
PLACEHOLDER_SEGMENTS = {
    "user", "username", "name", "your-name", "yourname", "user-name", "userid",
    "<user>", "<username>", "<name>", "%username%", "$user", "${user}",
}


class PresetAuditError(RuntimeError):
    """Raised when the audit policy or root cannot be read."""


def _load_policy(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PresetAuditError(f"preset audit policy is unreadable: {path}: {exc}") from exc
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise PresetAuditError("preset audit policy schema is unsupported")
    return value


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_placeholder(value: str) -> bool:
    candidate = value.strip().casefold()
    return (
        candidate in PLACEHOLDER_SEGMENTS
        or candidate.startswith("<")
        or candidate.startswith("%")
        or candidate.startswith("$")
    )


def _path_is_under(relative: str, prefixes: Iterable[str]) -> bool:
    for prefix in prefixes:
        normalized = str(prefix).replace("\\", "/").strip("/")
        if relative == normalized or relative.startswith(normalized + "/"):
            return True
    return False


def _allowance(relative: str, category: str, policy: dict[str, Any]) -> dict[str, Any] | None:
    # Archive evidence is reported as ``archive.zip::member/path``.  Apply the
    # same intentional-fixture rule to the member path while retaining the
    # archive name in the receipt.
    policy_relative = relative.split("::", 1)[-1]
    candidates: list[str] = [relative]
    if policy_relative not in candidates:
        candidates.append(policy_relative)
    # Release archives commonly contain one top-level package directory
    # (``research-guard/...``).  Compare that normalized member path too, so
    # the same source allowlist is applied inside and outside the archive.
    member_parts = Path(policy_relative).parts
    if "::" in relative and len(member_parts) > 1:
        unwrapped = Path(*member_parts[1:]).as_posix()
        if unwrapped not in candidates:
            candidates.append(unwrapped)
    for rule in policy.get("allowlist", []):
        if not isinstance(rule, dict):
            continue
        categories = rule.get("categories") or []
        if category in categories and any(
            _path_is_under(candidate, rule.get("path_prefixes") or []) for candidate in candidates
        ):
            return {
                "id": str(rule.get("id") or "unnamed"),
                "reason": str(rule.get("reason") or "intentional policy exception"),
            }
    return None


def _redact(text: str) -> str:
    text = WINDOWS_USER_PATH.sub("<user-home>", text)
    text = POSIX_USER_PATH.sub("<user-home>", text)
    text = re.sub(r"(?i)(https?://)([^/@\s]+):([^/@\s]+)@", r"\1<credentials-redacted>@", text)
    return text


def _evidence(relative: str, line_number: int, line: str, matched: str, *, max_chars: int) -> dict[str, Any]:
    return {
        "path": relative,
        "line": line_number,
        "match": _redact(matched)[:max_chars],
        "snippet": _redact(line.strip())[:max_chars],
    }


def _record_mechanisms(
    inventory: dict[str, dict[str, Any]],
    relative: str,
    line_number: int,
    line: str,
    *,
    max_examples: int,
) -> None:
    """Record mechanism coverage without copying source values into receipts."""
    for category, patterns in MECHANISM_PATTERNS.items():
        for pattern_id, pattern in patterns:
            match = pattern.search(line)
            if match is None:
                continue
            item = inventory.setdefault(category, {"occurrences": 0, "files": set(), "patterns": {}, "examples": []})
            item["occurrences"] += 1
            item["files"].add(relative)
            item["patterns"][pattern_id] = int(item["patterns"].get(pattern_id, 0)) + 1
            if len(item["examples"]) < max_examples:
                # A pattern id and location are enough for review.  Do not
                # retain the matched value: a credential-like source line may
                # contain a user token or email next to the variable name.
                item["examples"].append({"path": relative, "line": line_number, "pattern": pattern_id})


def _finalize_mechanisms(inventory: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    finalized: list[dict[str, Any]] = []
    for category in sorted(inventory):
        item = inventory[category]
        finalized.append({
            "category": category,
            "occurrences": int(item["occurrences"]),
            "files": sorted(str(path) for path in item["files"]),
            "patterns": {key: int(item["patterns"][key]) for key in sorted(item["patterns"])},
            "examples": sorted(item["examples"], key=lambda value: (value["path"], value["line"], value["pattern"])),
        })
    return finalized


def _iter_files(root: Path) -> Iterable[Path]:
    if not root.is_dir():
        raise PresetAuditError(f"audit root is not a directory: {root}")
    for directory, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        current = Path(directory)
        retained_dirs: list[str] = []
        for name in sorted(dirnames):
            if name == ".git":
                continue
            candidate = current / name
            # Surface directory links as entries so the audit never silently
            # omits a link to a host-specific tree.  Normal directories remain
            # the only entries that os.walk descends into.
            if candidate.is_symlink():
                yield candidate
            else:
                retained_dirs.append(name)
        dirnames[:] = retained_dirs
        for name in sorted(filenames):
            yield current / name


def _matches_ignored_pattern(relative: str) -> bool:
    """Mirror the repository's generated-file patterns for the opt-out mode."""
    parts = Path(relative).parts
    if not parts:
        return False
    if parts[0] in {"build", "dist", "evals", ".research-guard"}:
        return True
    if parts[:2] == ("docs", "development"):
        return True
    if "snapshots" in parts or "quarantine" in parts or "admitted" in parts:
        return True
    if parts[:2] == ("assets", "payloads"):
        return True
    if parts[:2] == ("assets", "venue-evidence") and Path(relative).suffix.casefold() in {".html", ".pdf", ".zip"}:
        return True
    return False


def _is_generated_audit_receipt(relative: str) -> bool:
    """Avoid recursively scanning the receipt that this command is writing."""
    path = Path(relative)
    return (
        ".research-guard" in path.parts
        and path.suffix.casefold() == ".json"
        and path.name.casefold().startswith("preset-audit")
    )


def _is_preset_audit_source(relative: str) -> bool:
    """Recognize this scanner itself both unpacked and inside a release ZIP."""
    member = relative.split("::", 1)[-1].replace("\\", "/")
    return member == "scripts/preset_audit.py" or member.endswith("/scripts/preset_audit.py")


def _is_binary(path: Path, binary_extensions: set[str]) -> tuple[bool, str]:
    if path.suffix.casefold() in binary_extensions:
        return True, "extension"
    try:
        with path.open("rb") as handle:
            sample = handle.read(8192)
    except OSError as exc:
        return False, f"read-error:{exc}"
    if b"\x00" in sample:
        return True, "nul-byte"
    try:
        # A fixed byte sample can end in the middle of a CJK UTF-8 sequence.
        # Keep an incomplete tail in the decoder state so valid text is not
        # misclassified as non-UTF-8 merely because of the sample boundary.
        decoder = codecs.getincrementaldecoder("utf-8")()
        decoder.decode(sample, final=False)
    except UnicodeDecodeError:
        return True, "non-utf8"
    return False, ""


def _record_finding(
    findings: list[dict[str, Any]],
    allowed: list[dict[str, Any]],
    *,
    category: str,
    relative: str,
    line_number: int,
    line: str,
    matched: str,
    policy: dict[str, Any],
    max_chars: int,
) -> None:
    record = {
        "category": category,
        **_evidence(relative, line_number, line, matched, max_chars=max_chars),
    }
    exception = _allowance(relative, category, policy)
    if exception:
        record["allowance"] = exception
        allowed.append(record)
    else:
        findings.append(record)


def _scan_text_lines(
    relative: str,
    lines: Iterable[str],
    policy: dict[str, Any],
    findings: list[dict[str, Any]],
    allowed: list[dict[str, Any]],
    portable: list[dict[str, Any]],
    inventory: dict[str, dict[str, Any]] | None = None,
) -> None:
    max_chars = int((policy.get("scan") or {}).get("line_evidence_max_characters", 240))
    max_examples = int((policy.get("scan") or {}).get("mechanism_examples_max", 8))
    for line_number, line in enumerate(lines, start=1):
        if inventory is not None:
            _record_mechanisms(inventory, relative, line_number, line, max_examples=max_examples)
        user_spans: list[tuple[int, int]] = []
        for match in WINDOWS_USER_PATH.finditer(line):
            user_spans.append((match.start(), match.end()))
            if not _is_placeholder(match.group("user")):
                _record_finding(
                    findings, allowed, category="literal_user_path", relative=relative,
                    line_number=line_number, line=line, matched=match.group("value"),
                    policy=policy, max_chars=max_chars,
                )
        for match in POSIX_USER_PATH.finditer(line):
            user_spans.append((match.start(), match.end()))
            if not _is_placeholder(match.group("user")):
                _record_finding(
                    findings, allowed, category="literal_user_path", relative=relative,
                    line_number=line_number, line=line, matched=match.group("value"),
                    policy=policy, max_chars=max_chars,
                )
        if not _is_preset_audit_source(relative):
            for pattern in (WINDOWS_ABSOLUTE_PATH, UNC_PATH, POSIX_ABSOLUTE_PATH):
                for match in pattern.finditer(line):
                    if any(match.start() < end and start < match.end() for start, end in user_spans):
                        continue
                    value = match.group("value")
                    # TeX control sequences such as ``r"\\title\\s"`` and
                    # generated compiler logs can look like a two-segment UNC
                    # path.  Treat a UNC-shaped token as a host path only when
                    # its surrounding text declares path/network semantics;
                    # explicit ``UNC = ...`` fixtures remain detectable.
                    if pattern is UNC_PATH and re.match(r"^\\\\[A-Za-z]+\\[A-Za-z](?:$|[^A-Za-z])", value):
                        context = line.casefold()
                        path_context = re.search(
                            r"(?:unc|network|path|file|directory|folder|share|mount|windows|server|root)",
                            context,
                        )
                        if path_context is None:
                            continue
                    # ``/usr/bin/env`` is a portable shebang resolver.  It is
                    # recorded as a portable convention rather than treated as
                    # a fixed installation path, including embedded test text.
                    if value == "/usr/bin/env" and "#!/usr/bin/env" in line:
                        portable.append({
                            "id": "portable-posix-shebang",
                            "pattern": value,
                            "path": relative,
                            "line": line_number,
                            "reason": "portable shebang resolver",
                        })
                        continue
                    _record_finding(
                        findings, allowed, category="literal_absolute_path", relative=relative,
                        line_number=line_number, line=line, matched=value,
                        policy=policy, max_chars=max_chars,
                    )
        for match in LOOPBACK_ENDPOINT.finditer(line):
            port = match.group("port") or match.group("bare_port")
            if port is None or int(port) != 0:
                _record_finding(
                    findings, allowed, category="fixed_local_endpoint", relative=relative,
                    line_number=line_number, line=line, matched=match.group("value"),
                    policy=policy, max_chars=max_chars,
                )
        for match in PRIVATE_IPV4.finditer(line):
            _record_finding(
                findings, allowed, category="private_network_endpoint", relative=relative,
                line_number=line_number, line=line, matched=match.group("value"),
                policy=policy, max_chars=max_chars,
            )
        if AMBIENT_PROXY_READ.search(line) and relative not in {"scripts/network_config_core.py", "scripts/preset_audit.py"} and not _is_preset_audit_source(relative):
            _record_finding(
                findings, allowed, category="ambient_proxy_read", relative=relative,
                line_number=line_number, line=line, matched=AMBIENT_PROXY_READ.search(line).group(0),
                policy=policy, max_chars=max_chars,
            )
        package_index_match = AMBIENT_PACKAGE_INDEX_READ.search(line)
        if package_index_match and relative not in {"scripts/network_config_core.py", "scripts/preset_audit.py"} and not _is_preset_audit_source(relative):
            _record_finding(
                findings, allowed, category="ambient_package_index_read", relative=relative,
                line_number=line_number, line=line, matched=package_index_match.group(0),
                policy=policy, max_chars=max_chars,
            )
        credential_match = AMBIENT_CREDENTIAL_READ.search(line)
        if credential_match and not _is_preset_audit_source(relative):
            _record_finding(
                findings, allowed, category="ambient_credential_read", relative=relative,
                line_number=line_number, line=line, matched=credential_match.group(0),
                policy=policy, max_chars=max_chars,
            )
        proxy_match = HARDCODED_PROXY_VALUE.search(line)
        if proxy_match:
            _record_finding(
                findings, allowed, category="hardcoded_proxy_value", relative=relative,
                line_number=line_number, line=line, matched=proxy_match.group(0),
                policy=policy, max_chars=max_chars,
            )
        inheritance_match = AMBIENT_ENVIRONMENT_INHERITANCE.search(line)
        if inheritance_match:
            _record_finding(
                findings, allowed, category="ambient_environment_inheritance", relative=relative,
                line_number=line_number, line=line, matched=inheritance_match.group(0),
                policy=policy, max_chars=max_chars,
            )
        font_match = HOST_FONT_PRESET.search(line) if re.search(
            r"(?i)(?:font(?:[-_.]|\s)|font-family|rcparams|matplotlib\.rc)", line
        ) else None
        if font_match:
            _record_finding(
                findings, allowed, category="host_font_preset", relative=relative,
                line_number=line_number, line=line, matched=font_match.group(0),
                policy=policy, max_chars=max_chars,
            )
        locale_match = HOST_LOCALE_INFERENCE.search(line) if relative.split("::", 1)[-1] != "scripts/preset_audit.py" else None
        if locale_match:
            _record_finding(
                findings, allowed, category="host_locale_inference", relative=relative,
                line_number=line_number, line=line, matched=locale_match.group(0),
                policy=policy, max_chars=max_chars,
            )

        for default in policy.get("portable_defaults", []):
            if not isinstance(default, dict):
                continue
            for pattern in default.get("patterns") or []:
                if str(pattern) in line:
                    portable.append({
                        "id": str(default.get("id") or "unnamed"),
                        "pattern": str(pattern),
                        "path": relative,
                        "line": line_number,
                        "reason": str(default.get("reason") or "portable default"),
                    })


def _scan_text_file(
    root: Path,
    path: Path,
    policy: dict[str, Any],
    findings: list[dict[str, Any]],
    allowed: list[dict[str, Any]],
    portable: list[dict[str, Any]],
    inventory: dict[str, dict[str, Any]] | None = None,
) -> None:
    relative = _relative(root, path)
    try:
        handle = path.open("r", encoding="utf-8", errors="strict")
    except (OSError, UnicodeError) as exc:
        findings.append({"category": "scan_error", "path": relative, "error": str(exc)})
        return
    with handle:
        _scan_text_lines(relative, handle, policy, findings, allowed, portable, inventory)


def _scan_archive(
    root: Path,
    path: Path,
    policy: dict[str, Any],
    findings: list[dict[str, Any]],
    allowed: list[dict[str, Any]],
    portable: list[dict[str, Any]],
    skipped: list[dict[str, str]],
    archive_stats: dict[str, int],
    inventory: dict[str, dict[str, Any]] | None = None,
) -> None:
    relative = _relative(root, path)
    limit = int((policy.get("scan") or {}).get("archive_member_max_bytes", 4 * 1024 * 1024))
    try:
        archive = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as exc:
        skipped.append({"path": relative, "reason": f"archive-unreadable:{exc}"})
        return
    with archive:
        member_limit = int((policy.get("scan") or {}).get("archive_member_count_max", 10000))
        for member_index, member in enumerate(archive.infolist()):
            if member_index >= member_limit:
                skipped.append({"path": relative, "reason": "archive-member-count-limit"})
                archive_stats["members_skipped"] += 1
                break
            if member.is_dir():
                continue
            member_path = f"{relative}::{member.filename}"
            if member.file_size > limit:
                skipped.append({"path": member_path, "reason": "archive-member-too-large"})
                archive_stats["members_skipped"] += 1
                continue
            try:
                data = archive.read(member)
                text = data.decode("utf-8")
            except (OSError, UnicodeError, RuntimeError, zipfile.BadZipFile) as exc:
                skipped.append({"path": member_path, "reason": f"archive-member-nontext:{type(exc).__name__}"})
                archive_stats["members_skipped"] += 1
                continue
            archive_stats["members_scanned"] += 1
            archive_stats["bytes_scanned"] += len(data)
            _scan_text_lines(member_path, text.splitlines(keepends=True), policy, findings, allowed, portable, inventory)


def _scan_tar_archive(
    root: Path,
    path: Path,
    policy: dict[str, Any],
    findings: list[dict[str, Any]],
    allowed: list[dict[str, Any]],
    portable: list[dict[str, Any]],
    skipped: list[dict[str, str]],
    archive_stats: dict[str, int],
    inventory: dict[str, dict[str, Any]] | None = None,
) -> None:
    """Inspect text members of tar-family archives without extracting them."""
    relative = _relative(root, path)
    limit = int((policy.get("scan") or {}).get("archive_member_max_bytes", 4 * 1024 * 1024))
    try:
        archive = tarfile.open(path, mode="r:*")
    except (OSError, tarfile.TarError) as exc:
        skipped.append({"path": relative, "reason": f"archive-unreadable:{exc}"})
        return
    with archive:
        member_limit = int((policy.get("scan") or {}).get("archive_member_count_max", 10000))
        for member_index, member in enumerate(archive.getmembers()):
            if member_index >= member_limit:
                skipped.append({"path": relative, "reason": "archive-member-count-limit"})
                archive_stats["members_skipped"] += 1
                break
            member_path = f"{relative}::{member.name}"
            if member.isdir():
                continue
            if not member.isfile():
                skipped.append({"path": member_path, "reason": "archive-member-nonregular"})
                archive_stats["members_skipped"] += 1
                continue
            if member.size > limit:
                skipped.append({"path": member_path, "reason": "archive-member-too-large"})
                archive_stats["members_skipped"] += 1
                continue
            try:
                extracted = archive.extractfile(member)
                data = extracted.read() if extracted is not None else b""
                text = data.decode("utf-8")
            except (OSError, UnicodeError, tarfile.TarError) as exc:
                skipped.append({"path": member_path, "reason": f"archive-member-nontext:{type(exc).__name__}"})
                archive_stats["members_skipped"] += 1
                continue
            archive_stats["members_scanned"] += 1
            archive_stats["bytes_scanned"] += len(data)
            _scan_text_lines(member_path, text.splitlines(keepends=True), policy, findings, allowed, portable, inventory)
def _read_json(root: Path, relative: str) -> dict[str, Any]:
    path = root / Path(relative)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PresetAuditError(f"required policy binding is unreadable: {relative}: {exc}") from exc
    if not isinstance(value, dict):
        raise PresetAuditError(f"required policy binding must be an object: {relative}")
    return value


def _policy_bindings(root: Path, policy: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    violations: list[dict[str, Any]] = []
    bindings = policy.get("required_policy_bindings") or {}
    resource = bindings.get("resource_policy") or {}
    resource_path = str(resource.get("path") or "")
    try:
        resource_value = _read_json(root, resource_path)
    except PresetAuditError as exc:
        violations.append({"category": "policy_binding", "path": resource_path, "error": str(exc)})
    else:
        checks = {
            "maximum_parallel_workers": resource_value.get("maximum_parallel_workers"),
            "gpu_allowed": resource_value.get("gpu_allowed"),
            "execution_mode": resource_value.get("execution_mode"),
        }
        expected = {
            "maximum_parallel_workers": resource.get("maximum_parallel_workers"),
            "gpu_allowed": resource.get("gpu_allowed"),
            "execution_mode": resource.get("execution_mode"),
        }
        if int(resource_value.get("owned_task_budget_bytes", 0)) > int(resource.get("owned_task_budget_bytes_max", 0)):
            violations.append({"category": "policy_binding", "path": resource_path, "key": "owned_task_budget_bytes", "actual": resource_value.get("owned_task_budget_bytes"), "expected_max": resource.get("owned_task_budget_bytes_max")})
        for key, actual in checks.items():
            if actual != expected[key]:
                violations.append({"category": "policy_binding", "path": resource_path, "key": key, "actual": actual, "expected": expected[key]})
        records.append({"id": "resource_policy", "path": resource_path, "status": "PASS", "values": checks})

    delegation = bindings.get("llm_delegation_policy") or {}
    delegation_path = str(delegation.get("path") or "")
    try:
        delegation_value = _read_json(root, delegation_path)
    except PresetAuditError as exc:
        violations.append({"category": "policy_binding", "path": delegation_path, "error": str(exc)})
    else:
        keys = (
            "default_execution_mode", "default_reasoning_effort", "maximum_reasoning_effort",
            "maximum_parallel_subagents", "external_api_default_allowed",
        )
        actual = {key: delegation_value.get(key) for key in keys}
        expected = {key: delegation.get(key) for key in keys}
        for key in keys:
            if actual[key] != expected[key]:
                violations.append({"category": "policy_binding", "path": delegation_path, "key": key, "actual": actual[key], "expected": expected[key]})
        records.append({"id": "llm_delegation_policy", "path": delegation_path, "status": "PASS", "values": actual})

    network = bindings.get("network_policy") or {}
    network_path = str(network.get("path") or "")
    try:
        network_text = (root / Path(network_path)).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        violations.append({"category": "policy_binding", "path": network_path, "error": str(exc)})
    else:
        required_tokens = (
            "RESEARCH_GUARD_FOREIGN_PROXY", "read_saved_proxy", "network_environment",
            "_PACKAGE_INDEX_VARIABLES", "PIP_EXTRA_INDEX_URL", "PIP_CONFIG_FILE",
        )
        missing = [token for token in required_tokens if token not in network_text]
        if missing:
            violations.append({"category": "policy_binding", "path": network_path, "key": "explicit_network_inputs", "missing": missing})
        records.append({"id": "network_policy", "path": network_path, "status": "PASS", "values": {"explicit_proxy_input": True, "unset_foreign_proxy_route": network.get("unset_foreign_proxy_route")}})

    boundary = bindings.get("runtime_boundary") or {}
    boundary_records: list[dict[str, Any]] = []
    for item in boundary.get("files") or []:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "")
        optional = bool(item.get("optional", False))
        if optional and not (root / Path(path)).is_file():
            boundary_records.append({"path": path, "status": "SKIPPED_OPTIONAL", "required_tokens": list(item.get("required_tokens") or [])})
            continue
        try:
            text = (root / Path(path)).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            violations.append({"category": "policy_binding", "path": path, "error": str(exc)})
            continue
        missing = [str(token) for token in item.get("required_tokens") or [] if str(token) not in text]
        if missing:
            violations.append({"category": "policy_binding", "path": path, "key": "runtime_boundary", "missing": missing})
        boundary_records.append({"path": path, "status": "PASS" if not missing else "FAIL", "required_tokens": list(item.get("required_tokens") or [])})
    if boundary_records:
        records.append({"id": "runtime_boundary", "status": "PASS" if all(item["status"] in {"PASS", "SKIPPED_OPTIONAL"} for item in boundary_records) else "FAIL", "files": boundary_records})
    return records, violations


def audit_repository(
    root: str | os.PathLike[str] | Path = PLUGIN_ROOT,
    *,
    policy_path: str | os.PathLike[str] | Path | None = None,
    include_ignored: bool = True,
) -> dict[str, Any]:
    """Scan every non-Git file and return a portable, redacted audit receipt."""
    resolved_root = Path(root).expanduser().resolve()
    policy = _load_policy(Path(policy_path).expanduser().resolve() if policy_path else DEFAULT_POLICY)
    findings: list[dict[str, Any]] = []
    allowed: list[dict[str, Any]] = []
    portable: list[dict[str, Any]] = []
    mechanism_inventory: dict[str, dict[str, Any]] = {}
    skipped: list[dict[str, str]] = []
    scan_errors: list[dict[str, str]] = []
    scanned_files = 0
    scanned_bytes = 0
    archive_stats = {"archives_scanned": 0, "members_scanned": 0, "members_skipped": 0, "bytes_scanned": 0}
    generated_receipts_skipped = 0
    symlink_entries_skipped = 0
    binary_extensions = set(str(item).casefold() for item in (policy.get("scan") or {}).get("binary_extensions", [])) or DEFAULT_BINARY_EXTENSIONS

    for path in _iter_files(resolved_root):
        relative = _relative(resolved_root, path)
        if not include_ignored and _matches_ignored_pattern(relative):
            continue
        if _is_generated_audit_receipt(relative):
            skipped.append({"path": relative, "reason": "self-referential-audit-receipt"})
            generated_receipts_skipped += 1
            continue
        if path.is_symlink():
            skipped.append({"path": relative, "reason": "symlink-not-followed"})
            symlink_entries_skipped += 1
            continue
        try:
            size = path.stat().st_size
        except OSError as exc:
            scan_errors.append({"path": relative, "error": str(exc)})
            continue
        binary, reason = _is_binary(path, binary_extensions)
        if reason.startswith("read-error:"):
            scan_errors.append({"path": relative, "error": reason})
            continue
        if binary:
            archive_name = path.name.casefold()
            if archive_name.endswith((".zip", ".whl", ".egg", ".jar", ".vsix", ".nupkg")):
                archive_stats["archives_scanned"] += 1
                _scan_archive(
                    resolved_root, path, policy, findings, allowed, portable,
                    skipped, archive_stats, mechanism_inventory,
                )
            elif archive_name.endswith((".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz")):
                archive_stats["archives_scanned"] += 1
                _scan_tar_archive(
                    resolved_root, path, policy, findings, allowed, portable,
                    skipped, archive_stats, mechanism_inventory,
                )
            skipped.append({"path": relative, "reason": reason})
            continue
        scanned_files += 1
        scanned_bytes += size
        _scan_text_file(resolved_root, path, policy, findings, allowed, portable, mechanism_inventory)

    bindings, binding_violations = _policy_bindings(resolved_root, policy)
    findings.extend(binding_violations)
    findings.extend({"category": "scan_error", **item} for item in scan_errors)
    status = "PASS" if not findings else "FAIL"
    return {
        "schema_version": 1,
        "policy_id": policy.get("policy_id"),
        "status": status,
        "root": resolved_root.name,
        "include_ignored_files": bool(include_ignored),
        "scope": (
            "complete checkout excluding .git; ignored runtime/evaluation files are classified, not silently omitted"
            if include_ignored else
            "package-oriented checkout excluding .git and repository-generated ignored paths"
        ),
        "scan": {
            "files_scanned": scanned_files,
            "bytes_scanned": scanned_bytes,
            "binary_or_non_utf8_files_skipped": len(skipped),
            "symlink_entries_skipped": symlink_entries_skipped,
            "scan_errors": len(scan_errors),
            "generated_audit_receipts_skipped": generated_receipts_skipped,
            "archives_inspected": archive_stats["archives_scanned"],
            "archive_entries_scanned": archive_stats["members_scanned"],
            "archive_entries_skipped": archive_stats["members_skipped"],
            "archive_text_bytes_scanned": archive_stats["bytes_scanned"],
        },
        "violations": findings,
        "allowed_findings": allowed,
        "portable_defaults": portable,
        "mechanism_inventory": _finalize_mechanisms(mechanism_inventory),
        "policy_bindings": bindings,
        "skipped_files": skipped,
        "next_action": "Correct every violation and rerun; allowed findings are intentional fixtures/evidence only." if findings else "No host-specific preset was found; keep this receipt with the release/development checkpoint.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit all checkout files for machine-specific Research Guard presets.")
    parser.add_argument("--root", type=Path, default=PLUGIN_ROOT, help="Repository root to scan (default: this checkout)")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY, help="Preset-audit policy JSON")
    parser.add_argument("--output", type=Path, help="Optional JSON receipt path")
    parser.add_argument("--no-ignored", action="store_true", help="Exclude ignored files (not recommended for full audit)")
    arguments = parser.parse_args(argv)
    try:
        report = audit_repository(arguments.root, policy_path=arguments.policy, include_ignored=not arguments.no_ignored)
    except (PresetAuditError, OSError, ValueError) as exc:
        print(json.dumps({"status": "FAIL", "error": type(exc).__name__, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        arguments.output.expanduser().resolve().write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
