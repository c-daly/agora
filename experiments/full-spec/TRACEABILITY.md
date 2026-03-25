# Traceability Matrix — Full Spec Coverage

Built from `docs/agora-spec.md`, not from goal.yaml.

| # | Spec Component | Expected File | Spec Requirement | Status |
|---|---------------|---------------|------------------|--------|
| 1 | fred_adapter | `agora/adapters/fred_adapter.py` | fetch any FRED series by ID | IMPLEMENTED (124L) |
| 2 | edgar_filings_adapter | `agora/adapters/edgar_filings_adapter.py` | fetch 10-K, 10-Q, 8-K filings | IMPLEMENTED (213L) |
| 3 | edgar_insider_adapter | `agora/adapters/edgar_insider_adapter.py` | fetch Form 4 insider transactions | IMPLEMENTED (322L) |
| 4 | edgar_institutional_adapter | `agora/adapters/edgar_institutional_adapter.py` | fetch 13F institutional holdings | IMPLEMENTED (186L) |
| 5 | edgar_activist_adapter | `agora/adapters/edgar_activist_adapter.py` | fetch 13D/13G activist disclosures | IMPLEMENTED (358L) |
| 6 | treasury_adapter | `agora/adapters/treasury_adapter.py` | yield curves, auction results | IMPLEMENTED (214L) |
| 7 | bls_adapter | `agora/adapters/bls_adapter.py` | employment, inflation detail | IMPLEMENTED (154L) |
| 8 | yahoo_quotes_adapter | `agora/adapters/yahoo_quotes_adapter.py` | quotes, historicals, fundamentals | IMPLEMENTED (59L) |
| 9 | yahoo_options_adapter | `agora/adapters/yahoo_options_adapter.py` | full options chains per symbol | IMPLEMENTED (111L) |
| 10 | congress_adapter | `agora/adapters/congress_adapter.py` | congressional trading disclosures | IMPLEMENTED (274L) |
| 11 | finra_short_volume_adapter | `agora/adapters/finra_short_volume_adapter.py` | daily short sale volume, all TRFs combined | IMPLEMENTED (209L) |
| 12 | finra_short_interest_adapter | `agora/adapters/finra_short_interest_adapter.py` | twice-monthly short interest per security | IMPLEMENTED (216L) |
| 13 | sec_ftd_adapter | `agora/adapters/sec_ftd_adapter.py` | SEC fails-to-deliver flat files | IMPLEMENTED (260L) |
| 14 | threshold_list_adapter | `agora/adapters/threshold_list_adapter.py` | Reg SHO threshold lists from NYSE, NASDAQ, CBOE | IMPLEMENTED (254L) |
| 15 | yahoo_short_adapter | `agora/adapters/yahoo_short_adapter.py` | short interest, short ratio from yfinance | IMPLEMENTED (108L) |
| 16 | options_sentiment_adapter | `agora/adapters/options_sentiment_adapter.py` | put/call ratios and IV skew | IMPLEMENTED (136L) |
| 17 | yield_curve | `agora/analysis/yield_curve.py` | current curve, historical, inversion detection | IMPLEMENTED (136L) |
| 18 | insider_activity | `agora/analysis/insider_activity.py` | aggregate insider buy/sell ratios by sector/company | IMPLEMENTED (211L) |
| 19 | macro_dashboard | `agora/analysis/macro_dashboard.py` | key indicator summary with trend detection | IMPLEMENTED (164L) |
| 20 | sector_analysis | `agora/analysis/sector_analysis.py` | sector performance, rotation, correlation | IMPLEMENTED (259L) |
| 21 | earnings_context | `agora/analysis/earnings_context.py` | upcoming earnings with historical surprise data | IMPLEMENTED (104L) |
| 22 | congress_tracker | `agora/analysis/congress_tracker.py` | congressional trades with timing analysis | IMPLEMENTED (224L) |
| 23 | short_composite | `agora/analysis/short_composite.py` | unified per-symbol score from all short sources | IMPLEMENTED (216L) |
| 24 | short_squeeze_detector | `agora/analysis/short_squeeze_detector.py` | identify candidates: high SI + rising price + high DTC | IMPLEMENTED (405L) |
| 25 | short_divergence | `agora/analysis/short_divergence.py` | detect divergences between short positioning and other signals | IMPLEMENTED (251L) |
| 26 | ftd_analyzer | `agora/analysis/ftd_analyzer.py` | FTD trend analysis, threshold list correlation | IMPLEMENTED (164L) |
| 27 | sector_short_sentiment | `agora/analysis/sector_short_sentiment.py` | aggregate short metrics by sector | IMPLEMENTED (116L) |
| 28 | correlation_matrix | `agora/analysis/quant/correlation_matrix.py` | rolling/static pairwise correlation, regime changes | IMPLEMENTED (156L) |
| 29 | pca_factors | `agora/analysis/quant/pca_factors.py` | PCA on returns covariance, latent factors | IMPLEMENTED (89L) |
| 30 | random_matrix_filter | `agora/analysis/quant/random_matrix_filter.py` | Marchenko-Pastur noise filtering | IMPLEMENTED (155L) |
| 31 | factor_decomposition | `agora/analysis/quant/factor_decomposition.py` | Fama-French style regression | IMPLEMENTED (149L) |
| 32 | cointegration | `agora/analysis/quant/cointegration.py` | pairwise cointegration testing | IMPLEMENTED (194L) |
| 33 | correlation_network | `agora/analysis/quant/correlation_network.py` | graph from correlation matrix, MST, topology | IMPLEMENTED (173L) |
| 34 | volatility_decomposition | `agora/analysis/quant/volatility_decomposition.py` | overnight vs intraday, variance risk premium | IMPLEMENTED (171L) |
| 35 | short_factor_analysis | `agora/analysis/quant/short_factor_analysis.py` | PCA on short positioning data | IMPLEMENTED (203L) |
| 36 | viz_yield_curve | `webapp/src/components/YieldCurveChart.tsx` | Interactive yield curve with time slider | IMPLEMENTED (46L) |
| 37 | viz_macro_grid | `webapp/src/components/MacroGrid.tsx` | Macro indicator grid with sparklines | IMPLEMENTED (151L) |
| 38 | viz_insider_heatmap | — | Insider trading heatmap (sector x time) | **MISSING** |
| 39 | viz_sector_rotation | — | Sector rotation chart | **MISSING** |
| 40 | viz_congress_timeline | — | Congressional trading timeline | **MISSING** |
| 41 | viz_earnings_calendar | — | Earnings calendar with context | **MISSING** |
| 42 | viz_correlation_explorer | — | Correlation matrix explorer | **MISSING** |
| 43 | viz_short_composite | `webapp/src/pages/SymbolDeepDive.tsx` | Short composite dashboard per symbol | IMPLEMENTED (332L) |
| 44 | viz_short_volume_ratio | `webapp/src/pages/SymbolDeepDive.tsx` | Short volume ratio time series | IMPLEMENTED (332L) |
| 45 | viz_short_interest_tracker | — | Short interest change tracker | **MISSING** |
| 46 | viz_ftd_heatmap | `webapp/src/components/FtdHeatmap.tsx` | FTD heatmap (symbol x time) | IMPLEMENTED (167L) |
| 47 | viz_threshold_monitor | — | Threshold list monitor | **MISSING** |
| 48 | viz_squeeze_screener | `webapp/src/pages/Screener.tsx` | Short squeeze candidate screener | IMPLEMENTED (188L) |
| 49 | viz_options_gauge | — | Options sentiment gauge | **MISSING** |
| 50 | viz_divergence_alerts | `webapp/src/pages/SymbolDeepDive.tsx` | Short divergence alerts | IMPLEMENTED (332L) |
| 51 | viz_sector_short_pressure | — | Sector short pressure chart | **MISSING** |
| 52 | viz_corr_matrix | — | Interactive correlation matrix | **MISSING** |
| 53 | viz_pca_chart | — | PCA variance explained chart | **MISSING** |
| 54 | viz_factor_bars | — | Factor loading bar charts | **MISSING** |
| 55 | viz_corr_network | — | Correlation network graph | **MISSING** |
| 56 | viz_cointegration_spreads | — | Cointegration pair spread charts | **MISSING** |
| 57 | viz_vol_decomp | — | Volatility decomposition stacked area | **MISSING** |
| 58 | viz_vrp_timeseries | — | Variance risk premium time series | **MISSING** |
| 59 | viz_short_factor_heatmap | — | Short factor heatmap | **MISSING** |
| 60 | app_dashboard_composer | — | Dashboard composer — arrange components | **MISSING** |
| 61 | app_symbol_search | `webapp/src/App.tsx` | Symbol search with auto-complete | IMPLEMENTED (177L) |
| 62 | app_glossary_tooltips | `webapp/src/components/GlossaryTooltip.tsx` | Glossary tooltips on ALL metrics, axes, column headers | IMPLEMENTED (106L) |
| 63 | app_refresh_indicator | — | Data refresh status indicator | **MISSING** |
| 64 | app_source_attribution | — | Source attribution per widget | **MISSING** |
| 65 | app_alert_config | — | Alert configuration for squeeze/divergence | **MISSING** |
| 66 | glossary_data | `agora/glossary/terms.yaml` | Static term definitions | IMPLEMENTED (281L) |
| 67 | glossary_api | `agora/api/routes.py` | GET /api/glossary endpoints | IMPLEMENTED (313L) |

**Implemented: 46 | Missing: 21 | Total: 67**

## Missing Components

- **viz_insider_heatmap**: Insider trading heatmap (sector x time)
- **viz_sector_rotation**: Sector rotation chart
- **viz_congress_timeline**: Congressional trading timeline
- **viz_earnings_calendar**: Earnings calendar with context
- **viz_correlation_explorer**: Correlation matrix explorer
- **viz_short_interest_tracker**: Short interest change tracker
- **viz_threshold_monitor**: Threshold list monitor
- **viz_options_gauge**: Options sentiment gauge
- **viz_sector_short_pressure**: Sector short pressure chart
- **viz_corr_matrix**: Interactive correlation matrix
- **viz_pca_chart**: PCA variance explained chart
- **viz_factor_bars**: Factor loading bar charts
- **viz_corr_network**: Correlation network graph
- **viz_cointegration_spreads**: Cointegration pair spread charts
- **viz_vol_decomp**: Volatility decomposition stacked area
- **viz_vrp_timeseries**: Variance risk premium time series
- **viz_short_factor_heatmap**: Short factor heatmap
- **app_dashboard_composer**: Dashboard composer — arrange components
- **app_refresh_indicator**: Data refresh status indicator
- **app_source_attribution**: Source attribution per widget
- **app_alert_config**: Alert configuration for squeeze/divergence