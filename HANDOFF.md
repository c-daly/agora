# Session Handoff — Experiment Workflow + Agora POC

## What we're doing

Two parallel tracks:

### Track 1: Build the experiment workflow
Agent-swarm `/experiment` workflow with review phase, batch execution, and proper subagent registration.

### Track 2: Build Agora (the test workload)
Financial intelligence web app. Four adapters/analysis modules done. POC epic filed and set up — ready to execute.

**The inner/outer loop:** Agora tickets run through `/experiment`. When they fail or produce bad results, that's data about what the workflow needs.

## What to do next

### Run the POC batch

Everything is set up and ready:

```
experiments/poc/
  goal.yaml              # 6 tasks with dependencies
  tasks/
    api_routes/          # FastAPI routes (42 pytest tests ready)
    glossary_data/       # Static YAML glossary (schema validation tests)
    webapp_scaffold/     # React + Vite + yield curve viz (vitest + pytest bridge)
    ftd_heatmap/         # FTD visualization component
    macro_grid/          # Macro indicator grid
    glossary_tooltips/   # Tooltip integration
```

Execution order (from dependency sort):
- **Wave 1 (parallel):** api_routes, glossary_data
- **Wave 2:** webapp_scaffold (needs api_routes)
- **Wave 3 (parallel):** ftd_heatmap, macro_grid, glossary_tooltips

Run with: `/experiment-batch experiments/poc/`

GitHub issues: c-daly/agora #1 (epic), #2-#7 (tasks)

### Known gaps to watch for

1. **`/experiment-setup` doesn't walk batch directories** — it handles one goal.yaml, not `tasks/*/goal.yaml`. Needs a small update to detect and iterate subdirectories.
2. **Frontend eval is uncharted** — vitest tests exist but the harness expects pytest `[METRIC]` output. Pytest bridge scripts were generated but are untested.
3. **Subagent registration (#85)** — experiment runners still use `bypassPermissions`. Proper mcp-call registration is the priority fix.
4. **Reviews must actually run** — this session proved reviews find real bugs every time, but I skipped them during subagent-driven-development. Non-negotiable going forward.

## What was done this session

### Completed experiments (4)
| Ticket | Type | Tests | Reviewed |
|--------|------|-------|----------|
| fred_adapter | REST adapter | 13/13 | Yes — 2 bugs found, fixed |
| sec_ftd_adapter | Flat file adapter | 18/18 | Yes — session leak found, fixed |
| treasury_adapter | REST/CSV adapter | 21/21 | Yes — minor issues found, fixed |
| yield_curve | Analysis module | 17/17 | Yes — bad fixture found, fixed |

### Workflow improvements
- Review phase added to `/experiment` (eval → review → journal)
- `mcp-call` registration bug fixed (subagents can now use tools)
- `mcp-call` symlinked to `.venv/bin/` (on PATH for subagents)
- `experiment` registered as known workflow
- `/experiment-batch` skill built with batch_resolver library (30 tests)
- Batch resolver reviewer found 4 real bugs — all fixed

### POC epic
- GitHub repo created: c-daly/agora
- 7 issues filed (#1 epic, #2-#7 tasks)
- Experiment setup complete for all 6 tasks
- Batch goal.yaml with dependencies and issue references

## Key files

### Agora (`~/projects/agora`, branch: main, remote: c-daly/agora)
- `agora/adapters/` — fred, sec_ftd, treasury adapters
- `agora/analysis/yield_curve.py` — spread computation + inversion detection
- `agora/schemas/models.py` — all common data schemas
- `experiments/poc/` — POC batch (goal.yaml + 6 task directories with eval)
- `experiments/{fred,sec_ftd,treasury,yield_curve}_adapter/` — completed experiments

### Agent-swarm (`~/.claude/plugins/agent-swarm`, branch: feature/experiment-workflow)
- `skills/experiment/SKILL.md` — review phase added
- `skills/experiment-batch/SKILL.md` — batch orchestration skill
- `lib/batch_resolver.py` — batch task discovery and resolution (30 tests)
- `bin/mcp-call` — fixed registration bug
- `config/workflows/experiment.yaml` — review phase
- `config/workflows/experiment-batch.yaml` — batch workflow
- `docs/superpowers/specs/2026-03-23-experiment-batch-design.md`
- `docs/superpowers/plans/2026-03-23-experiment-batch.md`

### GitHub issues
- agora #1-#7 — POC epic and tasks
- agent-swarm #84 — Review phase (implemented)
- agent-swarm #85 — Subagent registration (priority)
- agent-swarm #86 — Batch ticket discovery

## Lessons learned
- Reviews are non-negotiable — the reviewer finds real bugs every time it runs
- "All tests pass first try" is suspicious, not reassuring
- Plans with complete code are dictation — the implementer needs room to make decisions
- Don't silently work around failures (like the 404 on issue creation) — escalate them
- Don't dispatch redundant agents — track what's already running
- Agents don't merge or close issues — humans decide what ships
- Archiving is a human action after signoff
