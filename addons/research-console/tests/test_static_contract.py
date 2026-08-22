from __future__ import annotations

import re
import unittest
from html.parser import HTMLParser
from pathlib import Path


ADDON = Path(__file__).resolve().parents[1]
STATIC = ADDON / "research_console" / "static"


class ShellParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.inline_scripts = 0
        self.inline_styles = 0
        self.labels: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("id"):
            self.ids.add(str(values["id"]))
        if tag == "script" and not values.get("src"):
            self.inline_scripts += 1
        if tag == "style" or values.get("style"):
            self.inline_styles += 1
        if tag == "label" and values.get("for"):
            self.labels.add(str(values["for"]))


def contrast(first: str, second: str) -> float:
    def luminance(value: str) -> float:
        channels = [int(value[index:index + 2], 16) / 255 for index in (1, 3, 5)]
        linear = [channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4 for channel in channels]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]
    bright, dark = sorted((luminance(first), luminance(second)), reverse=True)
    return (bright + 0.05) / (dark + 0.05)


class StaticContractTests(unittest.TestCase):
    def test_html_uses_only_external_scripts_and_controls_are_labeled(self) -> None:
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        parser = ShellParser()
        parser.feed(html)
        self.assertEqual(parser.inline_scripts, 0)
        self.assertEqual(parser.inline_styles, 0)
        for identifier in ("workspaceInput", "sandboxSelect", "messageInput"):
            self.assertIn(identifier, parser.labels)
        for identifier in ("transcript", "activityLog", "focusOptions", "sendButton", "stopButton"):
            self.assertIn(identifier, parser.ids)

    def test_css_has_responsive_keyboard_and_reduced_motion_contracts(self) -> None:
        css = (STATIC / "styles.css").read_text(encoding="utf-8")
        for token in (
            ":focus-visible", "prefers-reduced-motion", "@media (max-width: 760px)",
            "@media (min-width: 481px) and (max-width: 620px)", "flex-wrap: wrap", "overflow-y: auto",
            "flex: 1 1 160px", "overflow-x: visible",
        ):
            self.assertIn(token, css)
        self.assertGreaterEqual(contrast("#142b31", "#f1f6f4"), 7)
        self.assertGreaterEqual(contrast("#ffffff", "#083f47"), 7)

    def test_javascript_uses_safe_dom_links_and_no_remote_api_or_html_injection(self) -> None:
        script = (STATIC / "app.js").read_text(encoding="utf-8")
        self.assertIn('document.createElement("a")', script)
        self.assertIn('anchor.rel = "noopener noreferrer"', script)
        self.assertNotIn("innerHTML", script)
        self.assertNotIn("eval(", script)
        self.assertNotIn("dangerously-bypass", script)
        domains = re.findall(r"https://[A-Za-z0-9.-]+", script)
        self.assertEqual(domains, [])
        self.assertIn("state.focus.size < 3", script)
        self.assertIn("application/x-ndjson", (STATIC.parent / "server.py").read_text(encoding="utf-8"))

    def test_static_assets_remain_small_and_self_contained(self) -> None:
        files = list(STATIC.iterdir())
        self.assertEqual({path.name for path in files}, {"index.html", "styles.css", "app.js", "mark.svg"})
        self.assertLess(sum(path.stat().st_size for path in files), 300_000)


if __name__ == "__main__":
    unittest.main()
