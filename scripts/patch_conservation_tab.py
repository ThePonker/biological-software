"""patch_conservation_tab.py -- read structured tracks, not display strings.

    python scripts/patch_conservation_tab.py

Run patch_key_species_tracks.py FIRST -- this reads the fields it adds.

The fault
---------
conservation_tab._parse_status reverse-engineers status codes out of the
short_status display string. For a priority species short_status is the literal
"Priority", which matches no token, so every priority species falls through to
the tier fallback and is labelled "S41" -- whichever jurisdiction actually
listed it. Glory Park reports "Section 41: 4" without reading Section 41 at all.

CATEGORIES also has no bocc, red_list_england, red_list_wales or
threat_global_iucn, and collapses all legal instruments to "WCA".

The fix
-------
Read KeySpeciesEntry.rarity / .threat / .threat_legacy / .priority / .legal
directly. Each priority jurisdiction and each legal instrument is counted under
its own name, so a Scottish or Welsh listing is reported as itself.

Also fixed while here:
  * bar width was `count * 40` capped at 200, so 5 species and 50 both filled
    the bar. Now scaled against the largest count in the group.
  * `opacity: 0.7` does nothing in a Qt stylesheet -- removed.

Line-based patching, because the file's line endings are not guaranteed.

Safe to re-run. Backs up as conservation_tab.py.bak_fix1.
"""
import os
import shutil
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(_ROOT, "Examen", "conservation_tab.py")
BACKUP = TARGET + ".bak_fix1"

NEW_CATEGORIES = '''# Status categories in display order.
# Threat and rarity codes are fixed vocabularies. Priority jurisdictions and
# legal instruments are open sets -- whatever Codex holds is shown -- so they
# are handled separately below rather than listed here.
CATEGORIES = [
    ("Threat status (GB, 2001 IUCN)", [
        ("CR", "Critically Endangered", RED_STATUS),
        ("EN", "Endangered", RED_STATUS),
        ("VU", "Vulnerable", "#d97706"),
        ("NT", "Near Threatened", AMBER),
        ("DD", "Data Deficient", AMBER),
    ]),
    ("Threat status (pre-2001)", [
        ("RDB1", "Red Data Book 1", RED_STATUS),
        ("RDB2", "Red Data Book 2", RED_STATUS),
        ("RDB3", "Red Data Book 3", AMBER),
        ("RDBK", "Red Data Book K", AMBER),
    ]),
    ("Rarity (current)", [
        ("NR", "Nationally Rare", RED_STATUS),
        ("NS", "Nationally Scarce", AMBER),
    ]),
    ("Rarity (legacy)", [
        ("Na", "Notable A", AMBER),
        ("Nb", "Notable B", "#92774e"),
        ("Notable", "Notable", "#92774e"),
    ]),
]

PRIORITY_GROUP = "Priority listings"
LEGAL_GROUP = "Legal protection"
'''

NEW_SET_RESULT = '''    def set_result(self, result, detail=None):
        for w in self._widgets:
            w.deleteLater()
        self._widgets.clear()

        # Counts come from the structured tracks on each key species, not from
        # parsing a display string. Priority jurisdictions and legal instruments
        # are counted under their own names.
        status_counts = {}
        priority_counts = {}
        legal_counts = {}
        for k in result.key_species:
            for code in (getattr(k, "rarity", ""), getattr(k, "threat", ""),
                         getattr(k, "threat_legacy", "")):
                if code:
                    status_counts[code] = status_counts.get(code, 0) + 1
            for j in getattr(k, "priority", None) or []:
                priority_counts[j] = priority_counts.get(j, 0) + 1
            for inst in getattr(k, "legal", None) or []:
                legal_counts[inst] = legal_counts.get(inst, 0) + 1

        total_key = result.key_species_count
        total_species = result.total_species

        hdr = QLabel(f"{total_key} key species of {total_species} total "
                      f"({result.key_species_pct}%)")
        hdr.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        hdr.setStyleSheet("color: " + ACCENT_DARK + ";")
        self._layout.insertWidget(self._layout.count(), hdr)
        self._widgets.append(hdr)

        for group_name, statuses in CATEGORIES:
            rows = [(code, label, colour, status_counts.get(code, 0))
                    for code, label, colour in statuses]
            rows = [r for r in rows if r[3] > 0]
            if rows:
                self._add_group(group_name, rows)

        # Open-set groups, most frequent first.
        if priority_counts:
            self._add_group(PRIORITY_GROUP, [
                (self._abbrev(j), j, MOSS_GREEN, n)
                for j, n in sorted(priority_counts.items(), key=lambda kv: -kv[1])])
        if legal_counts:
            self._add_group(LEGAL_GROUP, [
                ("", inst, ACCENT_DARK, n)
                for inst, n in sorted(legal_counts.items(), key=lambda kv: -kv[1])])

        self._add_guilds(result)

    @staticmethod
    def _abbrev(jurisdiction):
        """Short code for a priority jurisdiction, for the left-hand column."""
        j = (jurisdiction or "").lower()
        if "s.41" in j or "s41" in j or "section 41" in j:
            return "S41"
        if "wales" in j or "s7" in j:
            return "S7"
        if "scottish" in j:
            return "SBL"
        if "northern ireland" in j or j.startswith("ni "):
            return "NI"
        if "bap" in j:
            return "BAP"
        return ""

    def _add_group(self, group_name, rows):
        grp = QFrame()
        grp.setStyleSheet("QFrame { background: " + SURFACE + "; border: 1px solid "
                           + BORDER + "; border-radius: 6px; }")
        gl = QVBoxLayout(grp); gl.setContentsMargins(12, 10, 12, 10); gl.setSpacing(6)

        title = QLabel(group_name)
        title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        title.setStyleSheet("color: " + TEXT_HEADING + "; border: none;")
        gl.addWidget(title)

        # Bars are scaled against the largest count in this group, so the
        # lengths mean something. Previously count * 40 capped at 200, which
        # filled the bar for anything over five species.
        peak = max(r[3] for r in rows) or 1

        for code, label, colour, count in rows:
            row = QHBoxLayout(); row.setSpacing(8)

            code_lbl = QLabel(code)
            code_lbl.setFixedWidth(50)
            code_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            code_lbl.setStyleSheet(f"color: {colour}; border: none;")
            row.addWidget(code_lbl)

            desc_lbl = QLabel(label)
            desc_lbl.setFixedWidth(200)
            desc_lbl.setWordWrap(True)
            desc_lbl.setStyleSheet("color: " + TEXT_SECONDARY + "; font-size: 11px; border: none;")
            row.addWidget(desc_lbl)

            bar_container = QFrame()
            bar_container.setFixedHeight(18)
            bar_container.setStyleSheet("background: " + BG + "; border-radius: 3px; border: none;")
            bar = QFrame(bar_container)
            bar.setFixedSize(max(6, int(200 * count / peak)), 18)
            bar.setStyleSheet(f"background: {colour}; border-radius: 3px;")
            row.addWidget(bar_container, 1)

            count_lbl = QLabel(str(count))
            count_lbl.setFixedWidth(30)
            count_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            count_lbl.setStyleSheet(f"color: {colour}; border: none;")
            count_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            row.addWidget(count_lbl)

            gl.addLayout(row)

        self._layout.insertWidget(self._layout.count(), grp)
        self._widgets.append(grp)

    def _add_guilds(self, result):
        if not (result.larval_guild_counts or result.adult_guild_counts):
            return
        guild_frame = QFrame()
        guild_frame.setStyleSheet("QFrame { background: " + SURFACE + "; border: 1px solid "
                                   + BORDER + "; border-radius: 6px; }")
        gfl = QVBoxLayout(guild_frame); gfl.setContentsMargins(12, 10, 12, 10); gfl.setSpacing(4)
        gt = QLabel("Feeding guilds")
        gt.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        gt.setStyleSheet("color: " + TEXT_HEADING + "; border: none;")
        gfl.addWidget(gt)

        for label, counts in [("Larval", result.larval_guild_counts),
                               ("Adult", result.adult_guild_counts)]:
            if counts:
                top = sorted(counts.items(), key=lambda x: -x[1])[:6]
                text = f"{label}: " + ", ".join(f"{k} ({v})" for k, v in top)
                gl_lbl = QLabel(text)
                gl_lbl.setWordWrap(True)
                gl_lbl.setStyleSheet("color: " + TEXT_SECONDARY + "; font-size: 11px; border: none;")
                gfl.addWidget(gl_lbl)

        self._layout.insertWidget(self._layout.count(), guild_frame)
        self._widgets.append(guild_frame)
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
    print("Patching Examen/conservation_tab.py -- structured tracks")
    print("=" * 70)

    if "PRIORITY_GROUP" in raw:
        print("  = already patched -- nothing to do")
        return 0

    # --- 1. CATEGORIES block ---------------------------------------------
    c_start = find_line(lines, "# Status categories in display order")
    if c_start < 0:
        c_start = find_line(lines, "CATEGORIES = [")
    c_end = find_line(lines, "class ConservationTab", c_start if c_start >= 0 else 0)
    if c_start < 0 or c_end < 0:
        print("  x could not locate the CATEGORIES block")
        return 1
    print(f"  + CATEGORIES        lines {c_start + 1}-{c_end}")

    # --- 2. set_result through end of file --------------------------------
    s_start = find_line(lines, "    def set_result(self, result, detail=None):")
    if s_start < 0:
        print("  x could not locate set_result")
        return 1
    print(f"  + set_result .. EOF lines {s_start + 1}-{len(lines)}")

    new_lines = (
        lines[:c_start]
        + NEW_CATEGORIES.split("\n")
        + lines[c_end:s_start]
        + NEW_SET_RESULT.split("\n")
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
        print(f"    restore: copy {os.path.basename(BACKUP)} conservation_tab.py")
        return 1

    print("")
    print("  NEXT: python -m Examen -> Glory Park -> Conservation")
    print("  Expect 'Priority listings' naming each jurisdiction separately")
    print("  instead of a single 'Section 41' row, plus a Legal protection")
    print("  group if any key species are protected.")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
