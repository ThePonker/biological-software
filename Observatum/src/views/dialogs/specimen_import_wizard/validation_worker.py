from src.utils.constants import compute_taxonomic_sort_key
import paths
from shared.species_lookup import lookup_names
from shared.species_lookup_entries import entries
"""
Validation Worker for Specimen Import Wizard.

PANDAS REFACTOR: Uses vectorized operations for fast validation.
"""

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, List

import pandas as pd
from PySide6.QtCore import QThread, Signal


def _find_vc_database() -> Optional[str]:
    """Find the Vice County lookup database."""
    candidates = []
    try:
        from PySide6.QtCore import QSettings
        settings = QSettings()
        custom_path = settings.value("database/vc_lookup_path")
        if custom_path:
            candidates.append(Path(custom_path))
    except Exception:
        pass
    try:
        this_file = Path(__file__).resolve()
        candidates.append(this_file.parent.parent.parent.parent / "data" / "vc_lookup.db")
        candidates.append(this_file.parent.parent.parent / "data" / "vc_lookup.db")
    except Exception:
        pass
    cwd = Path(os.getcwd())
    candidates.append(cwd / "data" / "vc_lookup.db")
    candidates.append(cwd / "src" / "data" / "vc_lookup.db")
    if sys.path:
        candidates.append(Path(sys.path[0]) / "data" / "vc_lookup.db")
    candidates.append(Path("data") / "vc_lookup.db")
    try:
        home = Path.home()
        candidates.append(paths.VC_LOOKUP_DB)
    except Exception:
        pass
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        candidates.append(exe_dir / "data" / "vc_lookup.db")
    for path in candidates:
        try:
            if path.exists():
                return str(path)
        except Exception:
            pass
    return None


from ..row_status import RowStatus  # noqa: F401  (I9: one copy; re-exported for the mixins)


@dataclass
class ImportRow:
    row_number: int
    raw_data: Dict[str, str]
    status: RowStatus = RowStatus.PENDING
    error_message: str = ""
    warnings: List[str] = field(default_factory=list)
    species_name: str = ""
    species_tvk: str = ""
    common_name: str = ""
    order_name: str = ""
    family: str = ""
    subfamily: str = ""
    date_collected: str = ""
    grid_ref: str = ""
    vc_number: Optional[int] = None
    vc_name: str = ""
    site_name: str = ""
    collector: str = ""
    determiner: str = ""
    specimen_code: str = ""
    preparation_type: str = ""
    storage_location: str = ""
    drawer_number: str = ""
    condition: str = ""
    label_data: str = ""
    notes: str = ""
    import_notes: str = ""
    superfamily: str = ""
    taxonomic_sort_key: Optional[int] = None
    taxon_group: str = ""
    sex: str = ""                                   # IMP-7: could not be mapped
    is_duplicate: bool = False                      # IMP-7: already in the collection
    existing_record_id: Optional[int] = None


def normalise_sex(value: str):
    """(stored value, warning): 'M' / 'male' / '1m' -> 'Male', 'F' -> 'Female', 'u' / 'unknown'
    -> 'Unknown' (the values the collection holds); anything else is kept as written, with a
    warning. Read with shared.sex_summary.classify_sex, as the collection counts them."""
    from shared.sex_summary import classify_sex
    text = (value or "").strip()
    if not text:
        return "", ""
    kind = classify_sex(text)
    if kind == "m":
        return "Male", ""
    if kind == "f":
        return "Female", ""
    if text.lower() in ("u", "unknown", "unsexed", "?"):
        return "Unknown", ""
    return text, f"Non-standard sex: {text}"


class ValidationWorker(QThread):
    progress = Signal(int, int)
    row_validated = Signal(int, object)
    finished = Signal(list)

    def __init__(self, rows: List[ImportRow], column_mapping: Dict[str, str],
                 uksi_model, vc_db_path: str = None, main_db_path: str = None, db_manager=None):
        super().__init__()
        self.rows = rows
        self.column_mapping = column_mapping
        self.uksi_model = uksi_model
        self.vc_db_path = vc_db_path
        self.db_manager = db_manager            # for the duplicate check (IMP-7)
        self._cancelled = False
        self._vc_service = None

    def cancel(self):
        self._cancelled = True

    def run(self):
        db_path = self.vc_db_path or _find_vc_database()
        if db_path:
            try:
                from src.services.vc_lookup_service import VCLookupService
                self._vc_service = VCLookupService(db_path)
            except ImportError:
                try:
                    from services.vc_lookup_service import VCLookupService
                    self._vc_service = VCLookupService(db_path)
                except ImportError:
                    self._vc_service = None

        total = len(self.rows)
        self.progress.emit(0, total)

        # Step 1: Build DataFrame
        self.progress.emit(int(total * 0.05), total)
        df = self._build_dataframe()
        if self._cancelled:
            return

        # Step 2: Batch species lookup
        self.progress.emit(int(total * 0.10), total)
        df = self._batch_species_lookup(df)
        if self._cancelled:
            return

        # Step 3: Batch VC lookup
        self.progress.emit(int(total * 0.50), total)
        df = self._batch_vc_lookup(df)
        if self._cancelled:
            return

        # Step 4: Validate dates
        self.progress.emit(int(total * 0.80), total)
        df = self._validate_dates(df)
        if self._cancelled:
            return

        # Step 4b: specimens already in the collection (IMP-7, 10 Oct 2026)
        df = self._duplicate_check(df)

        # Step 5: Build ImportRow objects
        self.progress.emit(int(total * 0.90), total)
        validated_rows = self._build_import_rows(df)

        # Step 6: Skip per-row signals - table will be populated in main thread
        # This avoids cross-thread signal congestion
        
        if self._vc_service:
            self._vc_service.close()

        # Emit 90% - main thread will update to 100% during table population
        self.progress.emit(int(total * 0.90), total)
        self.finished.emit(validated_rows)

    def _build_dataframe(self) -> pd.DataFrame:
        df = self._build_dataframe_rows()
        if df.empty:
            return df
        sexes = [normalise_sex(v) for v in df["sex"]]
        df["sex_value"] = [v for v, _ in sexes]
        df["sex_warning"] = [w for _, w in sexes]
        return df

    def _build_dataframe_rows(self) -> pd.DataFrame:
        mapping = self.column_mapping
        data = []
        for i, row in enumerate(self.rows):
            raw = row.raw_data
            data.append({
                "row_idx": i,
                "row_number": row.row_number,
                "species_name": raw.get(mapping.get("species_name", ""), "").strip(),
                "date_collected": raw.get(mapping.get("date_collected", ""), "").strip(),
                "grid_ref": raw.get(mapping.get("grid_ref", ""), "").strip().upper().replace(" ", ""),
                "site_name": raw.get(mapping.get("site_name", ""), "").strip(),
                "collector": raw.get(mapping.get("collector", ""), "").strip(),
                "determiner": raw.get(mapping.get("determiner", ""), "").strip(),
                "specimen_code": raw.get(mapping.get("specimen_code", ""), "").strip(),
                "preparation_type": raw.get(mapping.get("preparation_type", ""), "").strip(),
                "storage_location": raw.get(mapping.get("storage_location", ""), "").strip(),
                "drawer_number": raw.get(mapping.get("drawer_number", ""), "").strip(),
                "condition": raw.get(mapping.get("condition", ""), "").strip(),
                "label_data": raw.get(mapping.get("label_data", ""), "").strip(),
                "notes": raw.get(mapping.get("notes", ""), "").strip(),
                "sex": raw.get(mapping.get("sex", ""), "").strip(),
            })
        return pd.DataFrame(data)

    def _batch_species_lookup(self, df: pd.DataFrame) -> pd.DataFrame:
        df["species_tvk"] = ""
        df["taxonomic_sort_key"] = None
        df["superfamily"] = ""
        df["common_name"] = ""
        df["order_name"] = ""
        df["family"] = ""
        df["subfamily"] = ""
        df["species_error"] = ""
        df["species_warning"] = ""
        df["import_notes"] = ""
        df["matched_name"] = df["species_name"]

        if not self.uksi_model:
            df.loc[df["species_name"] != "", "species_warning"] = "UKSI lookup not available"
            return df

        unique_species = df[df["species_name"] != ""]["species_name"].unique().tolist()
        if not unique_species:
            return df

        # One rule set for all three wizards (shared/species_lookup.py): exact names and
        # synonyms; anything else is an error naming the closest UKSI names, to be confirmed
        # with Resolve Species. Saved aliases are no longer used.
        species_lookup = entries(lookup_names(unique_species, self.uksi_model,
                                              cancelled=lambda: self._cancelled))

        # Apply to DataFrame
        for idx, row in df.iterrows():
            name = row["species_name"]
            if name and name in species_lookup:
                lookup = species_lookup[name]
                df.at[idx, "species_tvk"] = lookup.get("tvk", "")
                df.at[idx, "species_error"] = lookup.get("error", "")
                df.at[idx, "common_name"] = lookup.get("common_name", "")
                df.at[idx, "order_name"] = lookup.get("order_name", "")
                df.at[idx, "family"] = lookup.get("family", "")
                df.at[idx, "matched_name"] = lookup.get("species_name", name)   # UKSI's (IMP-15)
                # Compute taxonomic sort key and superfamily
                tvk = lookup.get("tvk", "")
                if tvk:
                    try:
                        sc_result = self.uksi_model.db.execute_uksi(
                            'SELECT sort_code, "order", superfamily FROM taxa WHERE tvk = ?', (tvk,)
                        )
                        sc = sc_result[0] if sc_result else None
                        if sc:
                            df.at[idx, "taxonomic_sort_key"] = compute_taxonomic_sort_key(sc[1] or '', sc[0] or 0)
                            df.at[idx, "superfamily"] = sc[2] or ''
                            # Subfamily via parent chain (genus->subfamily or genus->tribe->subfamily)
                            try:
                                sf_result = self.uksi_model.db.execute_uksi(
                                    'SELECT sf.scientific_name FROM taxa sp '
                                    'JOIN taxa g ON sp.parent_tvk = g.tvk '
                                    'JOIN taxa sf ON g.parent_tvk = sf.tvk AND sf.rank = "Subfamily" '
                                    'WHERE sp.tvk = ? '
                                    'UNION '
                                    'SELECT sf.scientific_name FROM taxa sp '
                                    'JOIN taxa g ON sp.parent_tvk = g.tvk '
                                    'JOIN taxa t ON g.parent_tvk = t.tvk '
                                    'JOIN taxa sf ON t.parent_tvk = sf.tvk AND sf.rank = "Subfamily" '
                                    'WHERE sp.tvk = ? '
                                    'LIMIT 1', (tvk, tvk)
                                )
                                df.at[idx, "subfamily"] = sf_result[0][0] if sf_result else ''
                            except Exception:
                                df.at[idx, "subfamily"] = ''
                            # Taxon group: shared/taxon_groups.py (10 Oct 2026). The inline map
                            # here disagreed with the observation wizard's (Neuroptera,
                            # Trichoptera, 'insect' for snakeflies) and made butterflies moths.
                            from shared.taxon_groups import taxon_group
                            df.at[idx, "taxon_group"] = taxon_group(
                                sc[1] or '', lookup.get("family"), lookup.get("class_name"),
                                lookup.get("kingdom"), lookup.get("phylum")) or ''
                    except Exception as e:
                        print(f"[specimen import] taxonomy lookup failed for {tvk}: {e}")
                warning = lookup.get("warning", "")
                sk = df.at[idx, "taxonomic_sort_key"]
                if tvk and (sk is None or pd.isna(sk) or not sk):
                    # I7 (9 Oct 2026): without a sort key the specimen is invisible in the
                    # collection sidebar -- say so instead of importing it silently
                    warning = "; ".join(w for w in (warning, "No taxonomic sort key -- it would "
                                        "not show in the collection sidebar") if w)
                df.at[idx, "species_warning"] = warning
                df.at[idx, "species_error"] = lookup.get("error", "")
                df.at[idx, "import_notes"] = lookup.get("import_notes", "")
            elif not name:
                df.at[idx, "species_error"] = "Species name is required"

        return df

    def _batch_vc_lookup(self, df: pd.DataFrame) -> pd.DataFrame:
        df["vc_number"] = None
        df["vc_name"] = ""
        df["grid_error"] = ""
        df["grid_warning"] = ""

        if not self._vc_service:
            df.loc[df["grid_ref"] != "", "grid_warning"] = "VC lookup not available"
            return df

        unique_grids = df[df["grid_ref"] != ""]["grid_ref"].unique().tolist()
        if not unique_grids:
            return df

        # 2 km tetrads (SP46Q) included (IMP-13, 10 Oct 2026)
        from shared.import_core import vc_for_grid_refs
        vc_lookup = vc_for_grid_refs(self._vc_service, unique_grids)

        for idx, row in df.iterrows():
            grid = row["grid_ref"]
            if grid and grid in vc_lookup:
                lookup = vc_lookup[grid]
                df.at[idx, "vc_number"] = lookup.get("vc_number")
                df.at[idx, "vc_name"] = lookup.get("vc_name", "")
                df.at[idx, "grid_warning"] = lookup.get("warning", "")
                df.at[idx, "grid_error"] = lookup.get("error", "")
            elif not grid:
                df.at[idx, "grid_warning"] = "No grid reference provided"

        return df

    def _validate_dates(self, df: pd.DataFrame) -> pd.DataFrame:
        df["date_error"] = ""
        df["date_warning"] = ""
        df["parsed_date"] = ""

        for idx, row in df.iterrows():
            date_str = row["date_collected"]
            if not date_str:
                df.at[idx, "date_warning"] = "No date provided"
                continue
            parsed, error = parse_specimen_date(date_str)
            df.at[idx, "parsed_date"] = parsed
            df.at[idx, "date_error"] = error

        return df

    def _parse_date(self, date_str: str) -> Optional[str]:
        """ISO date for an exact date, else None (kept for old callers)."""
        return parse_specimen_date(date_str)[0] or None

    def _duplicate_check(self, df: pd.DataFrame) -> pd.DataFrame:
        """Mark specimens already in the collection (IMP-7, 10 Oct 2026; there was no check).

        The same specimen code, or the same species (TVK), date, grid reference and sex.
        Several specimens of one species from one day are normal (a series), so the check
        COUNTS: with two such held and three in the file, two are duplicates and one is new.
        A lookup that fails marks every row, so nothing imports as new by mistake."""
        df["is_duplicate"] = False
        df["existing_record_id"] = None
        df["dup_error"] = ""
        if self.db_manager is None or df.empty:
            return df
        try:
            held = self.db_manager.execute_main(
                "SELECT id, specimen_code, species_tvk, species_name, date_collected, grid_ref, sex "
                "FROM specimens") or []
        except Exception as e:
            print(f"[specimen import] duplicate check FAILED: {e}")
            df["dup_error"] = f"Duplicate check failed ({e}) -- not imported, to be safe"
            return df

        def g(r, i, k):
            return r[i] if isinstance(r, (list, tuple)) else r[k]

        by_code, by_key, used = {}, {}, set()
        for r in held:
            rid, code = g(r, 0, "id"), (g(r, 1, "specimen_code") or "").strip()
            if code:
                by_code[code.casefold()] = rid
            rest = (g(r, 4, "date_collected"), g(r, 5, "grid_ref"), g(r, 6, "sex"))
            # by TVK, and by name: a specimen held on the s.l. TVK is the same specimen
            tvk, name = (g(r, 2, "species_tvk") or "").strip(), (g(r, 3, "species_name") or "").strip()
            for key in ([_specimen_key(tvk, "", *rest)] if tvk else []) + \
                    ([_specimen_key("", name, *rest)] if name else []):
                by_key.setdefault(key, []).append(rid)
        for idx, row in df.iterrows():
            code = (row.get("specimen_code") or "").strip()
            if code and code.casefold() in by_code:
                df.at[idx, "is_duplicate"] = True
                df.at[idx, "existing_record_id"] = by_code[code.casefold()]
                continue
            if code:
                continue                       # a new code: a new specimen
            rest = (row.get("parsed_date"), row.get("grid_ref"), row.get("sex_value"))
            keys = [_specimen_key(row.get("species_tvk"), "", *rest)] if row.get("species_tvk") else []
            keys += [_specimen_key("", n, *rest) for n in (row.get("matched_name"), row.get("species_name")) if n]
            rid = next((i for k in keys for i in by_key.get(k, ()) if i not in used), None)
            if rid is not None:                # one held specimen per file row, in turn
                used.add(rid)
                df.at[idx, "is_duplicate"] = True
                df.at[idx, "existing_record_id"] = rid
        return df

    def _build_import_rows(self, df: pd.DataFrame) -> List[ImportRow]:
        validated_rows = []
        for idx, row in df.iterrows():
            import_row = self.rows[row["row_idx"]]
            import_row.species_name = row["matched_name"] if row["matched_name"] else row["species_name"]
            import_row.species_tvk = row["species_tvk"] or ""
            import_row.common_name = row["common_name"] or ""
            import_row.order_name = row["order_name"] or ""
            import_row.family = row["family"] or ""
            import_row.taxonomic_sort_key = int(row["taxonomic_sort_key"]) if pd.notna(row.get("taxonomic_sort_key")) else None
            import_row.superfamily = row.get("superfamily", "") or ""
            import_row.taxon_group = row.get("taxon_group", "") or ""
            import_row.subfamily = row.get("subfamily", "") or ""
            import_row.date_collected = row["parsed_date"] if row["parsed_date"] else ""
            import_row.grid_ref = row["grid_ref"]
            import_row.vc_number = int(row["vc_number"]) if pd.notna(row["vc_number"]) else None
            import_row.vc_name = row["vc_name"] or ""
            import_row.site_name = row["site_name"]
            import_row.collector = row["collector"]
            import_row.determiner = row["determiner"]
            import_row.specimen_code = row.get("specimen_code", "") or ""
            import_row.preparation_type = row.get("preparation_type", "") or ""
            import_row.storage_location = row.get("storage_location", "") or ""
            import_row.drawer_number = row.get("drawer_number", "") or ""
            import_row.condition = row.get("condition", "") or ""
            import_row.label_data = row.get("label_data", "") or ""
            import_row.notes = row.get("notes", "") or ""
            import_row.sex = row.get("sex_value", "") or ""
            import_row.is_duplicate = bool(row.get("is_duplicate", False))
            rid = row.get("existing_record_id")
            import_row.existing_record_id = int(rid) if rid is not None and pd.notna(rid) else None
            notes = row["import_notes"] or ""
            if not notes:
                warning = row.get("species_warning", "") or row.get("warning", "")
                if warning:
                    notes = warning
            import_row.import_notes = notes

            errors = []
            warnings = []
            if row["species_error"]:
                errors.append(row["species_error"])
            if row["species_warning"]:
                warnings.append(row["species_warning"])
            if row["grid_error"]:
                errors.append(row["grid_error"])
            if row["grid_warning"]:
                warnings.append(row["grid_warning"])
            if row["date_error"]:
                errors.append(row["date_error"])
            if row["date_warning"]:
                warnings.append(row["date_warning"])
            if row.get("sex_warning"):
                warnings.append(row["sex_warning"])
            if row.get("dup_error"):
                errors.append(row["dup_error"])
            if import_row.is_duplicate:
                warnings.append(f"Already in the collection (specimen {import_row.existing_record_id})")

            import_row.warnings = warnings
            if errors:
                import_row.status = RowStatus.ERROR
                import_row.error_message = "; ".join(errors)
            elif warnings:
                import_row.status = RowStatus.WARNING
                import_row.error_message = "; ".join(warnings)
            else:
                import_row.status = RowStatus.VALID
                import_row.error_message = ""

            validated_rows.append(import_row)

        return validated_rows


def parse_specimen_date(text: str):
    """(ISO date, error) for a specimen's date (10 Oct 2026). One reader for the three wizards
    (shared.import_core): '6.vi.2021' is read (IMP-13); a date still to come is an error.
    A specimen holds one exact date -- the table has no date type -- so a year, a month or a
    range is an error rather than a made-up day."""
    from shared.import_core import parse_record_date
    p = parse_record_date(text)
    if p.error:
        return "", p.error.replace("Unreadable date", "Invalid date")
    if p.date and not p.exact:
        kind = {"O": "a month", "Y": "a year"}.get(p.date_type, "a date range")
        return "", f"Invalid date: '{text}' is {kind}, not a day -- a specimen needs the day"
    return p.date, ""


def _specimen_key(tvk, name, date, grid, sex):
    """What makes two specimens the same for the duplicate check."""
    who = (tvk or "").strip() or "name:" + " ".join(str(name or "").split()).casefold()
    return (who, str(date or "")[:10], str(grid or "").upper().replace(" ", ""),
            str(sex or "").strip().casefold())
