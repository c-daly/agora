# Session Handoff — Run Full Spec Batch Autonomously

## What to do

Run `/experiment-batch experiments/full-spec/` and complete all 25 tasks without human intervention.

The batch goal.yaml is at `experiments/full-spec/goal.yaml`. It has 25 tasks across 5 epics with dependency chains. The batch resolver handles ordering and parallelization.

## Enforcement rules (non-negotiable)

1. **Every agent must be registered via `prepare_dispatch`** — the hook blocks bypassPermissions and verifies agent IDs with the daemon
2. **Review phase requires APPROVED verdict** — checkpoint blocks advancement without it. Dispatch the reviewer agent, store the verdict, then pass checkpoint
3. **Full test suite must pass** — not just new tests. Run the complete suite before committing
4. **Visual verification for UI tasks** — if target is in webapp/, open it in a browser and screenshot
5. **Don't stop to ask** — follow the workflow to completion. Only stop for hard blockers
6. **Monitor background agents** — check on stragglers when others finish. Kill and redispatch stuck agents
7. **No "pre-existing" bugs** — every bug in this repo was written by agents. Fix them, don't label them

## Workflow per task

```
read → plan → work → eval → review (checkpoint required) → journal → decide → next task
```

The daemon enforces transitions. eval can only go to review or work. review requires checkpoint with APPROVED verdict before advancing to journal.

## What's built

- 7 adapters, 3 analysis modules, 3 API files, glossary
- React webapp: dashboard, deep dive page, screener page
- 42 vitest tests, 16 screener API tests all passing
- GitHub issues: #17-#21 (epics), #22-#46 (tasks)

## What to build

25 tasks in `experiments/full-spec/goal.yaml`:
- 9 adapters: edgar_filings, edgar_institutional, edgar_activist, yahoo_options, options_sentiment, finra_short_interest, threshold_list, bls, congress
- 16 analysis modules: insider_activity, short_squeeze_detector, ftd_analyzer, sector_short_sentiment, macro_dashboard, sector_analysis, earnings_context, congress_tracker, correlation_matrix, pca_factors, random_matrix_filter, factor_decomposition, cointegration, correlation_network, volatility_decomposition, short_factor_analysis

## Key files

- `experiments/full-spec/goal.yaml` — the batch definition
- `agora/schemas/models.py` — all data schemas
- `agora/adapters/` — existing adapters (patterns to follow)
- `agora/analysis/` — existing analysis modules (patterns to follow)
- `docs/agora-spec.md` — full project specification

## Environment

- `FRED_API_KEY` must be set (for FRED adapter)
- `BLS_API_KEY` needed for BLS adapter (#33)
- SEC requires User-Agent header, 10 req/sec limit
- yfinance is installed (for Yahoo adapters)
- numpy, scipy, scikit-learn installed (for quant modules)
