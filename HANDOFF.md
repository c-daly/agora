# Session Handoff — Experiment Setup Skill + Agora Scaffold

## What we're doing

Two parallel tracks (unchanged from prior session):

### Track 1: Build the ticket resolution workflow
Improve and automate the agent-swarm `/experiment` workflow. This session added `/experiment-setup` — a skill that prepares experiment directories before `/experiment` runs.

### Track 2: Build Agora (the test workload)
Financial intelligence web app. Scaffolded at `~/projects/agora` (separate from LOGOS). First ticket (fred_adapter) is ready to run through `/experiment`.

**The inner/outer loop:** Agora tickets run through `/experiment`. When they fail or produce bad results, that's data about what the workflow needs.

## What was done this session

### 1. Agora project scaffold (`~/projects/agora`, branch: `main`)
- **pyproject.toml** — Python 3.11+, FastAPI, Pydantic, NumPy, SciPy
- **agora/schemas/models.py** — Pydantic models: TimeSeries, Filing, Transaction, Quote, ShortData, OptionsSnapshot
- **agora/adapters/**, **analysis/**, **analysis/quant/**, **api/**, **glossary/** — empty packages, ready for components
- **docs/agora-spec.md** — full 175-line spec copied from LOGOS
- **.github/ISSUE_TEMPLATE/agora-task.yml** — ticket template with fields mapping 1:1 to goal.yaml (priority, context, objective, target, success_criteria, eval, environment, notes)
- **experiments/fred_adapter/** — first ticket, ready to run (see below)

### 2. Fred adapter experiment ticket (`~/projects/agora/experiments/fred_adapter/`)
- **goal.yaml** — objective: build FRED adapter returning TimeSeries objects. Target: `agora/adapters/fred_adapter.py`. Success criterion: `test_pass_rate >= 1.0`.
- **constraints.yaml** — interface contract: `fetch_series(series_id, api_key, *, start_date, end_date) -> list[TimeSeries]` from `agora.adapters.fred_adapter`
- **eval/conftest.py** — `fred_api_key` fixture (skips if `FRED_API_KEY` not set), `pytest_terminal_summary` hook emitting `[METRIC] test_pass_rate=<ratio>`
- **eval/test_fred_adapter.py** — 11 tests across 4 classes: SchemaCompliance (6), DateFiltering (4 including empty range), ErrorHandling (2 with match assertions), MissingValues (1)

### 3. `/experiment-setup` skill (`agent-swarm`, branch: `feature/experiment-workflow`)
- **skills/experiment-setup/SKILL.md** — single-shot skill, `user_invocable: true`
- 5-step protocol: validate goal.yaml → read project context → generate constraints.yaml → generate eval scripts → cross-check consistency
- Supports human-driven (interactive, shows output at each step) and agent-driven (autonomous, runs straight through) modes
- Component-type detection from target path (adapter/analysis/quant/visualization) with thoroughness checklists per type
- Design spec: `docs/superpowers/specs/2026-03-23-experiment-setup-design.md`
- Implementation plan: `docs/superpowers/plans/2026-03-23-experiment-setup.md`

### 4. Harness changes (`agent-swarm`, branch: `feature/experiment-workflow`)
- **`escalate_if` type widened** — `list[str]` → `list` (accepts both strings and `{condition, reason}` dicts)
- **`normalize_escalation(entry)`** — converts any escalate_if entry to `{condition, reason}` dict. Strings default to `reason: "error"`.
- **`validate_goal(goal)`** — returns list of error strings. Checks: objective non-empty, success_criteria non-empty, each criterion has metric and threshold.
- **12 new tests** in `tests/test_experiment_harness.py` — all 33 tests passing

### 5. GitHub issues filed
- **agent-swarm #82** — Decide phase does not check `escalate_if` constraints (the SKILL.md says it does, the code doesn't)
- **agent-swarm #83** — test_pass_rate metric not synthesized by harness (eval-side workaround in conftest.py)
- **logos #523** — LOGOS ticket templates not compatible with goal.yaml format

## Decisions made this session

1. **Agora lives at `~/projects/agora`**, not under LOGOS — it's a separate project
2. **Tickets should not prescribe methodology** — the objective describes outcomes, not implementation details. The eval defines the concrete interface contract.
3. **goal.yaml IS the ticket** — the GitHub issue template maps 1:1 to goal.yaml fields. No separate "ticket" abstraction.
4. **Interface contracts go in constraints.yaml** — the agent reads constraints during `read` phase, so it knows what function signatures the eval expects before it starts building
5. **Interactive mode via escalation constraints** — `escalate_if` entries with `reason: routine_checkpoint` at phase transitions, not workflow config changes
6. **`/experiment-setup` and `/ticket-gen` are separate skills** — setup validates/produces artifacts, ticket-gen (future) creates the goal.yaml itself
7. **test_pass_rate solved eval-side** — conftest.py emits `[METRIC] test_pass_rate=<ratio>` via `pytest_terminal_summary` hook, no harness change needed

## What to do next

1. **Restart Claude Code session** so the new `/experiment-setup` skill is discovered (it didn't load after `/reload-plugins`)
2. **Run the fred_adapter ticket through `/experiment`:**
   - `pip install -e .` in `~/projects/agora` so schemas are importable
   - Ensure `FRED_API_KEY` is in the environment
   - Point `/experiment` at `~/projects/agora/experiments/fred_adapter/`
   - Watch what happens — note what breaks and why
3. **After the first ticket:** categorize failures, fix workflow issues, write the next ticket (e.g., `sec_ftd_adapter` — flat file parsing)
4. **agent-swarm #82** blocks interactive mode — escalation checking needs to be implemented in the decide phase
5. **Channels + Telegram** for always-on agent — deferred for now

## Key files

### Agora (`~/projects/agora`)
- `pyproject.toml` — project config
- `agora/schemas/models.py` — all common data schemas
- `docs/agora-spec.md` — full project specification
- `.github/ISSUE_TEMPLATE/agora-task.yml` — ticket template
- `experiments/fred_adapter/goal.yaml` — first ticket
- `experiments/fred_adapter/constraints.yaml` — interface contracts
- `experiments/fred_adapter/eval/` — eval scripts (11 tests)

### Agent-swarm (`~/.claude/plugins/agent-swarm`, branch: `feature/experiment-workflow`)
- `skills/experiment-setup/SKILL.md` — the new skill
- `lib/experiment_harness.py` — `validate_goal()`, `normalize_escalation()`, widened `escalate_if`
- `lib/experiment_workflow.py` — workflow state management (escalation checking NOT yet implemented)
- `skills/experiment/SKILL.md` — the `/experiment` skill that consumes the prepared directories
- `config/workflows/experiment.yaml` — phase permissions
- `docs/superpowers/specs/2026-03-23-experiment-setup-design.md` — design spec
- `docs/superpowers/plans/2026-03-23-experiment-setup.md` — implementation plan

### Relevant repos
- `c-daly/agent-swarm` — workflow enforcement system
- `c-daly/logos` — meta-repo with ticket templates in `.github/`
- `~/projects/agora` — the new financial intelligence project (not yet on GitHub)

## User preferences learned
- Tickets describe outcomes, not methodology
- Focus on progressive automation — manual first, automate patterns once there's data
- Agora is the workload, not the point — the point is perfecting the workflow
- Channels/Telegram deferred — tickets first
- Issues that need tracking go to GitHub (agent-swarm or logos depending on scope)
