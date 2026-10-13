"""A1: what an iRecord sync WOULD do with a download, before it is run. READ ONLY.

    py -3.14 scripts\\check_irecord_download.py "C:\\path\\download-....csv"
    py -3.14 scripts\\check_irecord_download.py download.csv --tag OBS-WJH-IRTEST-20261013- --expect 46

Reads the iRecord download the way the sync does (utf-8-sig, falling back to latin-1) and runs
the sync's OWN matching step -- ObservationValidationWorker._extract_irecord_fields and
_batch_duplicate_check, imported, not copied -- against observatum.db opened read-only.
Species, vice county and the later import steps are not run: this reports matching only.

Reports, for the whole download: rows that would UPDATE a held record (by iRecord ID, by
External key, or the copy already held when iRecord holds a record twice) and rows that would
be ADDED -- separately those whose External key names several held records (the A2 guard's
case: today they are added). Then:
- Observatum keys (External key starting OBS-): how many come back to exactly one held record;
- the --tag records (default the 13 Oct 2026 test upload): found / missing numbers, what the
  sync would do with each, any key held twice in the download, any key already in Observatum.
Writes one CSV per row of the tagged set and any row whose key or ID points at more than one
record (default scripts\\_oneoff\\irecord_download_check_<date>.csv) -- the only file it writes.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import os
import re
import sqlite3
import sys
import types
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, "Observatum")):
    if p not in sys.path:
        sys.path.insert(0, p)
import paths  # noqa: E402

FINAL = "READ ONLY. Nothing has been changed."
DEFAULT_TAG = "OBS-WJH-IRTEST-20261013-"


def read_download(path):
    """Rows as dicts, read as the sync's file step reads them."""
    for enc in ("utf-8-sig", "latin-1"):
        try:
            with open(path, "r", encoding=enc, newline="") as f:
                sample = f.read(4096)
                f.seek(0)
                delim = "\t" if sample.count("\t") > sample.count(",") else ","
                return list(csv.DictReader(f, delimiter=delim))
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"Could not read {path}")


class ReadOnlyDb:
    """The one method the matching step calls (execute_main), on a read-only connection."""

    def __init__(self, path):
        self.conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        self.conn.row_factory = sqlite3.Row

    def execute_main(self, sql, params=()):
        return self.conn.execute(sql, params).fetchall()


def run_matching(rows, db):
    """The sync's matching on these rows. Returns the DataFrame the sync would act on."""
    import pandas as pd
    from src.views.dialogs.observation_import_wizard.validation_worker import (
        ImportMode, ObservationValidationWorker as W)

    # The two methods use only these attributes; a plain namespace stands in for the QThread
    me = types.SimpleNamespace(db_manager=db, import_mode=ImportMode.IRECORD_SYNC,
                               _cancelled=False)
    me._parse_int = lambda v: W._parse_int(me, v)
    me._parse_float = lambda v: W._parse_float(me, v)
    records = []
    for n, raw in enumerate(rows, start=2):
        rec = W._extract_irecord_fields(me, raw)
        rec["row_number"] = n
        records.append(rec)
    df = pd.DataFrame(records)
    return W._batch_duplicate_check(me, df)


def outcome(row, shared_keys=frozenset()):
    note = str(row.get("import_notes") or "")
    if row.get("is_duplicate"):
        if note.startswith("Will update via iRecord ID"):
            return "update (iRecord ID)"
        if note.startswith("Will update via External key"):
            return "update (External key)"
        if "holds this twice" in note:
            return "update held copy (iRecord holds it twice)"
        return "update (other)"
    if row.get("external_key") in shared_keys:
        return "add as new (key names several records)"
    return "add as new"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("download")
    ap.add_argument("--db", default=str(paths.OBSERVATUM_DB))
    ap.add_argument("--tag", default=DEFAULT_TAG, help="External key prefix of a test set")
    ap.add_argument("--expect", type=int, default=46, help="records expected with --tag")
    ap.add_argument("--csv", default=None)
    a = ap.parse_args(argv)

    rows = read_download(a.download)
    db = ReadOnlyDb(a.db)
    print(f"Download: {a.download}\n  {len(rows):,} rows")
    if not rows:
        print(FINAL)
        return 0
    df = run_matching(rows, db)
    shared = {r[0] for r in db.execute_main(
        "SELECT observatum_key FROM observations WHERE observatum_key IS NOT NULL "
        "AND observatum_key != '' GROUP BY observatum_key HAVING COUNT(*) > 1")}
    df["outcome"] = [outcome(r, shared) for r in df.to_dict("records")]

    ids = [int(v) for v in df["irecord_id"].dropna()]
    inputs = [str(v) for v in df["input_on_date"] if str(v).strip()]
    print(f"  highest iRecord ID {max(ids) if ids else '-'}; "
          f"{len(inputs):,} rows with an input date")

    print("\nWhat the sync would do (matching step only):")
    for k, v in Counter(df["outcome"]).most_common():
        print(f"  {k:<44}{v:>8,}")

    # Observatum keys coming back
    key = df["external_key"].fillna("").astype(str)
    obs = df[key.str.startswith("OBS-")]
    held = {r[0] for r in db.execute_main(
        "SELECT observatum_key FROM observations WHERE observatum_key LIKE 'OBS-%'")}
    print(f"\nObservatum keys in the download (External key OBS-...): {len(obs):,}")
    if len(obs):
        known = obs[obs["external_key"].isin(held)]
        print(f"  already in Observatum: {len(known):,}; not yet: {len(obs) - len(known):,}")
        for k, v in Counter(known["outcome"]).most_common():
            print(f"    held, {k}: {v:,}")

    # Keys or IDs pointing at more than one row/record
    dup_keys = key[key != ""].value_counts()
    obs_dup = dup_keys[(dup_keys > 1) & dup_keys.index.str.startswith("OBS-")]
    print(f"\nObservatum keys appearing more than once in the download: {len(obs_dup)}")
    for k, v in obs_dup.head(10).items():
        print(f"  {k}  x{v}")

    # The tagged test set
    tag = df[key.str.startswith(a.tag)] if a.tag else df.iloc[0:0]
    print(f"\nTest set '{a.tag}': {len(tag)} found, {a.expect} expected")
    if a.tag:
        nums = set()
        for k in tag["external_key"]:
            m = re.search(r"(\d+)$", k)
            if m:
                nums.add(int(m.group(1)))
        missing = [n for n in range(1, a.expect + 1) if n not in nums]
        shown = ("none" if not missing else f"all {a.expect}" if len(missing) == a.expect
                 else ", ".join(str(n) for n in missing))
        print(f"  missing numbers: {shown}")
        twice = tag["external_key"].value_counts()
        print(f"  keys appearing twice: {list(twice[twice > 1].index) or 'none'}")
        already = sorted(set(tag["external_key"]) & held)
        print(f"  keys already in Observatum: {len(already)}")
        for k, v in Counter(tag["outcome"]).most_common():
            print(f"  {k}: {v}")
        ok = (len(tag) == a.expect and not missing and len(twice[twice > 1]) == 0)
        if len(tag):
            print("  RESULT: " + ("all keys came back once; the sync would add each once "
                                  "and keep its key as the Observatum key"
                                  if ok and set(tag["outcome"]) == {"add as new"} and not already
                                  else "see the CSV -- not the expected clean result"))

    out = a.csv or os.path.join(ROOT, "scripts", "_oneoff",
                                f"irecord_download_check_{datetime.date.today():%Y%m%d}.csv")
    pick = df[key.str.startswith(a.tag) | key.isin(obs_dup.index)] if a.tag else df[key.isin(obs_dup.index)]
    cols = ["row_number", "irecord_id", "external_key", "species_name", "date", "grid_ref",
            "site_name", "input_on_date", "outcome", "existing_record_id", "import_notes"]
    os.makedirs(os.path.dirname(out), exist_ok=True)
    pick[cols].to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\nRows written: {len(pick)} -> {out}")
    print(FINAL)
    return 0


if __name__ == "__main__":
    sys.exit(main())
