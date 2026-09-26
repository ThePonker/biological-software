"""patch_jurisdiction_ui.py -- jurisdiction derived from the vice-county.

    python scripts/patch_jurisdiction_ui.py

Touches two files, and they must go together: a control that does not reach the
classification is worse than no control at all.

    shared/services/pantheon_analysis_service.py   accept and pass jurisdiction
    Examen/site_analysis_view.py                   derive it, show it, allow override

The problem
-----------
Key-species classification became jurisdiction-aware on 5 September and defaults
to England. There is no control, so a Scottish or Welsh site would silently be
assessed under English rules -- Scottish Biodiversity List species dropped, S41
species counted -- with nothing on screen to say so.

Why derived rather than a mode
------------------------------
The jurisdiction is a property of the site, not of the session. Glory Park is in
Northamptonshire and will always be assessed under English rules. A toolbar mode
is something you can forget you are in: select an English site with Scotland
still chosen and the answer is wrong with no warning. That is the same shape as
the pooled-years problem fixed this morning.

Vice-county is already on every record and derived from the grid reference, so
the country can be read from the data:

    1-34, 36-40, 53-70   England
    35, 41-52            Wales
    71                   Isle of Man
    72-112               Scotland

The combo therefore defaults to **Auto (vice-county)** and reports what it found.
The explicit settings remain for a cross-border project, or where the records
carry no VC.

Northern Ireland has no Watsonian vice-county in this range and must be chosen
explicitly.

Safe to re-run. Backs up as .bak_juris alongside each file.
"""
import os
import shutil
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVICE = os.path.join(_ROOT, "shared", "services", "pantheon_analysis_service.py")
VIEW = os.path.join(_ROOT, "Examen", "site_analysis_view.py")

# ---------------------------------------------------------------- service
S_OLD_RESULT = """    key_species: list = field(default_factory=list)
    key_species_count: int = 0"""

S_NEW_RESULT = """    # The jurisdiction the key-species filter used. Carried on the result so a
    # report can state it: S41 confers key status in England, the Scottish
    # Biodiversity List does not, and the figure is meaningless without saying
    # which rule produced it.
    jurisdiction: str = "England"

    key_species: list = field(default_factory=list)
    key_species_count: int = 0"""

S_OLD_SIG = """    def analyse(self, tvks, species_names=None,
                mode=AnalysisMode.CODEX_FULL):
        if not tvks:
            return AnalysisResult()

        unique_tvks = list(set(tvks))
        names = species_names or {}
        result = AnalysisResult(total_species=len(unique_tvks), mode=mode.value)"""

S_NEW_SIG = """    def analyse(self, tvks, species_names=None,
                mode=AnalysisMode.CODEX_FULL, jurisdiction="England"):
        \"\"\"Analyse a species list.

        jurisdiction  which country's rules decide key status. Section 41 is
                      England's list, made under English law; a Scottish
                      Ministers' list carries no weight in an English planning
                      determination, and the reverse. Rarity and threat are
                      GB-wide and unaffected.
        \"\"\"
        if not tvks:
            return AnalysisResult(jurisdiction=jurisdiction)

        unique_tvks = list(set(tvks))
        names = species_names or {}
        result = AnalysisResult(total_species=len(unique_tvks), mode=mode.value,
                                jurisdiction=jurisdiction)"""

S_OLD_CALL = """            codex_statuses = self._codex.get_statuses_batch(unique_tvks, mode)"""

S_NEW_CALL = """            try:
                codex_statuses = self._codex.get_statuses_batch(
                    unique_tvks, mode, jurisdiction)
            except TypeError:
                # Older CodexRepository without the jurisdiction parameter.
                codex_statuses = self._codex.get_statuses_batch(unique_tvks, mode)"""

S_OLD_CMP = """    def compare(self, tvks, species_names=None):
        c = self.analyse(tvks, species_names, AnalysisMode.CODEX_FULL)
        p = self.analyse(tvks, species_names, AnalysisMode.PANTHEON_ONLY)"""

S_NEW_CMP = """    def compare(self, tvks, species_names=None, jurisdiction="England"):
        c = self.analyse(tvks, species_names, AnalysisMode.CODEX_FULL, jurisdiction)
        p = self.analyse(tvks, species_names, AnalysisMode.PANTHEON_ONLY, jurisdiction)"""

# ---------------------------------------------------------------- view
V_OLD_SETMODE = """    def set_mode(self, mode):
        self._mode = mode; self._load_projects()"""

V_NEW_SETMODE = '''    def set_mode(self, mode):
        self._mode = mode; self._load_projects()

    # ── Jurisdiction ─────────────────────────────────────────────
    # Watsonian vice-counties. VC is already on every record and derived from
    # the grid reference, so the country can be read from the data rather than
    # chosen from a menu that can be forgotten.
    _VC_COUNTRY = ([("England", range(1, 35))] +
                   [("Wales", [35])] +
                   [("England", range(36, 41))] +
                   [("Wales", range(41, 53))] +
                   [("England", range(53, 71))] +
                   [("Isle of Man", [71])] +
                   [("Scotland", range(72, 113))])

    @classmethod
    def _country_for_vc(cls, vc):
        for country, rng in cls._VC_COUNTRY:
            if vc in rng:
                return country
        return ""

    def _derive_jurisdiction(self, proj):
        """Commonest country across the project's records, or '' if unknown."""
        if proj is None or not paths.OBSERVATUM_DB.exists():
            return ""
        where = "record_type='Commercial' AND project_name=?"
        params = [proj.project_name]
        if getattr(proj, "client", ""):
            where += " AND client=?"
            params.append(proj.client)
        if getattr(proj, "survey_year", ""):
            where += " AND substr(date,1,4)=?"
            params.append(str(proj.survey_year))
        try:
            conn = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
            rows = conn.execute(
                f"""SELECT vc_number, COUNT(1) FROM observations
                    WHERE {where} AND vc_number IS NOT NULL AND vc_number != ''
                    GROUP BY 1 ORDER BY 2 DESC""", params).fetchall()
            conn.close()
        except sqlite3.Error:
            return ""
        tally = {}
        for vc, n in rows:
            try:
                country = self._country_for_vc(int(vc))
            except (TypeError, ValueError):
                continue
            if country:
                tally[country] = tally.get(country, 0) + n
        if not tally:
            return ""
        return max(tally, key=tally.get)

    def _resolve_jurisdiction(self, proj):
        """The jurisdiction to assess under, and how it was arrived at."""
        chosen = self.juris_combo.currentText()
        if chosen != AUTO_JURISDICTION:
            return chosen, "chosen"
        derived = self._derive_jurisdiction(proj)
        if derived in ("", "Isle of Man"):
            # No usable vice-county, or a jurisdiction with no separate
            # priority list. England is the documented default; say so rather
            # than assert a country the records do not support.
            return "England", ("default" if not derived else f"default, VC in {derived}")
        return derived, "from vice-county"

    def _on_jurisdiction_changed(self, _text=None):
        if self._current_result is not None:
            self.detail_header.setText(
                self.detail_header.text().split("   \\u2014 assessed")[0]
                + "   (re-select the project to apply the new jurisdiction)")'''

V_OLD_COMBO = """        self.pool_chk.toggled.connect(self._on_pool_toggled)
        toolbar.addWidget(self.pool_chk)"""

V_NEW_COMBO = """        self.pool_chk.toggled.connect(self._on_pool_toggled)
        toolbar.addWidget(self.pool_chk)

        # Jurisdiction decides which priority listings confer key status. It is
        # a property of the site, so it is derived from the vice-county by
        # default rather than left as a mode that can be forgotten.
        toolbar.addWidget(QLabel("Jurisdiction:"))
        self.juris_combo = QComboBox()
        self.juris_combo.addItems([AUTO_JURISDICTION, "England", "Wales",
                                   "Scotland", "Northern Ireland"])
        self.juris_combo.setToolTip(
            "Which country's rules decide key species.\\n"
            "Auto reads the vice-county from the records.\\n"
            "Rarity and threat are GB-wide and unaffected.")
        self.juris_combo.currentTextChanged.connect(self._on_jurisdiction_changed)
        self.juris_combo.setStyleSheet(
            "QComboBox { padding: 3px 6px; border: 1px solid " + BORDER +
            "; border-radius: 3px; font-size: 11px; }")
        toolbar.addWidget(self.juris_combo)"""

V_OLD_TITLE = """        title = (f"{proj.display_name} \\u2014 {proj.client}{sites_info}"
                 if proj.survey_year else
                 f"{proj.project_name} \\u2014 {proj.client}{sites_info} (all years pooled)")
        self._run_analysis(tvks, names, title, detail.site.visit_count)"""

V_NEW_TITLE = """        title = (f"{proj.display_name} \\u2014 {proj.client}{sites_info}"
                 if proj.survey_year else
                 f"{proj.project_name} \\u2014 {proj.client}{sites_info} (all years pooled)")
        self._jurisdiction, how = self._resolve_jurisdiction(proj)
        title += f"   \\u2014 assessed under {self._jurisdiction} ({how})"
        self._run_analysis(tvks, names, title, detail.site.visit_count)"""

V_OLD_RUN = """    def _run_analysis(self, tvks, names, title, visits=0):
        mode = self._mode if isinstance(self._mode, AnalysisMode) else AnalysisMode.CODEX_FULL
        try:
            result = self._service.analyse(tvks, names, mode); self._current_result = result"""

V_NEW_RUN = """    def _run_analysis(self, tvks, names, title, visits=0):
        mode = self._mode if isinstance(self._mode, AnalysisMode) else AnalysisMode.CODEX_FULL
        juris = getattr(self, "_jurisdiction", "England")
        try:
            try:
                result = self._service.analyse(tvks, names, mode, juris)
            except TypeError:
                result = self._service.analyse(tvks, names, mode)
            self._current_result = result"""

V_OLD_STATE = """        self._current_project = None    # ProjectRecord; None for an imported list"""

V_NEW_STATE = """        self._current_project = None    # ProjectRecord; None for an imported list
        self._jurisdiction = "England"  # resolved per project; see _resolve_jurisdiction"""

V_OLD_IMPORT = """                self._current_detail = None; self._current_project = None
                self._current_site_name = "Imported List\""""

V_NEW_IMPORT = """                self._current_detail = None; self._current_project = None
                self._current_site_name = "Imported List"
                # An imported list has no records, so no vice-county to read.
                self._jurisdiction, how = self._resolve_jurisdiction(None)"""

V_OLD_EXPORT = """            export_workbook(self._current_result, self._current_detail, proj, path,
                            pooled_years=self._pool_years)"""

V_NEW_EXPORT = """            export_workbook(self._current_result, self._current_detail, proj, path,
                            jurisdiction=getattr(self, "_jurisdiction", "England"),
                            pooled_years=self._pool_years)"""


def apply(path, edits, marker, extra_check=None):
    name = os.path.basename(path)
    if not os.path.exists(path):
        print(f"  x NOT FOUND: {path}")
        return False
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    if marker in text:
        print(f"  = {name}: already patched")
        return True
    if extra_check and not extra_check(text):
        return False
    ok = True
    for label, old, new in edits:
        n = text.count(old)
        if n == 1:
            text = text.replace(old, new)
            print(f"  + {name}: {label}")
        else:
            print(f"  x {name}: {label}  ({n} matches, expected 1)")
            ok = False
    if not ok:
        print(f"    -> {name} NOT written")
        return False
    backup = path + ".bak_juris"
    if not os.path.exists(backup):
        shutil.copy2(path, backup)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    return True


def _view_imports(text):
    head = text.split("class ")[0]
    missing = [n for n in ("QComboBox", "QLabel") if n not in head]
    if missing:
        print(f"  x site_analysis_view.py does not import: {', '.join(missing)}")
        print("    add them to the PySide6.QtWidgets import list first")
        return False
    print("  . QComboBox and QLabel already imported")
    return True


def main():
    print("")
    print("Patching -- jurisdiction derived from the vice-county")
    print("=" * 70)

    ok = apply(SERVICE,
               [("jurisdiction on AnalysisResult", S_OLD_RESULT, S_NEW_RESULT),
                ("analyse() takes jurisdiction", S_OLD_SIG, S_NEW_SIG),
                ("pass it to get_statuses_batch", S_OLD_CALL, S_NEW_CALL),
                ("compare() takes jurisdiction", S_OLD_CMP, S_NEW_CMP)],
               "jurisdiction: str")

    ok &= apply(VIEW,
                [("state field", V_OLD_STATE, V_NEW_STATE),
                 ("VC mapping and resolution", V_OLD_SETMODE, V_NEW_SETMODE),
                 ("toolbar control", V_OLD_COMBO, V_NEW_COMBO),
                 ("resolve on project selection", V_OLD_TITLE, V_NEW_TITLE),
                 ("pass to analyse()", V_OLD_RUN, V_NEW_RUN),
                 ("resolve for an imported list", V_OLD_IMPORT, V_NEW_IMPORT),
                 ("pass to the workbook", V_OLD_EXPORT, V_NEW_EXPORT)],
                "_resolve_jurisdiction", _view_imports)

    # AUTO_JURISDICTION constant, once, near the top of the view
    if ok:
        with open(VIEW, "r", encoding="utf-8") as f:
            t = f.read()
        if "AUTO_JURISDICTION" in t and "AUTO_JURISDICTION =" not in t:
            t = t.replace("\nclass SiteAnalysisView(QWidget):",
                          '\nAUTO_JURISDICTION = "Auto (vice-county)"\n\n\n'
                          "class SiteAnalysisView(QWidget):", 1)
            with open(VIEW, "w", encoding="utf-8", newline="") as f:
                f.write(t)
            print("  + site_analysis_view.py: AUTO_JURISDICTION constant")

    print("")
    if not ok:
        print("  One or more files unchanged -- review before running Examen.")
        return 1

    print("  Checking both files compile and the VC mapping is right...")
    try:
        import py_compile
        py_compile.compile(SERVICE, doraise=True)
        py_compile.compile(VIEW, doraise=True)
        sys.path.insert(0, _ROOT)
        import importlib
        m = importlib.import_module("Examen.site_analysis_view")
        importlib.reload(m)
        V = m.SiteAnalysisView
        cases = [(1, "England"), (34, "England"), (35, "Wales"), (40, "England"),
                 (41, "Wales"), (52, "Wales"), (53, "England"), (70, "England"),
                 (71, "Isle of Man"), (72, "Scotland"), (112, "Scotland"),
                 (999, "")]
        bad = 0
        for vc, expect in cases:
            got = V._country_for_vc(vc)
            if got != expect:
                bad += 1
                print(f"    x VC {vc} -> {got!r}, expected {expect!r}")
        if bad:
            print(f"  x {bad} vice-county mapping(s) wrong")
            return 1
        print(f"  + all {len(cases)} vice-county cases correct")
    except Exception as e:  # noqa: BLE001
        print(f"  x FAILED: {type(e).__name__}: {e}")
        print("    restore: copy *.bak_juris back over each file")
        return 1

    print("")
    print("  NEXT: python -m Examen")
    print("  Select Glory Park. The header should end")
    print("    '— assessed under England (from vice-county)'")
    print("  Changing the combo prompts you to re-select; it does not silently")
    print("  leave a stale figure on screen.")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
