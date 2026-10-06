"""Three fixes from the October 2026 code analysis. All-or-nothing: every change is checked
before any file is written; each file gets a .bak and must compile; line endings kept.

 1. Examen: the "+ Add Manual Entry" route could empty codex.db manual_entries (DELETE of every
    row, then reload from the old codex_manual_entries.json) -- wiping every review status.
    The button is hidden and disconnected, and the dialog's codex write is disabled.
 2. Observatum observation filter, both client-side fallbacks (no repository, and after a
    repository error): passed 'observations' instead of 'filtered' -- a NameError, or the
    wrong list shown.
 3. vc_lookup_service: 'List' used in an annotation without being imported -- works only on
    Python 3.14; fails to load on 3.13 and earlier.

  python scripts\\patch_analysis_fixes_1_3.py          (refuses a second run)
"""
import os, py_compile, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHANGES = {
    "Examen/species_database_view.py": [(
        '''        self.manual_btn.clicked.connect(self._on_manual_entry)
        self.status_group.layout().addWidget(self.manual_btn)
''',
        '''        # "+ Add Manual Entry" removed (Oct 2026): its dialog emptied codex.db manual_entries,
        # which now holds every review status. Statuses come from review loads and the
        # withdraw / clear tools (scripts/), never from here.
        self.manual_btn.hide()
''')],
    "Examen/manual_entry_dialog.py": [(
        '''    """Write manual entries to codex.db manual_entries + rebuild status_summary rows."""
    if not paths.CODEX_DB.exists():
        return
''',
        '''    """DISABLED (Oct 2026). This replaced EVERY row of codex.db manual_entries with the old
    codex_manual_entries.json -- which would wipe all review statuses, withdrawals and
    clearances loaded since. Codex is written only by Codex Manager and the review scripts."""
    return
    if not paths.CODEX_DB.exists():
        return
''')],
    "Observatum/src/views/observations/observation_filter_mixin.py": [(
        '''            filtered = self._apply_filters(self._all_observations, filters)
            self.table_model.set_observations_fast(observations)
''',
        '''            filtered = self._apply_filters(self._all_observations, filters)
            self.table_model.set_observations_fast(filtered)
''', 2)],      # both fallbacks: no-repository path AND the repository-error path
    "Observatum/src/services/vc_lookup_service.py": [(
        '''from typing import Optional, Tuple, Dict, Any
''',
        '''from typing import Optional, Tuple, Dict, Any, List
''')],
}
MARK = "removed (Oct 2026): its dialog emptied codex.db"

plan = {}
for rel, reps in CHANGES.items():
    p = os.path.join(ROOT, *rel.split("/"))
    if not os.path.exists(p):
        sys.exit(f"  x {rel} not found -- nothing written")
    raw = open(p, "rb").read().decode("utf-8")
    crlf = "\r\n" in raw
    t = raw.replace("\r\n", "\n")
    if rel.endswith("species_database_view.py") and MARK in t:
        sys.exit("  already patched -- nothing done")
    for rep in reps:
        old, new = rep[0], rep[1]
        want = rep[2] if len(rep) > 2 else 1
        n = t.count(old)
        if n != want:
            sys.exit(f"  x {rel}: expected {want} match(es), found {n} -- nothing written:\n      {old.strip()[:80]}")
        t = t.replace(old, new)
    plan[p] = (t.replace("\n", "\r\n") if crlf else t, rel)

# compile every patched file before writing any
for p, (text, rel) in plan.items():
    tmp = p + ".tmp"
    open(tmp, "wb").write(text.encode("utf-8"))
    try:
        py_compile.compile(tmp, doraise=True)
    except py_compile.PyCompileError as e:
        for q in plan:
            if os.path.exists(q + ".tmp"):
                os.remove(q + ".tmp")
        sys.exit(f"  x {rel} would not compile -- nothing written: {e}")
for p, (text, rel) in plan.items():
    shutil.copy2(p, p + ".bak")
    os.replace(p + ".tmp", p)
    print(f"  patched {rel}  (backup .bak)")
print("  1 Examen manual-entry route disabled   2 filter fallback fixed   3 List imported")
