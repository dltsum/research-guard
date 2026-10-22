# SkillOpt experiment runners

Run the experiment relevant to the change once. Each public
`scripts/skillopt_*.py` experiment defaults to one execution; pass `--rounds N`
only when repeatability is the question being investigated. Running the same
deterministic regression several times does not provide independent scientific
replication. `skillopt_runner.py` is an internal helper, not an experiment CLI.

For example:

```sh
python -X utf8 scripts/skillopt_p16.py --output-root outputs/selection-check
python -X utf8 scripts/skillopt_p16.py --rounds 2 --output-root outputs/repeatability-check
```

Each invocation creates a dated run directory below `--output-root`, writes
one `report.json`, and saves complete standard-output and standard-error logs
for each actual child command. The report records commands, return codes,
test counts, skipped tests, and observed resources. Failed commands remain
failed. Finding no tests does not count as a successful experiment. There is
no separate source-text score, digest seal, or identical per-round report copy.

The thirteen regression entry points share the same small execution helper:

| Entry | Actual regression scope |
| --- | --- |
| `skillopt_bilingual_docs.py` | Documentation, package contents, preset audit |
| `skillopt_ci_migration.py` | Isolated installation, platform and public-package behavior |
| `skillopt_direction_exploration.py` | Research-direction lifecycle |
| `skillopt_frontier_skill_research.py` | Frontier Skill trials and domain-Skill integration |
| `skillopt_instruction_numerical.py` | Instruction handling and numerical verification |
| `skillopt_p16.py` | Module selection and continuation |
| `skillopt_p17.py` | Paper review and figure behavior |
| `skillopt_p18.py` | Active AI-reviewer adaptation |
| `skillopt_p27_macro_paper_spine.py` | Paper-spine planning and collision integration |
| `skillopt_resource_task_planning.py` | Resource planning and process accounting |
| `skillopt_skill_composition.py` | Composition and related portability/frontier integration |
| `skillopt_skill_portability.py` | Transfer and related frontier integration |
| `skillopt_subagent_delegation.py` | Delegation interfaces and execution records |

`skillopt_p12.py` additionally runs a real Optuna TPE search with 18 trials per
requested round. It optimizes review-prioritization parameters on declared
synthetic fixtures, then runs the P12 regression once in one child process
under the actual candidate file. It does not optimize semantic module routing.
Its default is one optimization round. Candidates and the report stay in the
run directory; add `--apply-config` to write an accepted configuration back to
the source configuration after regression passes. No configuration digest or
resume cache is needed. Optuna is required only for this optimization runner.

These are local regression and optimization records. The delegation experiment
does not itself start a native agent, the figure experiment does not perform
a new reference-style generation, and the synthetic P12 fixtures are not user
literature decisions. Full workflow demonstrations need their own actual
inputs and interaction records. Historical multi-round reports describe past
runs and do not prescribe a minimum number of repeats for new changes.
