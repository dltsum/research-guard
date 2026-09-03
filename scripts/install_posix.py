from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dependency_manager import clean_state, cancel_install, resume_install  # noqa: E402
from network_config_core import (  # noqa: E402
    NetworkConfigError,
    config_path,
    network_environment,
    normalize_proxy,
    request_routes,
    read_saved_proxy,
    write_network_config,
)


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_PIP_INDEX = "https://pypi.org/simple"


class InstallError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def _host_platform() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    architecture = "arm64" if machine in {"arm64", "aarch64"} else "x64" if machine in {"x86_64", "amd64"} else machine
    if system not in {"linux", "darwin"} or architecture not in {"x64", "arm64"}:
        raise InstallError(f"Unsupported POSIX platform: {system}-{architecture}")
    if system == "linux" and architecture != "x64":
        raise InstallError("Linux arm64 is not yet an admitted release target")
    return f"{'macos' if system == 'darwin' else 'linux'}-{architecture}"


def _load_manifest() -> dict[str, Any]:
    path = PLUGIN_ROOT / "RELEASE_MANIFEST.json"
    if not path.is_file():
        raise InstallError("RELEASE_MANIFEST.json is required; install from a built release archive")
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("package") != "research-guard" or value.get("runtime_delivery") != "system-python-venv":
        raise InstallError("This installer accepts only a Research Guard system-python-venv release")
    if value.get("platform") != _host_platform():
        raise InstallError(f"Release platform {value.get('platform')} does not match host {_host_platform()}")
    for record in value.get("files", []):
        path = PLUGIN_ROOT / str(record.get("path"))
        if not path.is_file() or path.stat().st_size != int(record.get("bytes", -1)) or _sha256(path) != record.get("sha256"):
            raise InstallError(f"Release file integrity failure: {record.get('path')}")
    return value


def _run(command: list[str], *, env: dict[str, str] | None = None, timeout: int = 1800) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, text=True, capture_output=True, env=env, timeout=timeout, check=False)
    if completed.returncode != 0:
        raise InstallError((completed.stderr or completed.stdout or "command failed")[-4000:])
    return completed


def _resolve_foreign_proxy(
    requested: str | None,
    guard_home: Path,
    *,
    interactive: bool | None = None,
) -> tuple[str | None, bool]:
    """Resolve an install-time choice without importing host proxy settings.

    The boolean reports whether a new choice was made.  An existing saved
    choice is preserved on idempotent install/update runs; a missing choice is
    direct by default when stdin is not interactive or the prompt is skipped.
    """
    if requested is not None:
        try:
            return normalize_proxy(requested), True
        except NetworkConfigError as exc:
            raise InstallError(str(exc)) from exc
    saved_path = config_path(guard_home)
    if saved_path.is_file():
        try:
            return read_saved_proxy(guard_home), False
        except NetworkConfigError as exc:
            raise InstallError(str(exc)) from exc
    if interactive is None:
        interactive = bool(sys.stdin.isatty() and sys.stdout.isatty())
    if interactive:
        try:
            answer = input("Optional foreign-source proxy URL (Enter for direct): ").strip()
        except EOFError:
            answer = ""
        try:
            return normalize_proxy(answer), True
        except NetworkConfigError as exc:
            raise InstallError(str(exc)) from exc
    return None, True


def _install_requirements(
    python: Path,
    requirements: Path,
    preferred_index: str | None,
    *,
    foreign_proxy: str | None = None,
    network_receipt: dict[str, Any] | None = None,
) -> str:
    # Do not infer the installer's package route from the builder's country or
    # host.  Official PyPI direct access is the portable default; a user may
    # explicitly select a domestic/organisation mirror with --pip-index-url.
    indexes = [preferred_index] if preferred_index else [OFFICIAL_PIP_INDEX]
    errors = []
    attempted_routes: list[str] = []
    used_routes: list[str] = []

    def is_transport_failure(detail: str) -> bool:
        """Recognise pip transport failures without retrying package errors.

        A failed proxy can be specific to the installer host (for example a
        Singapore workstation copied from a machine with a local proxy).  The
        direct route is therefore a recovery path, but only for diagnostics
        that identify transport/TLS/DNS failure.  Resolver, version, and HTTP
        response errors remain ordinary install failures.
        """
        return bool(re.search(
            r"(?i)(proxyerror|connecttimeout|readtimeout|failed to establish a new connection|"
            r"connection (?:refused|reset|aborted|timed? out|closed)|max retries exceeded|"
            r"temporary failure in name resolution|name or service not known|could not resolve|"
            r"network is unreachable|no route to host|(?:ssl|tls)(?:error|\s+(?:error|failure|handshake))|"
            r"certificate verify failed|timed? out|could not fetch url|connection broken)",
            detail,
        ))

    for index in indexes:
        if not index:
            continue
        # The resolver is injected with the install-time choice so this
        # package-manager path never consults a host HTTP_PROXY or a second
        # saved setting.  ``request_routes`` still provides the shared
        # explicit-proxy -> direct-fallback policy and honours the opt-out
        # switch for users who intentionally require proxy-only operation.
        routes = request_routes(index, proxy_resolver=lambda _url: foreign_proxy)
        for route_name, proxy in routes:
            attempted_routes.append(route_name)
            command = [
                str(python), "-m", "pip", "install", "--isolated", "--disable-pip-version-check", "--no-input",
            ]
            if proxy:
                # Keep the user-selected route explicit while preventing pip
                # from reading a host pip.conf/pip.ini or ambient PIP_* values.
                command.extend(["--proxy", proxy])
            command.extend(["--index-url", index, "-r", str(requirements)])
            # The proxy is an explicit user choice and is applied to the
            # selected index; ambient proxy and package-index variables are
            # removed for every child process.  No country is inferred from a
            # hostname.
            environment = network_environment(proxy=None)
            try:
                _run(command, env=environment)
                used_routes.append(route_name)
                if network_receipt is not None:
                    network_receipt.update({
                        "network_routes_attempted": list(attempted_routes),
                        "network_routes_used": list(used_routes),
                        "network_route": route_name,
                    })
                return index
            except InstallError as exc:
                detail = str(exc)
                errors.append(f"{index} via {route_name}: {detail}")
                # Only a proxy transport failure may proceed to the explicit
                # direct fallback.  Do not turn HTTP/package-resolution errors
                # into repeated long transactions or misleading diagnostics.
                if route_name != "foreign-proxy" or not is_transport_failure(detail):
                    break
    if network_receipt is not None:
        network_receipt.update({
            "network_routes_attempted": list(attempted_routes),
            "network_routes_used": list(used_routes),
            "network_route": used_routes[-1] if used_routes else None,
        })
    raise InstallError("Core dependency installation failed on every configured index:\n" + "\n".join(errors))


def _copy_plugin(destination: Path) -> None:
    ignored = shutil.ignore_patterns(".git", "dist", "build", "__pycache__", "*.pyc", ".research-guard")
    shutil.copytree(PLUGIN_ROOT, destination, ignore=ignored)


def _write_mcp(plugin: Path, python: Path) -> None:
    value = {"mcpServers": {"research-guard": {
        "command": str(python), "args": ["-X", "utf8", str(plugin / "scripts" / "mcp_server.py")],
    }}}
    (plugin / ".mcp.json").write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _write_marketplace(user_root: Path) -> Path:
    path = user_root / ".agents" / "plugins" / "marketplace.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    else:
        value = {"name": "personal", "interface": {"displayName": "Personal"}, "plugins": []}
    if not isinstance(value, dict) or not isinstance(value.get("plugins"), list):
        raise InstallError(f"Invalid personal marketplace metadata: {path}")
    if value.get("name") != "personal":
        raise InstallError(f"The user-root marketplace must be named personal: {path}")
    others = [item for item in value["plugins"] if isinstance(item, dict) and item.get("name") != "research-guard"]
    others.append({
        "name": "research-guard",
        "source": {"source": "local", "path": "./plugins/research-guard"},
        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
        "category": "Education",
    })
    value["plugins"] = others
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    return path


def _register_codex(user_root: Path) -> str:
    codex = shutil.which("codex")
    if not codex:
        return "CODEX_NOT_FOUND"
    listed = _run([codex, "plugin", "marketplace", "list", "--json"], timeout=120)
    marketplaces = (json.loads(listed.stdout) or {}).get("marketplaces", [])
    roots = {Path(str(item.get("root"))).expanduser().resolve() for item in marketplaces if item.get("root")}
    if user_root not in roots:
        _run([codex, "plugin", "marketplace", "add", str(user_root), "--json"], timeout=120)
    _run([codex, "plugin", "add", "research-guard@personal", "--json"], timeout=120)
    return "REGISTERED"


def install(arguments: argparse.Namespace) -> dict[str, Any]:
    _load_manifest()
    if sys.version_info < (3, 11):
        raise InstallError("Python 3.11 or newer is required")
    user_root = Path(arguments.user_root or Path.home()).expanduser().resolve()
    # Explicit CLI locations win over process settings, which win over the
    # conventional per-user fallback.  This keeps a copied release from
    # silently targeting the host profile that built it.
    guard_home = Path(
        getattr(arguments, "home", None)
        or os.environ.get("RESEARCH_GUARD_HOME")
        or user_root / ".research-guard"
    ).expanduser().resolve()
    codex_home = Path(
        getattr(arguments, "codex_home", None)
        or os.environ.get("CODEX_HOME")
        or user_root / ".codex"
    ).expanduser().resolve()
    foreign_proxy, proxy_choice_made = _resolve_foreign_proxy(
        getattr(arguments, "foreign_proxy", None), guard_home
    )
    plugin_target = user_root / "plugins" / "research-guard"
    skill_target = codex_home / "skills" / "research-guard"
    runtime_target = guard_home / "runtime" / "python"
    for target in (plugin_target, skill_target, runtime_target):
        if target == user_root or user_root not in target.parents:
            raise InstallError(f"Unsafe install target: {target}")
    user_root.mkdir(parents=True, exist_ok=True)
    staging_parent = Path(tempfile.mkdtemp(prefix=".research-guard-install-", dir=user_root))
    staged_plugin = staging_parent / "plugin"
    staged_skill = staging_parent / "skill"
    staged_runtime = staging_parent / "runtime"
    backups: list[tuple[Path, Path]] = []
    swapped: list[Path] = []
    marketplace_path = user_root / ".agents" / "plugins" / "marketplace.json"
    marketplace_original = marketplace_path.read_bytes() if marketplace_path.is_file() else None
    marketplace_touched = False
    network_path = config_path(guard_home)
    network_original = network_path.read_bytes() if network_path.is_file() else None
    network_touched = False
    try:
        _copy_plugin(staged_plugin)
        venv.EnvBuilder(with_pip=True, clear=True).create(staged_runtime)
        python = staged_runtime / "bin" / "python"
        network_receipt: dict[str, Any] = {}
        used_index = _install_requirements(
            python, staged_plugin / "requirements-core.txt", arguments.pip_index_url,
            foreign_proxy=foreign_proxy,
            network_receipt=network_receipt,
        )
        _run([str(python), "-X", "utf8", "-c", "import matplotlib,networkx,numpy,optuna,PIL,pint,psutil,pypdf,yaml,sympy,z3"])
        staged_skill.mkdir(parents=True)
        shutil.copy2(staged_plugin / "SKILL.md", staged_skill / "SKILL.md")
        for directory in ("agents", "references"):
            shutil.copytree(staged_plugin / directory, staged_skill / directory)
        for target, staged in ((plugin_target, staged_plugin), (runtime_target, staged_runtime), (skill_target, staged_skill)):
            target.parent.mkdir(parents=True, exist_ok=True)
            backup = staging_parent / f"backup-{target.name}-{len(backups)}"
            if target.exists():
                target.replace(backup)
                backups.append((target, backup))
            staged.replace(target)
            swapped.append(target)
        installed_python = runtime_target / "bin" / "python"
        _write_mcp(plugin_target, installed_python)
        _run([str(installed_python), "-X", "utf8", str(plugin_target / "scripts" / "dependency_manager.py"), "register-core", str(runtime_target)])
        inventory = _run([str(installed_python), "-X", "utf8", str(plugin_target / "scripts" / "dependency_manager.py"), "inventory", "--json"])
        codex_registration = "SKIPPED_BY_FLAG"
        if not arguments.skip_codex_registration:
            _write_marketplace(user_root)
            marketplace_touched = True
            codex_registration = _register_codex(user_root)
        write_network_config(foreign_proxy, guard_home, source="installer")
        network_touched = True
        return {
            "status": "INSTALLED", "operation": "install",
            "requested_command": getattr(arguments, "command", "install"),
            "platform": _host_platform(), "plugin": str(plugin_target),
            "skill": str(skill_target), "core_runtime": str(runtime_target), "pip_index": used_index,
            "codex_registration": codex_registration,
            "network_proxy": "configured" if foreign_proxy else "direct",
            "network_proxy_choice": "prompt_or_flag" if proxy_choice_made else "preserved",
            **network_receipt,
            "network_config": str(network_path),
            "optional_selection_mode": "on-demand", "dependency_inventory": json.loads(inventory.stdout),
            "next_step": "Start a new agent session and ask it to load research-guard.",
        }
    except Exception:
        if marketplace_touched:
            if marketplace_original is None:
                marketplace_path.unlink(missing_ok=True)
            else:
                marketplace_path.write_bytes(marketplace_original)
        if network_touched:
            if network_original is None:
                network_path.unlink(missing_ok=True)
            else:
                network_path.parent.mkdir(parents=True, exist_ok=True)
                network_path.write_bytes(network_original)
        for target in reversed(swapped):
            if target.exists():
                shutil.rmtree(target)
        for target, backup in reversed(backups):
            if backup.exists():
                backup.replace(target)
        raise
    finally:
        shutil.rmtree(staging_parent, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Install or maintain Research Guard on Linux or macOS")
    parser.add_argument("command", nargs="?", choices=("install", "update", "clean", "hard-clean"), default="install")
    parser.add_argument("--user-root", help="Testing or alternate user root; defaults to the current home")
    parser.add_argument("--project-root", help="Project whose .research-guard session/cache should be cleaned")
    parser.add_argument("--home", help="Research Guard home for dependency/session cleanup")
    parser.add_argument("--codex-home", help="Codex home for plugin/Skill registration during install")
    parser.add_argument("--dry-run", action="store_true", help="Report cleanup candidates without removing them")
    parser.add_argument("--cancel", action="store_true", help="Cancel active install/cleanup units")
    parser.add_argument("--resume", action="store_true", help="Resume saved incomplete install units")
    parser.add_argument("--pip-index-url", help="Use one explicit Python package index; the default is official PyPI direct access")
    parser.add_argument(
        "--foreign-proxy",
        help="Optional credential-free HTTP(S) proxy for foreign sources; omit or pass an empty value for direct access",
    )
    parser.add_argument("--skip-codex-registration", action="store_true", help="Install files and runtime without mutating Codex plugin registration")
    arguments = parser.parse_args()
    try:
        if arguments.command in {"clean", "hard-clean"}:
            value = clean_state(
                arguments.project_root, home=arguments.home, hard=arguments.command == "hard-clean",
                dry_run=arguments.dry_run, cancel=arguments.cancel,
            )
        elif arguments.cancel:
            value = cancel_install()
        elif arguments.resume:
            value = resume_install()
        else:
            value = install(arguments)
        print(json.dumps(value, ensure_ascii=False, indent=2))
    except Exception as exc:
        print(json.dumps({"status": "ERROR", "error": type(exc).__name__, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
