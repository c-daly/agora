import pathlib

DST = "/Users/cdaly/projects/agora/agora/adapters/edgar_institutional_adapter.py"

txt = pathlib.Path("/Users/cdaly/projects/agora/agora/adapters/edgar_activist_adapter.py").read_text()
print("Template length:", len(txt))
