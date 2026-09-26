"""Point Observatum's five profile loaders at the one shared reader.

  ic_sidebar_mixin.py           specimen detail
  add_specimen_dialog.py        profile preview in Add/Edit Specimen
  observation_detail_mixin.py   _load_species_profile
  recording_scheme_tab.py       _load_species_profile (was name-only)
  species_info.py               _load_profile -- _current_profile now holds YOUR
                                text only; the preview may show the review's

Each replaces its own "SELECT profile_text ... by TVK, else by name" with
shared.species_accounts. Writes NOTHING unless every marker in every file is
found. Backups: *.bak_accounts. Compiles each file; view modules are not
imported (05_Rules.md -- it drags in the app's import chain).

Run:  python scripts\\patch_profile_readers.py
"""
import io, os, py_compile, re, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V = os.path.join(ROOT, "Observatum", "src", "views")

EDITS = [
    ("collection/ic_sidebar_mixin.py",
     lambda l: l.strip() == "# Get profile text if available",
     lambda l: 'print(f"[InsectCollectionTab] Error loading profile: {e}")' in l,
     '''# Profile text -- your account, else the review's, via the one shared reader
profile_text = None
try:
    from shared.species_accounts import get_preview_text
    profile_text = get_preview_text(_get_attr(specimen, 'species_tvk'), species_name)
except Exception as e:
    print(f"[InsectCollectionTab] Error loading profile: {e}")'''),

    ("dialogs/add_specimen_dialog.py",
     lambda l: l.strip() == "# Try by TVK first, then by name",
     lambda l: l.strip() == "self._update_profile_display(profile_text)",
     '''# Your account, else the review's, via the one shared reader
from shared.species_accounts import get_preview_text
profile_text = get_preview_text(species_tvk, species_name)
self._update_profile_display(profile_text)'''),

    ("observations/observation_detail_mixin.py",
     lambda l: l.strip().startswith("def _load_species_profile(self, species_tvk"),
     lambda l: l.strip() == "return profile_text",
     '''def _load_species_profile(self, species_tvk: str, species_name: str) -> str:
    """Profile text for display -- via the one shared reader."""
    try:
        from shared.species_accounts import get_preview_text
        return get_preview_text(species_tvk, species_name)
    except Exception as e:
        print(f"[ObservationTab] Error loading profile: {e}")
        return None'''),

    ("scheme/recording_scheme_tab.py",
     lambda l: l.strip().startswith("def _load_species_profile(self, record"),
     lambda l: l.strip() == "return profile_text",
     '''def _load_species_profile(self, record: dict) -> str:
    """Profile text for display -- via the one shared reader (TVK, else name)."""
    species_name = record.get('species') or record.get('species_name', '')
    tvk = record.get('species_tvk') or record.get('tvk')
    if not (species_name or tvk):
        return None
    try:
        from shared.species_accounts import get_preview_text
        return get_preview_text(tvk, species_name)
    except Exception as e:
        print(f"[RecordingSchemeTab] Error loading profile: {e}")
        return None'''),

    ("home/species_info.py",
     lambda l: l.strip().startswith("def _load_profile(self, tvk"),
     lambda l: l.strip() == 'print(f"Error loading profile: {e}")',
     '''def _load_profile(self, tvk: str):
    """Load the profile preview -- via the one shared reader.

    _current_profile holds YOUR account only. The preview may show the
    review's text, cited, but it must never become editable text of yours.
    """
    t = theme()
    self._current_profile = ""
    self.profile_preview.clear()
    self.profile_btn.setText("Create")

    if not tvk:
        return

    try:
        from shared.species_accounts import get_species_accounts
        acc = get_species_accounts(tvk)
        self._current_profile = acc.own or ""
        text = acc.preview_text()
        if text:
            preview = text[:300]
            if len(text) > 300:
                preview += "..."
            self.profile_preview.setText(preview)
            self.profile_btn.setText("View")
    except Exception as e:
        print(f"Error loading profile: {e}")'''),
]

print("Patching profile loaders -> shared.species_accounts")
print("=" * 72)

if not os.path.exists(os.path.join(ROOT, "shared", "species_accounts.py")):
    print("  x shared/species_accounts.py is missing -- ABORTED, nothing written")
    sys.exit(1)

planned, problems = [], []
for rel, spred, epred, body in EDITS:
    p = os.path.join(V, *rel.split("/"))
    if not os.path.exists(p):
        problems.append(f"{rel}: file not found")
        continue
    raw = io.open(p, "rb").read()
    bom = raw.startswith(b"\xef\xbb\xbf")
    lines = raw.decode("utf-8-sig").split("\n")
    starts = [i for i, l in enumerate(lines) if spred(l.rstrip("\r"))]
    if len(starts) != 1:
        problems.append(f"{rel}: start marker found {len(starts)} times")
        continue
    s = starts[0]
    e = next((i for i in range(s, min(len(lines), s + 45)) if epred(lines[i].rstrip("\r"))), None)
    if e is None:
        problems.append(f"{rel}: end marker not found within 45 lines")
        continue
    first = lines[s].rstrip("\r")
    ind = first[:len(first) - len(first.lstrip())]
    eol = "\r" if lines[s].endswith("\r") else ""
    new = [(ind + b if b else "") + eol for b in body.split("\n")]
    planned.append((rel, p, lines, s, e, new, bom))

if problems:
    for x in problems:
        print(f"  x {x}")
    print("\nABORTED -- nothing written.")
    sys.exit(1)

for rel, p, lines, s, e, new, bom in planned:
    shutil.copy2(p, p + ".bak_accounts")
    lines[s:e + 1] = new
    io.open(p, "w", encoding="utf-8-sig" if bom else "utf-8", newline="").write("\n".join(lines))
    try:
        py_compile.compile(p, doraise=True)
        print(f"  ok {rel}  (lines {s + 1}-{e + 1} -> {len(new)} lines, compiles)")
    except py_compile.PyCompileError as ex:
        shutil.copy2(p + ".bak_accounts", p)
        print(f"  x {rel}: COMPILE FAILED -- this file restored\n{ex}")

# Remaining direct reads of species_profiles in the views -- should be the editor only
print("\n  Remaining species_profiles queries under Observatum/src/views:")
for d, _, files in os.walk(V):
    for f in files:
        if f.endswith(".py") and ".bak" not in f:
            fp = os.path.join(d, f)
            for i, l in enumerate(io.open(fp, encoding="utf-8", errors="replace"), 1):
                if "FROM species_profiles" in l or "INTO species_profiles" in l \
                        or "UPDATE species_profiles" in l:
                    print(f"    {os.path.relpath(fp, ROOT)}:{i}")

# Where the editor is opened, and with what -- the seeding risk
print("\n  Where SpeciesProfileDialog is opened (check what text it is handed):")
for d, _, files in os.walk(os.path.join(ROOT, "Observatum", "src")):
    for f in files:
        if f.endswith(".py") and ".bak" not in f and f != "species_profile_dialog.py":
            fp = os.path.join(d, f)
            ls = io.open(fp, encoding="utf-8", errors="replace").read().splitlines()
            for i, l in enumerate(ls):
                if re.search(r"SpeciesProfileDialog\(", l):
                    print(f"    {os.path.relpath(fp, ROOT)}:{i + 1}")
                    for j in range(i, min(len(ls), i + 7)):
                        print(f"      {ls[j].rstrip()}")

print("\nDone. Open Observatum and look at a leaf beetle's specimen or record.")
