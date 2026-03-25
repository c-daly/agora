# Session Handoff — Agora Full Build Experiment

## What this is

An experiment-inside-an-experiment. The **inner loop** builds the Agora financial intelligence app through the enforced experiment workflow. The **outer loop** evaluates how the inner loop performed, identifies process failures, fixes the workflow, wipes the code, and runs again. The code is disposable. The workflow improvements are the real output.

```
OUTER LOOP (you run this):
  1. Run inner loop (build Agora from GitHub issues)
  2. Evaluate: did the workflow work? spec coverage? code quality?
  3. Identify process failures (skipped reviews, stubs, missing features)
  4. Fix the workflow/daemon/briefings in agent-swarm
  5. Wipe the agora code
  6. Run again
  7. Repeat until the inner loop works autonomously
```

## Current state

### Agora repo (`~/projects/agora`, branch: main)
- **Wiped clean** — only spec, config, and empty package stubs remain
- `docs/agora-spec.md` — the full spec (175 lines, defines everything)
- `pyproject.toml` — Python 3.11+, FastAPI, Pydantic, NumPy, SciPy, scikit-learn
- `.github/ISSUE_TEMPLATE/agora-task.yml` — issue template mapping 1:1 to goal.yaml
- `agora/` — empty `__init__.py` package stubs (adapters, analysis, quant, api, glossary, schemas)
- **67 GitHub issues** (#1-#67) covering the entire spec

### Agent-swarm (`~/.claude/plugins/agent-swarm`, branch: feature/experiment-workflow)
- Daemon enforces workflow phases and transitions
- `prepare_dispatch` rejects ALL agents without an active workflow
- Review phase requires APPROVED checkpoint with stored verdict
- Experiment-setup checks spec coverage before generating artifacts
- Worker monitoring requirements in experiment skill
- Reviewer briefing requires spec compliance checking

### GitHub issues breakdown
- #1-#7: POC epic (dashboard, API, glossary, components) — from prior runs
- #8-#16: Short selling intelligence epic
- #17-#21: Epics (EDGAR suite, Options, Short complete, Macro, Quant)
- #22-#46: Backend tasks (adapters + analysis + quant modules)
- #47-#67: Frontend + app shell (visualizations, dashboard composer, glossary integration, alerts)

## How to run the inner loop

### Step 1: Create the experiment directory

```
mkdir -p experiments/run-1/{eval,journal}
```

### Step 2: Create goal.yaml from GitHub issues

Use a GitHub search query to discover all tasks:

```yaml
query: "repo:c-daly/agora is:open -label:epic"
spec: docs/agora-spec.md

success_criteria:
  - metric: test_pass_rate
    threshold: 1.0
    primary: true

on_failure: continue
```

The query pulls all open non-epic issues. The `spec:` field triggers the coverage check during experiment-setup.

### Step 3: Run experiment-setup

`/experiment-setup experiments/run-1/`

This should:
1. Resolve the query → build task list from GitHub issues
2. Check spec coverage — flag any spec components with no corresponding issue
3. Generate constraints and eval for each task
4. Report readiness

### Step 4: Run the experiment batch

`/experiment-batch experiments/run-1/`

This runs each task through the enforced workflow:
```
read → plan → work → eval → review (checkpoint) → journal → decide
```

The daemon enforces every transition. The review checkpoint requires an APPROVED verdict. The batch skill requires per-task experiment workflows.

### Step 5: After the inner loop completes

Evaluate:
1. Run the traceability matrix — walk the spec, check every component has an implementation
2. Run the full test suite
3. Run ruff on all code
4. Start the servers and visually verify the UI
5. Check: did every task go through the full workflow? Were reviews meaningful?

## What to watch for (outer loop evaluation)

### Process failures

| Problem | How to detect | Resolution |
|---------|--------------|------------|
| Agent dispatched without workflow | `prepare_dispatch` should reject — if it doesn't, daemon needs restart to pick up config | Kill daemon, restart, verify |
| Review phase skipped | Check journal — no review verdict recorded | Daemon config has `checkpoint: true` on review phase. Verify config is loaded. |
| Stubs committed | Run ruff — F821 (undefined name) catches stubs | The reviewer should catch this. If it didn't, check if reviewer was dispatched with the goal objective. |
| Tests mock `create=True` | Grep for `create=True` in test files | The eval scripts from experiment-setup shouldn't use this. If implementer-written tests do, the reviewer should flag it. |
| Agent stuck/degraded | Output line count not growing between 60s checks | Kill and redispatch. Note the failure pattern for briefing improvements. |
| Rate limit kills agent | Agent output contains "rate limit" / "usage" / "resets" | Wait for reset, redispatch. Check if the agent wrote any files before dying. |
| Scratch files committed | `_*.py` files in repo root | .gitignore should catch these. If not, add patterns. |
| Spec component missing from task list | Traceability matrix shows gaps | File missing GitHub issues and rerun. |
| Glossary tooltips not on all metrics | Visual inspection of running app | This is a cross-cutting requirement — needs its own task (#67). |
| Frontend eval insufficient | UI "passes tests" but looks broken | Visual verification is mandatory for UI tasks. Open in browser, screenshot. |

### Code quality failures

| Problem | How to detect | Resolution |
|---------|--------------|------------|
| API leaks exception details | Reviewer checks for `str(exc)` in responses | Replace with generic error messages |
| Response body in exceptions | Reviewer checks for `resp.text` in raise | Redact or use parsed error_message only |
| No logging on adapter failures | Reviewer checks silent `except` blocks | Add `logger.warning(..., exc_info=True)` |
| Data shape mismatch API↔frontend | Visual verification — page shows wrong data | Map API response fields in the component |
| Missing error/loading states | Visual verification | Components need loading, error, empty states |

### Architecture failures

| Problem | How to detect | Resolution |
|---------|--------------|------------|
| Circular imports | Import errors at runtime | Restructure dependencies |
| Schema mismatch | Adapter returns wrong type | Read models.py, match return types |
| Rate limit violations | SEC/FINRA/BLS block requests | Add throttling, respect documented limits |

## Key files in agent-swarm

- `config/workflows/experiment.yaml` — phase definitions and transitions
- `lib/controller.py` — `prepare_dispatch` with workflow requirement
- `lib/protocol_assembly.py` — briefings for all agent roles
- `hooks/enforce-agent-registration.py` — blocks bypassPermissions and fake IDs
- `hooks/enforce-workflow-completion.py` — blocks completion claims without workflow done
- `skills/experiment/SKILL.md` — experiment workflow protocol with monitoring requirements
- `skills/experiment-batch/SKILL.md` — batch orchestration with per-task workflows
- `skills/experiment-setup/SKILL.md` — validation with spec coverage check

## Environment

- `FRED_API_KEY` must be set (for FRED adapter)
- `BLS_API_KEY` needed for BLS adapter
- SEC requires User-Agent header, 10 req/sec limit
- yfinance: unofficial, rate limit cautiously
- numpy, scipy, scikit-learn: in pyproject.toml

## Memory files

All in `~/.claude/projects/-Users-cdaly-projects-agora/memory/`:
- `feedback_reviews_nonnegotiable.md` — never skip reviews
- `feedback_agents_dont_merge.md` — humans decide what ships
- `feedback_workflow_antipatterns.md` — 11 documented failure patterns with solutions
- `feedback_always_dispatch.md` — always prepare_dispatch, never bypassPermissions
- `project_agora_workflow.md` — project state

## Success criteria for the outer loop

The inner loop is working when:
1. All 67 spec components are implemented (traceability matrix: 67/67)
2. All tests pass (pytest + vitest)
3. Ruff is clean (0 errors)
4. Every task went through the full experiment workflow (read → review → done)
5. The reviewer found and caught real issues (not rubber-stamp approvals)
6. The app renders correctly with real data (visual verification)
7. No human intervention was required during the inner loop
