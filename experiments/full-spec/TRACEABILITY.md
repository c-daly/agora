# Traceability Matrix — Full Spec Implementation

## How to read this

Each row maps: Goal task → Implementation file → Tests → Spec reference → Status

## Tasks

| # | Task ID | Goal | Implementation | Tests | Spec Section | Status |
|---|---------|------|----------------|-------|--------------|--------|
| 1 | edgar_filings_adapter | Fetch 10-K, 10-Q, 8-K from EDGAR | `agora/adapters/edgar_filings_adapter.py` | `tests/test_edgar_filings_adapter.py` | Adapters: edgar_filings_adapter | PENDING REVIEW |
| 2 | edgar_institutional_adapter | Fetch 13F holdings from EDGAR | | | Adapters: edgar_institutional_adapter | NOT STARTED |
| 3 | edgar_activist_adapter | Fetch 13D/13G from EDGAR | | | Adapters: edgar_activist_adapter | IN PROGRESS |
| 4 | insider_activity | Aggregate insider buy/sell ratios | | | Analysis: insider_activity | BLOCKED (dep: 2) |
| 5 | yahoo_options_adapter | Fetch options chains via yfinance | `agora/adapters/yahoo_options_adapter.py` | `tests/test_yahoo_options_adapter.py` | Adapters: yahoo_options_adapter | PENDING REVIEW |
| 6 | options_sentiment_adapter | Put/call ratios, IV skew | | | Adapters: options_sentiment_adapter | BLOCKED (dep: 5) |
| 7 | short_squeeze_detector | Identify squeeze candidates | | | Analysis: short_squeeze_detector | BLOCKED (dep: 6) |
| 8 | finra_short_interest_adapter | Bi-monthly short interest from FINRA | `agora/adapters/finra_short_interest_adapter.py` | `tests/test_finra_short_interest_adapter.py` | Adapters: finra_short_interest_adapter | PENDING REVIEW |
| 9 | threshold_list_adapter | Reg SHO threshold lists | | | Adapters: threshold_list_adapter | IN PROGRESS |
| 10 | ftd_analyzer | FTD trend analysis | `agora/analysis/ftd_analyzer.py` | `tests/test_ftd_analyzer.py` | Analysis: ftd_analyzer | PENDING REVIEW |
| 11 | sector_short_sentiment | Sector-level short metrics | | | Analysis: sector_short_sentiment | IN PROGRESS |
| 12 | bls_adapter | BLS employment, CPI, PPI | `agora/adapters/bls_adapter.py` | `tests/test_bls_adapter.py` | Adapters: bls_adapter | PENDING REVIEW |
| 13 | congress_adapter | Congressional trading disclosures | `agora/adapters/congress_adapter.py` | `tests/test_congress_adapter.py` | Adapters: congress_adapter | PENDING REVIEW |
| 14 | macro_dashboard | Key indicator summary + trends | | | Analysis: macro_dashboard | BLOCKED (dep: 12) |
| 15 | sector_analysis | Sector performance, rotation | | | Analysis: sector_analysis | IN PROGRESS |
| 16 | earnings_context | Earnings with historical surprises | | | Analysis: earnings_context | IN PROGRESS |
| 17 | congress_tracker | Congressional trades + timing | | | Analysis: congress_tracker | IN PROGRESS |
| 18 | correlation_matrix | Pairwise correlation matrices | | | Quant: correlation_matrix | IN PROGRESS |
| 19 | pca_factors | PCA on covariance matrix | | | Quant: pca_factors | BLOCKED (dep: 18) |
| 20 | random_matrix_filter | Marchenko-Pastur filtering | | | Quant: random_matrix_filter | BLOCKED (dep: 18) |
| 21 | factor_decomposition | Fama-French factor regression | | | Quant: factor_decomposition | IN PROGRESS |
| 22 | cointegration | Cointegration testing | | | Quant: cointegration | IN PROGRESS |
| 23 | correlation_network | Graph from correlation matrix | | | Quant: correlation_network | BLOCKED (dep: 18) |
| 24 | volatility_decomposition | Volatility component analysis | | | Quant: volatility_decomposition | IN PROGRESS |
| 25 | short_factor_analysis | PCA on short positioning | | | Quant: short_factor_analysis | BLOCKED (dep: 19) |

## Spec Compliance Checklist

Each completed task will be verified against `docs/agora-spec.md`:
- [ ] Function signatures match spec component description
- [ ] Return types use the correct schema objects
- [ ] Error handling matches spec eval criteria
- [ ] Edge cases from spec are covered in tests

This matrix will be updated as tasks complete and reviews finish.
