import io
p = r"scripts\build_codex_db.py"
t = io.open(p, encoding="utf-8").read()
old = "ecology unioned, highest SQS kept"
new = "ecology unioned, incumbent SQS kept"
print("found", t.count(old))
io.open(p, "w", encoding="utf-8", newline="").write(t.replace(old, new))
print("fixed")
