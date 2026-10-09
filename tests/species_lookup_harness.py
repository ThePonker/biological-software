"""Characterisation harness for the import wizards' species lookup (backlog C4, 9 Oct 2026).

Feeds a fixed list of species-name strings through each import wizard's validation worker
-- observation (iRecord sync and personal upload), specimen, scheme (iRecord, NBN Atlas,
generic CSV) -- against the real data/uksi.db, and records what comes out: the species
columns after the lookup step, and the finished import rows.

Recorded in tests/golden/species_lookup_golden.json; test_species_lookup_characterisation.py
checks the wizards still give the same answers. First recorded from the three original lookups
(C4, 9 Oct 2026); re-recorded the same evening for the one rule set (fix round items 13-15:
exact names and synonyms only, search hits are suggestions, Species over s.l., UKSI names
stored, saved aliases no longer used).

After a deliberate change to species matching (or a new uksi.db), regenerate:

    py -3.14 tests\\species_lookup_harness.py --write

Read-only: uksi.db and observatum.db are opened with ?mode=ro; the workers get no
database manager, so the duplicate checks do not run.
"""
from __future__ import annotations

import dataclasses
import json
import math
import os
import sqlite3
import sys
from enum import Enum

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (ROOT, os.path.join(ROOT, "Observatum")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

DATA = os.path.join(ROOT, "data")
UKSI_DB = os.path.join(DATA, "uksi.db")
OBS_DB = os.path.join(DATA, "observatum.db")
GOLDEN = os.path.join(ROOT, "tests", "golden", "species_lookup_golden.json")  # not tests/data: git ignores data/

# Names that exercise the awkward paths, whatever the databases hold.
TRICKY = [
    "", "   ",
    "Carabus nemoralis", "carabus nemoralis", "CARABUS NEMORALIS", "Carabus  nemoralis",
    "Carabus nemoralis ", " Carabus nemoralis",
    "Carabus cf. nemoralis", "Carabus cf nemoralis", "Carabus CF. nemoralis", "Carabus cf. nemorallis",
    "Anthocoris cf. confusus", "Bombus cf. lucorum",
    "Bombus lucorum agg.", "Bombus lucorum agg", "Bombus lucorum AGG.", "Bombus lucorum agg. ",
    "Bombus lucorum/terrestris agg.", "Rubus fruticosus agg.", "Cochlicopa lubrica agg.",
    "Amphipyra pyramidea agg.", "Leiopus linnei/nebulosus agg.", "Nosuchgenus nosuchus agg.",
    "Bombus lucorum s.l.", "Bombus lucorum sensu lato", "Cheilosia albitarsis sens.lat.",
    "Bombus lucorum", "Bombus terrestris",
    "Rutpela maculata", "Rutpela maculta", "Rutpla maculata", "Strangalia maculata",
    "Leptura maculata", "Gyrinus thomsoni", "Gyrinus edwardsi", "Sphaerius obsidianus",
    "Coccinella septempunctata", "Coccinella 7-punctata", "7-spot Ladybird", "Seven-spot Ladybird",
    "Stag Beetle", "Lucanus cervus", "Wasp Beetle", "Clytus arietis", "Clytus",
    "Lepturinae", "Cerambycidae", "Coleoptera",
    "Aneurus avenius", "Aneurus (Aneurodes) avenius", "Nabis rugosus", "Nabis (Nabis) rugosus",
    "Himacerus apterus", "Tingis ampliata", "Plagiognathus chrysanthemi",
    "Pieris napi britannica", "Pieris napi subsp. britannica", "Aglais io", "Inachis io",
    "Leiopus sp.", "Leiopus spp.", "Leiopus", "Leiopus nebulosus", "Leiopus linnei",
    "Cantharis flavilabris (=nigra auctt.)", "Ceutorhynchus obstrictus (=assimilis auctt.)",
    "Dicranopalpus ramosus sensu lato (pre 2015)",
    "Xylotrechus arvicola", "Tetrops starkii", "Tetrops starki",
    "Aleochara sp. indet.", "Notarealname", "Qq", "x", "Ab",
    "Phyllobius pomaceus/glaucus", "Anoplodera sexguttata", "Stenurella melanura",
    "Grammoptera ruficornis", "Grammoptera ruficornis ruficornis", "Gramoptera ruficornis",
    "Pyrochroa serraticornis", "Oedemera nobilis", "Malachius bipustulatus",
    # agg. where UKSI has no aggregate: the wizards fall back differently
    "Carabus nemoralis agg.", "Rutpela maculata agg.", "Coccinella septempunctata agg",
    "Strangalia maculata agg.", "Seven-spot Ladybird agg.", "Nosuchgenus cf. nosuchus",
    "Carabus cf. Nemoralis", "Strangalia cf. maculata", "Rutpla cf. maculata",
]

def _ro(path):
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def real_names(per_table=(160, 110, 90)):
    """A deterministic sample of real names, plus every awkward-looking one."""
    c = _ro(OBS_DB)
    out = []
    try:
        for table, n in zip(("observations", "specimens", "recording_scheme"), per_table):
            names = sorted({r[0] for r in c.execute(f"SELECT DISTINCT species_name FROM {table}") if r[0]})
            step = max(1, len(names) // n)
            out += names[::step][:n]
            out += [s for s in names if any(k in s for k in ("cf", "agg", "s.l", "sens", "(", " sp"))
                    or " " not in s.strip()]
    finally:
        c.close()
    return out


def all_names():
    seen, out = set(), []
    for s in TRICKY + real_names():
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def uksi_fingerprint():
    c = _ro(UKSI_DB)
    try:
        return "|".join(str(c.execute(f"SELECT COUNT(*), MAX(rowid) FROM {t}").fetchone())
                        for t in ("taxa", "synonyms", "common_names"))
    finally:
        c.close()


def stub_webengine():
    """Importing src.views pulls in the map (QtWebEngine), absent on a headless test machine."""
    import importlib.machinery
    import importlib.util
    import types
    if "PySide6.QtWebEngineWidgets" in sys.modules or importlib.util.find_spec("PySide6.QtWebEngineWidgets"):
        return
    from PySide6.QtWidgets import QWidget
    for m in ("PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineCore", "PySide6.QtWebChannel"):
        mod = types.ModuleType(m)
        mod.__spec__ = importlib.machinery.ModuleSpec(m, None)      # other tests call find_spec
        for n in ("QWebEngineView", "QWebEnginePage", "QWebEngineSettings", "QWebEngineProfile", "QWebChannel"):
            setattr(mod, n, type(n, (QWidget,), {}))
        sys.modules.setdefault(m, mod)


def uksi_model():
    from src.models.database import DatabaseManager
    from src.models.uksi import UKSIModel
    db = DatabaseManager()
    db.set_uksi_path(UKSI_DB)          # read-only connection (connect_ro)
    return UKSIModel(db)


# ---------------------------------------------------------------- plain values for JSON

def plain(v):
    if isinstance(v, Enum):
        return v.value
    if v is None or isinstance(v, (str, bool)):
        return v
    if hasattr(v, "item") and not isinstance(v, (list, dict)):
        v = v.item()                                     # numpy scalar
    if isinstance(v, float):
        if math.isnan(v):
            return "<NaN>"
        return v
    if isinstance(v, int):
        return v
    if isinstance(v, (list, tuple)):
        return [plain(x) for x in v]
    if isinstance(v, dict):
        return {str(k): plain(x) for k, x in v.items()}
    return repr(v)


SPECIES_COLS = ["species_name", "species_tvk", "matched_name", "common_name", "order_name", "family",
                "kingdom", "phylum", "class_name", "genus", "taxon_group", "taxon_rank",
                "taxonomic_sort_key", "superfamily", "subfamily",
                "species_error", "species_warning", "import_notes"]


def frame_rows(df):
    cols = [c for c in SPECIES_COLS if c in df.columns]
    return [{c: plain(r[c]) for c in cols} for _, r in df.iterrows()]


ROW_FIELDS = {"row_number", "species_name", "species_tvk", "common_name", "order_name", "family",
              "kingdom", "phylum", "class_name", "genus", "taxon_group", "taxon_rank", "subfamily",
              "superfamily", "taxonomic_sort_key", "status", "error_message", "warnings", "import_notes"}
FULL = "--full" in sys.argv          # every field of every row (a local check; too big to keep)


def row_dicts(rows):
    out = []
    for r in rows:
        d = dataclasses.asdict(r)
        d.pop("raw_data", None)
        if not FULL:
            d = {k: v for k, v in d.items() if k in ROW_FIELDS}
        out.append(plain(d))
    return out


# ---------------------------------------------------------------- the workers

def _run(worker):
    got = []
    worker.finished.connect(lambda rows: got.extend(rows))
    worker.run()
    return got


def capture_specimen(names, model):
    from src.views.dialogs.specimen_import_wizard.validation_worker import ImportRow, ValidationWorker
    mapping = {"species_name": "Species"}

    def make():
        rows = [ImportRow(row_number=i + 2, raw_data={"Species": n}) for i, n in enumerate(names)]
        return ValidationWorker(rows, mapping, model, vc_db_path=None)
    w = make()
    frame = frame_rows(w._batch_species_lookup(w._build_dataframe()))
    return {"frame": frame, "rows": row_dicts(_run(make()))}


def capture_observation(names, model, mode_name, tvks=None):
    from src.views.dialogs.observation_import_wizard.validation_worker import (
        ImportMode, ObservationImportRow, ObservationValidationWorker)
    mode = ImportMode[mode_name]
    tvks = tvks or {}
    if mode == ImportMode.IRECORD_SYNC:
        raws = [{"ID": str(1000 + i), "Taxon": n, "TaxonVersionKey": tvks.get(n, ""),
                 "Date interpreted": "01/06/2024", "Recorder": "Test"} for i, n in enumerate(names)]
        mapping = {}
    else:
        raws = [{"Species": n, "Date": "01/06/2024", "Recorder": "Test"} for n in names]
        mapping = {"species_name": "Species", "date": "Date", "recorder": "Recorder"}

    def make():
        rows = [ObservationImportRow(row_number=i + 2, raw_data=r) for i, r in enumerate(raws)]
        return ObservationValidationWorker(rows=rows, column_mapping=mapping, import_mode=mode,
                                           uksi_model=model, vc_db_path=None, db_manager=None)
    w = make()
    frame = frame_rows(w._batch_species_lookup(w._build_dataframe()))
    return {"frame": frame, "rows": row_dicts(_run(make()))}


def capture_scheme(names, model, mode_name, tvks=None):
    from src.views.dialogs.scheme_import_wizard.validation_worker import (
        SchemeImportMode, SchemeImportRow, SchemeValidationWorker)
    mode = SchemeImportMode[mode_name]
    tvks = tvks or {}
    if mode == SchemeImportMode.IRECORD:
        raws = [{"ID": str(1000 + i), "Taxon": n, "TaxonVersionKey": tvks.get(n, ""),
                 "Date interpreted": "01/06/2024"} for i, n in enumerate(names)]
    elif mode == SchemeImportMode.NBN_ATLAS:
        raws = [{"recordID": f"N{i}", "scientificName": n, "taxonID": tvks.get(n, ""),
                 "eventDate": "2024-06-01"} for i, n in enumerate(names)]
    else:
        raws = [{"Species": n, "Date": "01/06/2024"} for n in names]
    mapping = {"species_name": "Species", "date": "Date"}

    def make():
        rows = [SchemeImportRow(row_number=i + 2, raw_data=r) for i, r in enumerate(raws)]
        return SchemeValidationWorker(rows=rows, import_mode=mode, column_mapping=mapping,
                                      uksi_model=model, vc_db_path=None, db_manager=None)
    w = make()
    frame = frame_rows(w._batch_species_lookup(w._build_dataframe()))
    return {"frame": frame, "rows": row_dicts(_run(make()))}


def given_tvks(names, model):
    """Every third name arrives with a TVK, every ninth with a wrong one (iRecord / NBN files)."""
    exact = model.get_species_batch([n for n in names if n.strip()])
    out = {}
    for i, n in enumerate(names):
        hit = exact.get(n)
        if hit and i % 3 == 0:
            out[n] = hit.tvk
        elif i % 9 == 1 and n.strip():
            out[n] = "NHMSYS0000000000"
    return out


def capture_all(names=None):
    """Run every worker. The test passes the names stored in the golden file, so new records
    in observatum.db do not change what is checked."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    stub_webengine()
    names = all_names() if names is None else names
    model = uksi_model()
    tvks = given_tvks(names, model)
    return {
        "uksi": uksi_fingerprint(),
        "names": names,
        "specimen": capture_specimen(names, model),
        "observation_personal": capture_observation(names, model, "PERSONAL_UPLOAD"),
        "observation_irecord": capture_observation(names, model, "IRECORD_SYNC", tvks),
        "scheme_generic": capture_scheme(names, model, "GENERIC_CSV"),
        "scheme_irecord": capture_scheme(names, model, "IRECORD", tvks),
        "scheme_nbn": capture_scheme(names, model, "NBN_ATLAS", tvks),
    }


META = ("uksi", "names")


def dumps(result):
    """JSON with one record per line: compact, and a change shows as a one-line diff."""
    def one(v):
        return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    parts = [f'"uksi":{one(result["uksi"])}', '"names":[\n' + ",\n".join(one(n) for n in result["names"]) + "]"]
    for key in sorted(k for k in result if k not in META):
        blocks = []
        for part in ("frame", "rows"):
            recs = result[key][part]
            cols = sorted({c for r in recs for c in r})
            body = ",\n".join(one([r.get(c, "<absent>") for c in cols]) for r in recs)
            blocks.append(f'"{part}":{{"cols":{one(cols)},"data":[\n{body}]}}')
        parts.append(f'"{key}":{{' + ",\n".join(blocks) + "}")
    return "{" + ",\n".join(parts) + "}\n"


def loads(text):
    """The inverse of dumps()."""
    raw = json.loads(text)
    raw.pop("aliases", None)                 # golden files recorded before 9 Oct evening
    out = {k: raw.pop(k) for k in META}
    for key, parts in raw.items():
        out[key] = {part: [{c: v for c, v in zip(p["cols"], row) if v != "<absent>"} for row in p["data"]]
                    for part, p in parts.items()}
    return out


if __name__ == "__main__":
    import time
    t0 = time.time()
    result = capture_all()
    print(f"{len(result['names'])} names, {time.time() - t0:.1f} s")
    out = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--out=")), GOLDEN)
    if "--write" in sys.argv:
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            f.write(dumps(result))
        print("written", out)
    else:
        print("(not written; add --write)")
