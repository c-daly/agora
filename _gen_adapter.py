import pathlib

DST = "/Users/cdaly/projects/agora/agora/adapters/edgar_institutional_adapter.py"

Q = chr(34)
Q3 = Q * 3
BQ = chr(92)
N = chr(10)

lines = []

# Module docstring
lines.append(Q3 + 'EDGAR institutional-holdings (13F) adapter for Agora.')
lines.append('')
lines.append('Fetches SEC Form 13F-HR filings via the EDGAR full-text search (EFTS)')
lines.append('API, downloads the underlying XML information tables, and parses')
lines.append('institutional holding details into agora.schemas.Transaction objects.')
lines.append('')
lines.append('Form 13F-HR: filed quarterly by institutional investment managers with')
lines.append('             >=USD 100M in qualifying assets under management.')
lines.append('')
lines.append('SEC EDGAR EFTS endpoint:')
lines.append('  https://efts.sec.gov/LATEST/search-index?forms=13F-HR&q=...')
lines.append('')
lines.append('SEC requires:')
lines.append('  - A descriptive User-Agent header')
lines.append('  - Rate limiting to 10 requests per second')
lines.append(Q3)

print('Generating adapter...')

pathlib.Path(DST).write_text(N.join(lines) + N)
print('Wrote docstring')
