# P30 focused work discipline (2026-10-25)

## Scope and upstream decision

The user requested selective integration of Stop That Shit, a source submission,
a reconstruction of Research Guard's interaction design, and current writing /
figure test instructions. The inspected upstream is
[Stop That Shit 0.2.5](https://github.com/lennney/stop-that-shit/tree/0.2.5), MIT.
Only ideas were adapted; no upstream runtime or Skill text was vendored.

The initial local checkout was stale at `4c7bfc7`. Its first 129-test result is
historical evidence only, not validation of current Research Guard. After a
non-fast-forward push rejection, fetched `07ffa6c` and integrated on that base.
The current 2026-10-22 simplification takes precedence: no restored hash gates,
mandatory instruction registration, fixed review counts for ordinary tasks,
edit-triggered invalidation, or new execution-blocking Hook.

## Resulting behavior

- The existing module catalog returns `work_discipline`, explicitly labeled
  `main_agent_guidance` and `runtime_write_blocking=false`.
- Explicit module selection saves the same advisory guidance without inferring
  task modes from keywords or granting additional source-edit authority.
- The lightweight prompt Hook supplies that guidance without scanning project
  files or adding permission denials.
- The language Skill adds reader-consumer judgment for defensive sentences,
  captions and prefaces, while preserving meaningful qualifications.
- The new English/Chinese interaction guide separates ordinary editing from
  qualified-reference writing and reference illustration. It documents actual
  three-agent reviews and seven-class deliverables for those selected workflows.
- A pre-existing figure-Skill word-budget failure was repaired by shortening
  redundant phrasing; no acceptance limit or capability was removed.

## Actual verification

Current-base checks were run once per affected area, with failures repaired or
reported rather than relabeled. Final accepted records cover 22 test files and
155 tests, all passing. They include the new five-case integration contract,
MCP/Hook selection, writing and translation behavior, deterministic figures,
reference-figure contracts, no-digest workflows and bilingual readability.
The first language entrypoint exceeded its existing 60-line budget; shortened
the added guidance and reran that failed module. The current-base figure
entrypoint also exceeded its existing 320-word budget; shortened prose and
reran that module. Earlier failed outputs remain in the local test records.

One additional requested module, `test_reference_writing_contract.py`, was
resource-aborted twice under the unchanged 384 MiB worker profile (measured
384.1 and 389.2 MiB). It has no completed result and is not included in the
155 passed tests. Its assertions are not claimed to have passed. No unrelated
process was killed and no resource policy was weakened. This is a known local
validation limitation, not evidence of a writing-quality improvement.

Root and language Skill frontmatter validation passed. Repository validation
passed with 17 MCP tools, readable bilingual documents and no documentation
warnings. No release archive, plugin reinstall, trust change, paid model call or
empirical model-quality evaluation was performed for this source submission.
