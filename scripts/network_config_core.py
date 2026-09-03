"""Portable network configuration shared by Research Guard source clients.

The package deliberately does not infer a proxy from the host's ambient
``HTTP_PROXY``/``HTTPS_PROXY`` variables.  A user may opt into a credential-
free foreign-source proxy through ``RESEARCH_GUARD_FOREIGN_PROXY`` or the
installation-time ``network-config.json`` file.  With neither configured,
requests use a direct route.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
from collections.abc import Callable, Iterator
from typing import Mapping


PROXY_ENV = "RESEARCH_GUARD_FOREIGN_PROXY"
DISABLE_DIRECT_FALLBACK_ENV = "RESEARCH_GUARD_DISABLE_FOREIGN_DIRECT_FALLBACK"
CONFIG_FILENAME = "network-config.json"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
_PROXY_VARIABLES = (
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
    "http_proxy", "https_proxy", "all_proxy", "no_proxy",
)
# Package-manager index and configuration variables are also host inputs.  A
# pip invocation with an explicit ``--index-url`` can still be redirected by
# ``PIP_EXTRA_INDEX_URL``, ``PIP_FIND_LINKS`` or a user-local pip config.  Keep
# those values out of every Research Guard child environment; an explicit
# installer argument remains the only way to select a non-default index.
_PACKAGE_INDEX_VARIABLES = (
    "PIP_INDEX_URL", "PIP_EXTRA_INDEX_URL", "PIP_TRUSTED_HOST", "PIP_NO_INDEX",
    "PIP_FIND_LINKS", "PIP_CONFIG_FILE", "PIP_CERT", "PIP_CLIENT_CERT",
    "UV_INDEX_URL", "UV_EXTRA_INDEX_URL", "UV_FIND_LINKS",
)
_PYTHON_HOST_VARIABLES = (
    "PYTHONHOME", "PYTHONPATH", "PYTHONUSERBASE", "PYTHONSTARTUP",
    "PYTHONEXECUTABLE", "PYTHONIOENCODING", "PYTHONWARNINGS",
    "PYTHONBREAKPOINT", "PYTHONUTF8",
)


class NetworkConfigError(ValueError):
    """Raised when an explicit Research Guard network setting is invalid."""


def _home(home: str | os.PathLike[str] | None = None) -> Path:
    if home is not None:
        return Path(home).expanduser().resolve()
    configured = os.environ.get("RESEARCH_GUARD_HOME")
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / ".research-guard").resolve()


def config_path(home: str | os.PathLike[str] | None = None) -> Path:
    """Return the user-scoped network configuration path."""
    return _home(home) / CONFIG_FILENAME


def is_local_endpoint(url: str) -> bool:
    """Return true only for loopback endpoints owned by this process.

    A public domain suffix is never treated as evidence of the user's country.
    In particular, ``.cn`` sources may still use an explicitly selected proxy
    for a user outside China; unset configuration remains a direct attempt.
    """
    host = (urllib.parse.urlsplit(str(url)).hostname or "").casefold()
    return host in LOCAL_HOSTS


def is_domestic_or_local(url: str) -> bool:
    """Compatibility alias; only loopback is automatically local."""
    return is_local_endpoint(url)


def normalize_proxy(value: object, *, label: str = PROXY_ENV) -> str | None:
    """Validate and normalize an optional credential-free HTTP(S) proxy URL."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if any(char.isspace() for char in text):
        raise NetworkConfigError(f"{label} must be a credential-free HTTP(S) proxy URL")
    parsed = urllib.parse.urlsplit(text)
    try:
        port = parsed.port
    except ValueError as exc:
        raise NetworkConfigError(f"{label} must be a credential-free HTTP(S) proxy URL") from exc
    if (
        parsed.scheme.casefold() not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or (port is not None and not 1 <= port <= 65535)
    ):
        raise NetworkConfigError(f"{label} must be a credential-free HTTP(S) proxy URL")
    return text.rstrip("/")


def read_saved_proxy(home: str | os.PathLike[str] | None = None) -> str | None:
    """Read only the installer-owned config file, never ambient proxy vars."""
    path = config_path(home)
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise NetworkConfigError(f"invalid network configuration: {path}") from exc
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise NetworkConfigError(f"invalid network configuration schema: {path}")
    proxy = normalize_proxy(value.get("foreign_proxy"), label=f"{path.name}.foreign_proxy")
    configured = value.get("configured")
    if configured is not None and bool(configured) != bool(proxy):
        raise NetworkConfigError(f"network configuration status does not match foreign_proxy: {path}")
    return proxy


def foreign_proxy_for(url: str, home: str | os.PathLike[str] | None = None) -> str | None:
    """Resolve an explicit proxy for a foreign URL; unset means direct."""
    if is_local_endpoint(url):
        return None
    if PROXY_ENV in os.environ:
        # An explicitly present empty variable intentionally means direct and
        # takes precedence over a saved installer choice for this process.
        return normalize_proxy(os.environ.get(PROXY_ENV))
    return read_saved_proxy(home)


def request_routes(
    url: str,
    home: str | os.PathLike[str] | None = None,
    *,
    proxy_resolver: Callable[[str], str | None] | None = None,
) -> tuple[tuple[str, str | None], ...]:
    """Return deterministic proxy/direct routes for one source request."""
    # ``proxy_resolver`` is a narrow dependency-injection seam for clients
    # that expose a patchable local resolver in tests.  Production callers use
    # the shared resolver above; no caller may fall back to ambient HTTP_PROXY.
    proxy = proxy_resolver(url) if proxy_resolver is not None else foreign_proxy_for(url, home)
    if proxy is None:
        route = "local-direct" if is_local_endpoint(url) else "foreign-direct"
        return ((route, None),)
    routes: list[tuple[str, str | None]] = [("foreign-proxy", proxy)]
    disabled = os.environ.get(DISABLE_DIRECT_FALLBACK_ENV, "").strip().casefold()
    if disabled not in {"1", "true", "yes", "on"}:
        routes.append(("foreign-direct-fallback", None))
    return tuple(routes)


def route_openers(
    url: str,
    home: str | os.PathLike[str] | None = None,
    *,
    proxy_resolver: Callable[[str], str | None] | None = None,
) -> Iterator[tuple[str, str | None, urllib.request.OpenerDirector]]:
    """Yield one proxy-isolated opener per configured route.

    Every opener owns an explicit :class:`ProxyHandler`: an empty handler is
    used for direct routes, so a host's ``HTTP_PROXY``/``HTTPS_PROXY`` cannot
    silently change the route.  Callers should continue to the next yielded
    route only for transport failures and include the route names in their
    receipt/error; HTTP responses are source evidence, not route failures.
    """
    for route_name, proxy in request_routes(url, home, proxy_resolver=proxy_resolver):
        handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy} if proxy else {})
        yield route_name, proxy, urllib.request.build_opener(handler)


def network_environment(
    base: Mapping[str, str] | None = None,
    *,
    proxy: str | None = None,
) -> dict[str, str]:
    """Build a child environment without copying ambient proxy settings."""
    environment = dict(base if base is not None else os.environ)
    for variable in (*_PROXY_VARIABLES, *_PACKAGE_INDEX_VARIABLES, *_PYTHON_HOST_VARIABLES):
        environment.pop(variable, None)
    normalized = normalize_proxy(proxy)
    if normalized:
        environment.update({
            "HTTP_PROXY": normalized,
            "HTTPS_PROXY": normalized,
            "http_proxy": normalized,
            "https_proxy": normalized,
        })
    return environment


def write_network_config(
    proxy: str | None,
    home: str | os.PathLike[str] | None = None,
    *,
    source: str = "installer",
) -> Path:
    """Persist an optional proxy choice atomically without credentials."""
    normalized = normalize_proxy(proxy)
    path = config_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    value = {
        "schema_version": 1,
        "foreign_proxy": normalized,
        "configured": bool(normalized),
        "source": str(source),
        "updated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
    }
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise
    return path
