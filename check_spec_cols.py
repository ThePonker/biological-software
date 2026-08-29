import sqlite3, paths
c = sqlite3.connect(str(paths.OBSERVATUM_DB)); c.row_factory = sqlite3.Row
for col in ("specimen_code","preparation_type","storage_location","drawer_unit","condition","label_data"):
    n = c.execute(f"SELECT COUNT(*) FROM specimens WHERE {col} IS NOT NULL AND TRIM({col})<>''").fetchone()[0]
    vals = [r[0] for r in c.execute(f"SELECT DISTINCT {col} FROM specimens WHERE {col} IS NOT NULL AND TRIM({col})<>'' LIMIT 6")]
    print(f"  {col:18} filled={n:<6} e.g. {vals}")
print("  total specimens:", c.execute("SELECT COUNT(*) FROM specimens").fetchone()[0])
