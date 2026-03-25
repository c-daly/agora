import pathlib
import textwrap

DST = "/Users/cdaly/projects/agora/agora/adapters/edgar_institutional_adapter.py"

content = textwrap.dedent('''\
"""EDGAR institutional-holdings (13F) adapter for Agora.

Fetches SEC Form 13F-HR filings via the EDGAR full-text search (EFTS)
API, downloads the underlying XML information tables, and parses
institutional holding details into agora.schemas.Transaction objects.

Form 13F-HR: filed quarterly by institutional investment managers with
             >=USD 100M in qualifying assets under management.

SEC EDGAR EFTS endpoint:
  https://efts.sec.gov/LATEST/search-index?forms=13F-HR&q=...

SEC requires:
  - A descriptive User-Agent header
  - Rate limiting to 10 requests per second
"""
''')

print(f"Generated {len(content)} chars of docstring")
pathlib.Path(DST).write_text(content)
