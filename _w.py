import pathlib,sys,base64
f=sys.argv[1]
d=sys.stdin.buffer.read()
pathlib.Path(f).write_bytes(base64.b64decode(d))