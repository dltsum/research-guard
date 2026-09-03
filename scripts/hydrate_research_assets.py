from __future__ import annotations

import argparse
import hashlib
import json
import urllib.error
import urllib.request
from pathlib import Path

from ccf_catalog_core import ASSET_ROOT, CATEGORY_SOURCES, write_catalog
from network_config_core import NetworkConfigError, route_openers


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hydrate_ccf(timeout: float = 45) -> dict[str, object]:
    ASSET_ROOT.mkdir(parents=True, exist_ok=True)
    sources: list[dict[str, str]] = []
    for category, url in CATEGORY_SOURCES.items():
        target = ASSET_ROOT / f"{category}.html"
        request = urllib.request.Request(url, headers={"User-Agent": "ResearchGuardHydration/1.0"})
        attempted: list[str] = []
        last_transport: Exception | None = None
        data: bytes | None = None
        route_used: str | None = None
        try:
            for route_name, _proxy, opener in route_openers(url):
                attempted.append(route_name)
                try:
                    with opener.open(request, timeout=timeout) as response:
                        data = response.read()
                except urllib.error.HTTPError as exc:
                    raise RuntimeError(f"CCF request failed via {route_name}: HTTP {exc.code}") from exc
                except (OSError, urllib.error.URLError, TimeoutError) as exc:
                    last_transport = exc
                    continue
                route_used = route_name
                break
        except NetworkConfigError as exc:
            raise RuntimeError(str(exc)) from exc
        if data is None:
            detail = type(last_transport).__name__ if last_transport is not None else "no route completed"
            raise RuntimeError(f"CCF request failed after routes {attempted}: {detail}") from last_transport
        if len(data) < 20_000:
            raise RuntimeError(f"CCF response is unexpectedly small for {category} via {route_used}")
        target.write_bytes(data)
        sources.append({
            "category": category, "url": url, "path": str(target), "sha256": _sha(target),
            "route": str(route_used),
        })
    catalog = write_catalog()
    return {"status": "PASS", "sources": sources, "counts": catalog["counts"], "catalog_sha256": catalog["catalog_sha256"]}


def main() -> int:
    parser = argparse.ArgumentParser(description="Hydrate redistributable-by-link research assets.")
    parser.add_argument("--ccf-v7", action="store_true", help="Download all ten official CCF v7 category pages directly and rebuild the A/B catalog.")
    parser.add_argument("--timeout", type=float, default=45)
    arguments = parser.parse_args()
    if not arguments.ccf_v7:
        parser.error("select --ccf-v7")
    print(json.dumps(hydrate_ccf(arguments.timeout), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
