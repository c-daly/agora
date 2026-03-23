# Session Handoff — Experiment Workflow + Agora Batch Implementation

## What we're doing

Two parallel tracks (continued from prior session):

### Track 1: Build the experiment workflow
Improve and automate the agent-swarm `/experiment` workflow. This session added the review phase, fixed subagent tooling, built `/experiment-batch`, and identified critical gaps in the review discipline.

### Track 2: Build Agora (the test workload)
Financial intelligence web app. Four experiments completed: fred_adapter, sec_ftd_adapter, treasury_adapter, yield_curve.

**The inner/outer loop:** Agora tickets run through `/experiment`. When they fail or produce bad results, that's data about what the workflow needs.

## What was done this session

### 1. Fred adapter experiment — full workflow run
- Ran `/experiment-setup` to validate the existing ticket
- Ran `/experiment` manually: read → plan → work → eval → journal → decide
- **13/13 tests passed** first iteration
- Identified missing review phase — filed #84

### 2. Review phase added to experiment workflow
- Added `review` phase between eval and journal in SKILL.md + experiment.yaml
- Reviewer agent checks code quality, security, conventions
- APPROVED → journal. CHANGES_REQUESTED → kickback to work
- Spawned reviewer on fred_adapter — **found 2 major issues** (API key in exceptions, unguarded date parsing)
- Fixed both issues, re-reviewed, APPROVED

### 3. Subagent tooling fixes
- **mcp-call registration bug** — `mcp-call` didn't call `dc.register()` before `dc.call_tool()`. All subagent tool access was broken. Fixed.
- **mcp-call not on PATH** — symlinked `bin/mcp-call` into `.venv/bin/` so subagents can find it
- **experiment not a known workflow** — added to `_KNOWN_WORKFLOWS` in permission_query.py and protocol_assembly.py
- **experiment workflow protocol** — added `WORKFLOW_PROTOCOLS["experiment"]` with phase-specific mcp-call instructions

### 4. Three new experiment tickets created + completed
| Ticket | Type | Tests | Status |
|--------|------|-------|--------|
| sec_ftd_adapter | Flat file adapter (ShortData) | 18/18 | Reviewer found session leak + URL in exceptions |
| treasury_adapter | REST/CSV adapter (TimeSeries) | 21/21 | Reviewer found minor issues (unused import, asymmetric date behavior) |
| yield_curve | Analysis module (fixture-based) | 17/17 | Reviewer found bad test fixture + dead code |

All reviewer findings fixed and committed.

### 5. `/experiment-batch` skill built
- **Design spec**: `docs/superpowers/specs/2026-03-23-experiment-batch-design.md`
- **Implementation plan**: `docs/superpowers/plans/2026-03-23-experiment-batch.md`
- **Library**: `lib/batch_resolver.py` — parse_batch_goal, resolve_tasks, sort_by_dependencies
- **Skill**: `skills/experiment-batch/SKILL.md`
- **Workflow config**: `config/workflows/experiment-batch.yaml`
- **30 tests** across unit + E2E
- Reviewer found **4 real bugs** (task_id collisions, spread overwriting id, silent dependency drop, missing constraints propagation) — all fixed

### 6. Key discoveries about the workflow

**Reviews are non-optional.** When the reviewer agent runs, it finds real bugs every time. When we skip reviews (self-review, bypassPermissions), everything "passes" but has hidden issues. The reviewer is the quality signal.

**"All tests pass" is insufficient.** Tests were mostly happy-path. The reviewer caught issues the tests missed — misleading fixtures, namespace collisions, silent error swallowing.

**Plans that include code are dictation, not engineering.** When the plan contains the complete implementation, the implementer is just copy-pasting. The reviewer then becomes the only real quality gate.

## Decisions made this session

1. **Review phase is mandatory** — eval → review → journal (not eval → journal)
2. **Agents don't merge or close issues** — humans decide what ships
3. **Archiving requires human signoff** — agent reports results, human renames directory when satisfied
4. **Batch goal.yaml uses GitHub search syntax** — `query: "repo:c-daly/agora label:experiment-ready is:open"` passes through to search_issues
5. **Two-level eval hierarchy** — task-level evals (unit tests) gate run-level eval (integration tests)
6. **Per-task goal.yaml in task subdirectories** — keeps run-level goal.yaml small

## What to do next

### Priority 1: Subagent registration (#85)
Background experiment agents currently use `bypassPermissions`. They need proper `prepare_dispatch` → `mcp-call --caller-id` registration so the router can enforce phase permissions. The pieces are all there — just needs wiring.

### Priority 2: Implementation batch skill
Same mechanics as `/experiment-batch` but for production work instead of experiments. Probably just different SKILL.md prompting — "implement and ship" instead of "experiment and learn."

### Priority 3: Ticket discovery from GitHub (#86)
The `query:` field in batch goal.yaml accepts GitHub search syntax. The skill needs to call `search_issues`, parse results into task definitions, and generate per-task goal.yaml files. The issue template already maps 1:1 to goal.yaml fields.

### Deferred
- #82 — Decide phase doesn't check `escalate_if` constraints
- #83 — test_pass_rate metric not synthesized by harness
- Channels + Telegram for always-on agent

## Key files

### Agora (`~/projects/agora`, branch: `main`)
- `agora/adapters/fred_adapter.py` — FRED time series (reviewed, fixed)
- `agora/adapters/sec_ftd_adapter.py` — SEC FTD flat files (reviewed, fixed)
- `agora/adapters/treasury_adapter.py` — Treasury yield curves (reviewed, minor fixes)
- `agora/analysis/yield_curve.py` — spread computation + inversion detection (reviewed, fixed)
- `experiments/*/` — four completed experiments with journals

### Agent-swarm (`~/.claude/plugins/agent-swarm`, branch: `feature/experiment-workflow`)
- `skills/experiment/SKILL.md` — updated with review phase
- `skills/experiment-batch/SKILL.md` — new batch orchestration skill
- `lib/batch_resolver.py` — batch task discovery and resolution (30 tests)
- `lib/protocol_assembly.py` — added experiment workflow protocol + known workflows
- `lib/permission_query.py` — added experiment + experiment-batch to known workflows
- `bin/mcp-call` — fixed registration bug
- `config/workflows/experiment.yaml` — added review phase
- `config/workflows/experiment-batch.yaml` — new batch workflow
- `docs/superpowers/specs/2026-03-23-experiment-batch-design.md` — batch design spec
- `docs/superpowers/plans/2026-03-23-experiment-batch.md` — batch implementation plan

### GitHub issues
- #84 — Experiment workflow needs review phase (implemented)
- #85 — Experiment subagents must use mcp-call with proper registration
- #86 — Experiment batch: pluggable ticket discovery

## User preferences learned
- Reviews are the quality signal — never skip them
- "All tests pass first try" is suspicious, not reassuring
- Agents don't merge or close — humans decide
- Archiving is a human action after signoff
- GitHub search syntax as the universal query interface
- One directory per batch run, per-task subdirs for isolation
- Task unit tests gate integration tests (hard gate)
- Plans describing outcomes > plans dictating code
