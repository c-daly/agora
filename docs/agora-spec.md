# Agora — Open Financial Intelligence Platform

## Vision

An open-source financial intelligence application that aggregates freely available financial and economic data, presents it through interactive visualizations, and makes institutional-grade market context accessible to everyone. Special emphasis on compositing a complete short selling and bearish sentiment picture from disparate free sources — data that typically costs hundreds per month from commercial providers. Every metric and indicator is accompanied by accessible explanations via a glossary system.

## Tech Stack

- **Backend:** Python, FastAPI
- **Frontend:** React
- **Charting:** Recharts (or upgrade to D3 if needed per visualization)
- **Quantitative:** NumPy, SciPy, scikit-learn
- **Data storage:** SQLite for caching/persistence, flat files for raw data
- **Task scheduling:** APScheduler or similar for data refresh

## Architecture

```
adapters/         → One module per data source. Fetches, normalizes to common schema.
analysis/         → Modules that operate on normalized data. Each is independent.
analysis/quant/   → Quantitative/linear algebra analysis modules.
api/              → FastAPI routes. Thin layer between analysis and frontend.
frontend/         → React app. Each dashboard/visualization is a self-contained component.
schemas/          → Pydantic models defining the common data shapes.
glossary/         → Static term definitions. Tooltips and explanation content.
```

## Common Data Schema

All adapters normalize to these core shapes:

- **TimeSeries** — date, value, metadata (source, unit, frequency)
- **Filing** — date, entity, type, url, extracted_fields
- **Transaction** — date, entity, action, amount, context (insider trades, congressional trades)
- **Quote** — symbol, date, open, high, low, close, volume
- **ShortData** — symbol, date, data_type (volume|interest|ftd|threshold), value, total_for_ratio, source
- **OptionsSnapshot** — symbol, date, expiry, strike, type (put|call), volume, open_interest, implied_vol, bid, ask

Analysis modules consume these shapes. Visualizations consume analysis output.

## Glossary System

A static JSON/YAML file mapping term keys to definitions. Each entry has:

- **term** — display name
- **description** — what it is, in plain English
- **interpretation** — what's high, what's low, what to watch for
- **caveats** — known limitations or common misreadings

The frontend renders glossary entries as tooltips on any labeled metric, chart axis, or column header. Terms are referenced by key. No dynamic metadata, no per-value overhead — just a lookup table.

The glossary is also a ticket: populating it is independent work that can be done in parallel with everything else.

## Data Sources

### Market & Economic Data

| Source | Interface | Data | Rate Limits |
|--------|-----------|------|-------------|
| FRED | REST API, free key | Macro indicators (GDP, CPI, unemployment, rates, money supply) | 120 req/min |
| SEC EDGAR | REST API, no key | Filings, insider trades (Form 4), institutional holdings (13F), 13D/13G activist disclosures | 10 req/sec, User-Agent required |
| Treasury.gov | REST/CSV, no key | Yield curves, auction data, debt to the penny | Generous |
| BLS | REST API, free key | Employment, CPI detail, PPI, productivity | 500 daily |
| Yahoo Finance | yfinance library | Quotes, historicals, fundamentals, earnings dates, options chains, short interest summary | Unofficial, rate limit cautiously |
| Congressional trades | Quiver Quant API or scrape | Congress member stock transactions | Varies |

### Short Selling & Bearish Sentiment Data

| Source | Interface | Data | Frequency | Notes |
|--------|-----------|------|-----------|-------|
| FINRA Short Sale Volume | REST API + flat files | Daily short volume and total volume per symbol, per reporting facility (NYSE TRF, NASDAQ TRF Carteret, NASDAQ TRF Chicago, ADF, ORF) | Daily, by 6pm ET | API available; also downloadable pipe-delimited files. Must combine TRF files for complete off-exchange picture. Does NOT include on-exchange data. |
| FINRA Short Interest | Query page + pipe-delimited files | Total open short positions per security | Twice monthly | Downloadable for OTC; per-security query for listed. ~2 week reporting lag. |
| SEC Fails-to-Deliver | Flat files (pipe-delimited) | FTD balance per security (date, CUSIP, ticker, price, quantity) | Twice monthly | First half of month available at month end; second half ~15th of next month. |
| Reg SHO Threshold Lists | Flat files per exchange | Securities with sustained high FTDs (>=10k shares, >=0.5% outstanding, 5 consecutive days) | Daily | Separate lists from NYSE, NASDAQ, CBOE. Scrape or download. |
| Yahoo Finance (short fields) | yfinance library | Short interest, short ratio, short % of float, short % of shares outstanding | Varies | Bundled with fundamentals. Convenient but not authoritative. |
| CBOE Options | Scrape or derived | Put/call ratios, volume, open interest by strike | Daily | Aggregate ratios available; detailed chains via Yahoo. |
| Yahoo Finance Options | yfinance library | Full options chains — puts, calls, volume, OI, IV, bid/ask per strike/expiry | On demand | Free, no auth. Compute put/call OI ratios and IV skew as short sentiment proxies. |

## Component Inventory

### Adapters — Market & Economic
- `fred_adapter` — fetch any FRED series by ID
- `edgar_filings_adapter` — fetch 10-K, 10-Q, 8-K filings
- `edgar_insider_adapter` — fetch Form 4 insider transactions
- `edgar_institutional_adapter` — fetch 13F institutional holdings
- `edgar_activist_adapter` — fetch 13D/13G activist position disclosures
- `treasury_adapter` — yield curves, auction results
- `bls_adapter` — employment, inflation detail
- `yahoo_quotes_adapter` — quotes, historicals, fundamentals
- `yahoo_options_adapter` — full options chains per symbol
- `congress_adapter` — congressional trading disclosures

### Adapters — Short Selling & Sentiment
- `finra_short_volume_adapter` — daily short sale volume files, all TRFs combined. Prefer API, fall back to flat file download.
- `finra_short_interest_adapter` — twice-monthly short interest per security. Scrape query page for listed securities, download pipe-delimited for OTC.
- `sec_ftd_adapter` — SEC fails-to-deliver flat files. Download, parse, normalize.
- `threshold_list_adapter` — Reg SHO threshold lists from NYSE, NASDAQ, CBOE. Aggregate across exchanges.
- `yahoo_short_adapter` — short interest, short ratio, short % of float from yfinance fundamentals.
- `options_sentiment_adapter` — compute put/call ratios and IV skew from yahoo options chains.

### Analysis Modules — Market & Economic
- `yield_curve` — current curve, historical curves, inversion detection
- `insider_activity` — aggregate insider buy/sell ratios by sector/company
- `macro_dashboard` — key indicator summary with trend detection
- `sector_analysis` — sector performance, rotation, correlation
- `earnings_context` — upcoming earnings with historical surprise data
- `congress_tracker` — congressional trades with timing analysis

### Analysis Modules — Short Selling & Sentiment
- `short_composite` — combines all short data sources into a unified per-symbol score. Daily short volume ratio + bi-monthly short interest change + FTD trend + threshold list presence + options-implied sentiment.
- `short_squeeze_detector` — identifies candidates: high short interest + rising price + high days-to-cover + decreasing shares available (via FTD proxy) + rising volume.
- `short_divergence` — detects divergences between short positioning and other signals: shorts rising while insiders buy, shorts rising while institutions accumulate (13F), shorts dropping while FTDs increase.
- `ftd_analyzer` — FTD trend analysis per security. Persistent FTDs, spikes, threshold list correlation.
- `sector_short_sentiment` — aggregate short metrics by sector. Which sectors are seeing increasing/decreasing short pressure.

### Analysis Modules — Quantitative
- `correlation_matrix` — rolling and static pairwise correlation matrices for any asset set. Detects regime changes via rolling window comparison.
- `pca_factors` — principal component analysis on returns covariance matrix. Extracts latent market factors, tracks variance concentration over time.
- `random_matrix_filter` — Marchenko-Pastur filtering to separate signal from noise in correlation matrices. Eigenvalues exceeding the theoretical noise bound represent real structure.
- `factor_decomposition` — Fama-French style regression. Decomposes returns into market, size, value, momentum factors. Residual alpha relative to factor model.
- `cointegration` — pairwise and basket cointegration testing. Identifies mean-reverting relationships. Tracks spread deviation from equilibrium.
- `correlation_network` — builds graph from correlation/covariance matrix. Minimum spanning tree, threshold networks. Tracks topology changes (centrality, clustering) over time.
- `volatility_decomposition` — decomposes realized volatility into components (overnight vs intraday, systematic vs idiosyncratic). Compares against implied vol to compute variance risk premium.
- `short_factor_analysis` — PCA/factor analysis on short positioning data across securities. Identifies whether short interest is loading on known factors (sector, size) or represents independent signal.

### Visualizations (React components)

#### Market & Economic
- Interactive yield curve (draggable time slider)
- Macro indicator grid (sparklines + current values)
- Insider trading heatmap (sector × time)
- Sector rotation chart
- Congressional trading timeline
- Earnings calendar with context
- Correlation matrix explorer

#### Short Selling & Sentiment
- Short composite dashboard per symbol (all signals on one view)
- Short volume ratio time series (daily, with moving averages)
- Short interest change tracker (bi-monthly deltas, ranked)
- FTD heatmap (symbol × time, intensity = FTD magnitude)
- Threshold list monitor (current list + days on list history)
- Short squeeze candidate screener (ranked by composite criteria)
- Options sentiment gauge (put/call ratio + IV skew visualization)
- Short divergence alerts (table of conflicting signals)
- Sector short pressure chart (aggregate short metrics by sector over time)

#### Quantitative
- Interactive correlation matrix (color-coded, clickable for pair detail)
- PCA variance explained chart (eigenvalue spectrum vs random matrix bound)
- Factor loading bar charts per security
- Correlation network graph (interactive, filterable by threshold)
- Cointegration pair spread charts with equilibrium bands
- Volatility decomposition stacked area chart
- Variance risk premium time series (realized vs implied)
- Short factor heatmap (short positioning loadings on latent factors)

### App Shell
- Dashboard composer — arrange components into custom views
- Symbol search with auto-complete
- Glossary-backed tooltips on all metrics, axes, and column headers
- Data refresh status indicator
- Source attribution and data freshness display per widget
- Alert configuration for short squeeze candidates and divergence signals

## Eval Criteria Pattern

Each ticket's eval should verify:
- **Adapters:** returns correctly shaped data matching the relevant schema, handles API errors gracefully, respects rate limits, handles missing/malformed upstream data
- **Analysis:** produces expected output given known input fixtures, edge cases handled, scores are deterministic given the same inputs
- **Quant:** numerical accuracy against known reference calculations, handles degenerate cases (singular matrices, insufficient data), appropriate use of numerical stability techniques
- **Visualizations:** renders without error, accepts the data shape from its analysis module, interactive elements function, glossary tooltips present on all labeled metrics
- **Integration:** end-to-end from adapter through analysis to rendered visualization
- **Short-specific:** adapters that combine multiple reporting facilities produce correctly merged output; analysis modules degrade gracefully when a data source has stale or missing data
- **Glossary:** every term referenced in any visualization or API response has a corresponding glossary entry
