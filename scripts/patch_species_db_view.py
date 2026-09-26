"""patch_species_db_view.py -- fix the 8-track status panel in Examen.

    python scripts/patch_species_db_view.py

The fault
---------
Examen/species_database_view.py._display_codex_status reads SpeciesStatus using
the PRE-APRIL 8-track attribute names:

    gb_red_list, gb_red_list_legacy, gb_rarity, gb_rarity_legacy,
    section_41, bap, legal_protection, global_red_list

Only `legal_protection` still exists. So:

  * every other track returns "" from getattr(status, attr, "") and is silently
    skipped -- the Conservation status panel has shown NOTHING for any species
    since the April rebuild
  * `legal_protection` IS present but is a list[StatusEntry], so it is truthy,
    reaches QLabel(val), and raises:
        TypeError: QLabel.__init__ called with wrong argument types (list)

So the panel is either empty or crashes. It crashes for any legally protected
species, which is why it surfaced now.

This is the fourth instance of the same 8-track drift, and the seventh
never-executed-or-untested path found this year.

The fix
-------
Read the real 11-track fields. Each is either an Optional[StatusEntry] or a
list[StatusEntry] (legal_protection, priority), so both shapes are handled and
the entry's .value / .detail / .source are used rather than the object itself.

Line-based patching: the file's line endings are not guaranteed, so this locates
marker lines and replaces ranges rather than matching multi-line strings.

Safe to re-run. Backs up as species_database_view.py.bak_fix1.
"""
import os
import shutil
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(_ROOT, "Examen", "species_database_view.py")
BACKUP = TARGET + ".bak_fix1"

NEW_LABELS = '''TRACK_LABELS = {
    "threat_iucn_2001": "GB Red List (2001 IUCN)",
    "threat_iucn_2001_breeding": "GB Red List (breeding)",
    "threat_iucn_2001_nonbreeding": "GB Red List (non-breeding)",
    "threat_iucn_legacy": "GB Red List (pre-2001)",
    "threat_global_iucn": "Global Red List",
    "rarity_modern": "GB Rarity",
    "rarity_legacy": "GB Rarity (legacy)",
    "bocc": "Birds of Conservation Concern",
    "specialist_panel": "Specialist panel",
    "red_list_england": "England Red List",
    "red_list_wales": "Wales Red List",
    "legal_protection": "Legal protection",
    "priority": "Priority listing",
}

# Single-entry tracks, in display order.
SINGLE_TRACKS = [
    "threat_iucn_2001", "threat_iucn_2001_breeding", "threat_iucn_2001_nonbreeding",
    "threat_iucn_legacy", "threat_global_iucn",
    "rarity_modern", "rarity_legacy",
    "bocc", "specialist_panel",
    "red_list_england", "red_list_wales",
]

# Tracks carrying a list of entries -- a species can hold several.
LIST_TRACKS = ["legal_protection", "priority"]

SEVERE = {"CR", "EN", "VU", "NR", "RDB1", "RDB2", "RE", "EX", "EW"}
MODERATE = {"NT", "NS", "Na", "Nb", "RDB3", "RDBK", "Notable", "DD", "Amber"}
'''

NEW_METHOD = '''    def _display_codex_status(self, tvk):
        while self.status_grid.count():
            w = self.status_grid.takeAt(0).widget()
            if w: w.deleteLater()
        if not tvk:
            self.status_group.hide(); self.sqs_label.setText(""); return
        try: status = self._codex.get_status_summary(tvk)
        except FileNotFoundError: self.status_group.hide(); self.sqs_label.setText(""); return

        # Build (track, value, detail, source) rows from the 11-track model.
        # Single-entry tracks hold an Optional[StatusEntry]; list tracks hold
        # a list of them, so a species can show several priority listings.
        rows = []
        for track in SINGLE_TRACKS:
            entry = getattr(status, track, None)
            if entry is not None and getattr(entry, "value", ""):
                rows.append((track, entry.value,
                             getattr(entry, "detail", "") or "",
                             getattr(entry, "source", "") or ""))
        for track in LIST_TRACKS:
            for entry in getattr(status, track, None) or []:
                if getattr(entry, "value", ""):
                    rows.append((track, entry.value,
                                 getattr(entry, "detail", "") or "",
                                 getattr(entry, "source", "") or ""))

        if rows:
            self.status_group.show()
            for i, (track, val, detail, source) in enumerate(rows):
                tl = QLabel(TRACK_LABELS.get(track, track))
                tl.setStyleSheet("color: " + TEXT_SECONDARY + "; font-size: 11px; border: none;")
                self.status_grid.addWidget(tl, i, 0)
                # Detail carries the instrument or jurisdiction, which is the
                # useful part for legal_protection and priority.
                shown = f"{val} \\u2014 {detail}" if detail and detail != val else val
                vl = QLabel(shown)
                vl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
                c = RED_STATUS if val in SEVERE else (AMBER if val in MODERATE else ACCENT_DARK)
                vl.setStyleSheet("color: " + c + "; border: none;")
                vl.setWordWrap(True)
                self.status_grid.addWidget(vl, i, 1)
                sl = QLabel(source)
                sl.setStyleSheet("color: " + TEXT_MUTED + "; font-size: 10px; border: none;")
                sl.setWordWrap(True)
                self.status_grid.addWidget(sl, i, 2)
        else: self.status_group.hide()
        if status.sqs:
            self.sqs_label.setText(f"Species Quality Score (SQS): {status.sqs}")
            self.sqs_label.setStyleSheet("font-size: 12px; color: " + ACCENT_DARK + "; font-weight: bold;")
        else: self.sqs_label.setText("")
'''


def find_line(lines, startswith, after=0):
    for i in range(after, len(lines)):
        if lines[i].startswith(startswith):
            return i
    return -1


def main():
    if not os.path.exists(TARGET):
        print(f"NOT FOUND: {TARGET}")
        return 1

    with open(TARGET, "r", encoding="utf-8", newline="") as f:
        raw = f.read()
    ending = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.splitlines()

    print("")
    print("Patching Examen/species_database_view.py -- 11-track status panel")
    print("=" * 70)

    if "SINGLE_TRACKS" in raw:
        print("  = already patched -- nothing to do")
        return 0

    # --- 1. TRACK_LABELS .. MODERATE block --------------------------------
    start = find_line(lines, "TRACK_LABELS = {")
    end = find_line(lines, "MODERATE = {", start if start >= 0 else 0)
    if start < 0 or end < 0:
        print("  x could not locate TRACK_LABELS..MODERATE block")
        return 1
    print(f"  + vocabulary block   lines {start + 1}-{end + 1}")

    # --- 2. _display_codex_status ----------------------------------------
    m_start = find_line(lines, "    def _display_codex_status(self, tvk):")
    if m_start < 0:
        print("  x could not locate _display_codex_status")
        return 1
    m_end = find_line(lines, "    def _display_pantheon_ecology(self, tvk):", m_start)
    if m_end < 0:
        print("  x could not locate the following method")
        return 1
    print(f"  + _display_codex_status  lines {m_start + 1}-{m_end}")

    new_lines = (
        lines[:start]
        + NEW_LABELS.split("\n")
        + lines[end + 1:m_start]
        + NEW_METHOD.split("\n")
        + lines[m_end:]
    )

    shutil.copy2(TARGET, BACKUP)
    print(f"  backup written: {os.path.basename(BACKUP)}")

    with open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(ending.join(new_lines) + ending)

    print("")
    print("  Checking the file still compiles...")
    try:
        import py_compile
        py_compile.compile(TARGET, doraise=True)
        print("  + compiles cleanly")
    except Exception as e:  # noqa: BLE001
        print(f"  x COMPILE FAILED: {e}")
        print(f"    restore: copy {os.path.basename(BACKUP)} species_database_view.py")
        return 1

    print("")
    print("  NEXT: python -m Examen  -> Species Database -> search a protected")
    print("  species (e.g. Lucanus cervus) and confirm the status panel fills")
    print("  rather than crashing.")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
