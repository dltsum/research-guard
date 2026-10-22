# Contributing

Keep changes focused and verify the behavior they affect. A successful local
check establishes only what that check actually exercised.

## Development setup

Use Python 3.11 or newer on Windows x64, Linux x64, or macOS x64/arm64. Install
development dependencies when the selected checks need them:

~~~sh
python -m pip install --isolated --index-url https://pypi.org/simple -r requirements-dev.txt
~~~

Run the tests relevant to the change once. For example:

~~~sh
python -X utf8 scripts/run_incremental_tests.py --pattern "test_p24_frontier_skill_research.py" --suite frontier-skill
~~~

The runner records actual command output and exit status. It does not require
source fingerprints, cached PASS records, or repeated rounds. Rerun after a
repair or when a new concern needs verification. Broaden testing for changes
that span components or for a requested release; ordinary edits do not require
the complete suite. Run intentionally large memory-stress cases separately
from ordinary component checks.

## Bilingual documentation

Update both members when changing shared behavior in a bilingual document.
Review that they communicate the same meaning. The optional readability check
reports missing files or unreadable text:

~~~sh
python -X utf8 scripts/documentation_parity.py
~~~

There is no digest refresh, matching token list, or exact heading requirement.
See [the documentation policy](docs/DOCUMENTATION_POLICY.md) and
[its Chinese version](docs/DOCUMENTATION_POLICY.zh-CN.md).

## Optional Research Console add-on

The UI source lives under addons/research-console/; core archives exclude
that directory. Choose the affected unit, HTTP, bridge, accessibility, or
packaging checks. Inspect the affected layouts when changing visible behavior;
desktop and narrow screenshots are useful when responsive layout is involved.
Check archive exclusion and isolated installation when packaging changes.

SkillOpt is an optional experiment, not a maintenance prerequisite. Its default
is one run; request additional rounds only for a concrete comparison. Build an
archive when preparing a release:

~~~sh
python -X utf8 addons/research-console/build_addon.py --output dist/research-guard-ui-addon.zip
~~~

Update the [UI documentation](docs/RESEARCH_CONSOLE_UI.md) and
[Chinese pair](docs/RESEARCH_CONSOLE_UI.zh-CN.md) for shared behavior changes.
Keep the add-on localhost-only and separate from the core package. Preserve
its existing process ownership, cancellation, and explicit model-call boundary.

## Research and execution boundaries

- Keep source links, useful locators, declared metrics, and actual run results.
  Reassess affected conclusions after a substantive method or source change;
  ordinary file edits do not invalidate a project or require re-registration.
- Do not turn an exit code, bibliographic lookup, capacity check, or static
  scan into a novelty, causal, reproducibility, or safety claim.
- Preserve the user's requested independent reviewers and scientific controls.
  Same-host or same-model evidence does not prove provider independence.
- Reuse canonical owners rather than duplicating tools. Literature adapters
  should expose official record links and unavailable routes clearly.
- Preserve explicit authorization for external APIs, consequential commands,
  and user-owned inclusion or selection decisions. Reuse a working local
  compiler or optional tool directly; no registered dependency receipt is needed.
- Keep configured resource controls on task-owned process trees. Report
  unavailable tools and checks as unavailable or not run.

## Adding an upstream or component

Record the source URL, license, version or revision, purpose, relevant resource
cost, and overlap owner. Inspect the content that will be used. Compare other
implementations when that helps the decision; there is no arbitrary minimum.
Discovery alone does not authorize executing third-party code.

Ordinary installation does not require a SkillOpt study, frontier protocol,
or held-out evaluation. When claiming measured improvement or transfer, design
a suitable comparison, retain negative results, and keep independent evaluation
separate from tuning. See [optional SkillOpt experiments](references/skillopt-experiments.md).

## Pull requests

Describe the resulting behavior and the actual validation command and outcome.
Explain any new network or dependency boundary and update relevant public
documentation. Do not include credentials, private papers, provider responses,
or unreleased research data.
