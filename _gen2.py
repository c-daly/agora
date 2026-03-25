import pathlib

Q = chr(34)
Q3 = Q * 3
BQ = chr(92)
N = chr(10)
LB = chr(123)
RB = chr(125)
DST = "/Users/cdaly/projects/agora/agora/adapters/edgar_institutional_adapter.py"

SRC = pathlib.Path("/Users/cdaly/projects/agora/agora/adapters/edgar_activist_adapter.py").read_text()
print("Read template:", len(SRC), "chars")
