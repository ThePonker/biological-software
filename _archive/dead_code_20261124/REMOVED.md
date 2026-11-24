# Dead code removed 24 Nov 2026 (tidy-up after code review)

Exact source of each removed function, as it stood at origin/main b19f1a3, so it can be restored. Class methods keep their original indentation.

## Observatum/src/models/observation.py

### ObservationModel.update (was lines 286-412)

```python
    def update(self, observation: Observation) -> bool:
        """Update an existing observation."""
        if not observation.id:
            raise ValueError("Cannot update observation without ID")

        now = datetime.now().isoformat()

        query = """
            UPDATE observations SET
                irecord_id = ?, record_key = ?, external_key = ?, event_id = ?,
                collection_code = ?, dataset_name = ?, institution_code = ?, source = ?,
                species_name = ?, species_tvk = ?, common_name = ?, order_name = ?, family = ?,
                kingdom = ?, taxon_group = ?, taxon_rank = ?,
                identification_qualifier = ?, identification_remarks = ?, recorder_certainty = ?,
                date = ?, date_type = ?,
                grid_ref = ?, grid_precision = ?, vice_county = ?, vc_number = ?,
                site_name = ?, site_name_local = ?,
                latitude = ?, longitude = ?, geodetic_datum = ?, location_id = ?, location_remarks = ?,
                georeference_verification_status = ?,
                recorder = ?, determiner = ?, verifier = ?, verified_on = ?,
                sex = ?, stage = ?, quantity = ?, individual_count = ?,
                organism_quantity = ?, organism_quantity_type = ?, zero_abundance = ?,
                method = ?, basis_of_record = ?, occurrence_status = ?,
                comment = ?, internal_notes = ?, sample_comment = ?, biotope = ?,
                verification_status = ?, verification_status_2 = ?, automated_checks = ?,
                record_type = ?, project_name = ?, client = ?, embargo_status = ?, embargo_until = ?,
                licence = ?, rights_holder = ?, images = ?, sensitive = ?,
                sensitive_site = ?, sensitive_output_map_ref = ?,
                input_on_date = ?, last_edited_date = ?,
                sync_status = ?, never_upload_to_irecord = ?,
                irecord_key = ?, last_synced = ?, observatum_key = ?,
                updated_at = ?
            WHERE id = ?
        """

        params = (
            # External identity
            observation.irecord_id,
            observation.record_key,
            observation.external_key,
            observation.event_id,
            observation.collection_code,
            observation.dataset_name,
            observation.institution_code,
            observation.source,
            # Species identification
            observation.species_name,
            observation.species_tvk,
            observation.common_name,
            observation.order_name,
            observation.family,
            observation.kingdom,
            observation.taxon_group,
            observation.taxon_rank,
            observation.identification_qualifier,
            observation.identification_remarks,
            observation.recorder_certainty,
            # Date
            observation.date,
            observation.date_type,
            # Location - grid
            observation.grid_ref,
            observation.grid_precision,
            observation.vice_county,
            observation.vc_number,
            observation.site_name,
            observation.site_name_local,
            # Location - coordinates
            observation.latitude,
            observation.longitude,
            observation.geodetic_datum,
            observation.location_id,
            observation.location_remarks,
            observation.georeference_verification_status,
            # People
            observation.recorder,
            observation.determiner,
            observation.verifier,
            observation.verified_on,
            # Occurrence
            observation.sex,
            observation.stage,
            observation.quantity,
            observation.individual_count,
            observation.organism_quantity,
            observation.organism_quantity_type,
            observation.zero_abundance,
            observation.method,
            observation.basis_of_record,
            observation.occurrence_status,
            # Notes
            observation.comment,
            observation.internal_notes,
            observation.sample_comment,
            observation.biotope,
            # Verification
            observation.verification_status,
            observation.verification_status_2,
            observation.automated_checks,
            # Record management
            observation.record_type,
            observation.project_name,
            observation.client,
            observation.embargo_status,
            observation.embargo_until,
            # Metadata
            observation.licence,
            observation.rights_holder,
            observation.images,
            observation.sensitive,
            observation.sensitive_site,
            observation.sensitive_output_map_ref,
            observation.input_on_date,
            observation.last_edited_date,
            # Sync
            observation.sync_status,
            observation.never_upload_to_irecord,
            observation.irecord_key,
            observation.last_synced,
            observation.observatum_key,
            # Timestamps
            now,
            observation.id,
        )

        result = self.db.execute_main_write(query, params)
        return result > 0
```

## Observatum/src/repositories/observation_repository.py

### ObservationRepository.delete_many (was lines 284-299)

```python
    def delete_many(self, observation_ids: List[int]) -> int:
        """
        Delete multiple observations.
        
        Args:
            observation_ids: List of IDs to delete
            
        Returns:
            Number of records deleted
        """
        if not observation_ids:
            return 0
        
        placeholders = ",".join(["?" for _ in observation_ids])
        query = f"DELETE FROM observations WHERE id IN ({placeholders})"
        return self._execute_write(query, tuple(observation_ids))
```

### ObservationRepository.count_species_by_order (was lines 405-435)

```python
    def count_species_by_order(self, record_type: str = None) -> List[Dict[str, Any]]:
        """
        Count species grouped by taxonomic order.
        
        Args:
            record_type: Optional filter for Personal/Commercial
            
        Returns:
            List of {label, value} dicts
        """
        where = "WHERE species_tvk IS NOT NULL AND order_name IS NOT NULL"
        params = []
        
        if record_type:
            where += " AND record_type = ?"
            params.append(record_type)
        
        query = f"""
            SELECT order_name, COUNT(DISTINCT species_tvk) as species_count
            FROM observations
            {where}
            GROUP BY order_name
            ORDER BY species_count DESC
            LIMIT 10
        """
        
        results = self._execute(query, tuple(params) if params else ())
        return [
            {'label': row['order_name'], 'value': row['species_count']}
            for row in results
        ]
```

### ObservationRepository.get_top_families (was lines 437-476)

```python
    def get_top_families(self, limit: int = 5, record_type: str = None) -> List[Dict[str, Any]]:
        """
        Get top families by species count.
        
        Args:
            limit: Number of families
            record_type: Optional filter
            
        Returns:
            List of {family, species, records} dicts
        """
        where = "WHERE species_tvk IS NOT NULL AND family IS NOT NULL"
        params = []
        
        if record_type:
            where += " AND record_type = ?"
            params.append(record_type)
        
        query = f"""
            SELECT 
                family,
                COUNT(DISTINCT species_tvk) as species_count,
                COUNT(*) as record_count
            FROM observations
            {where}
            GROUP BY family
            ORDER BY species_count DESC
            LIMIT ?
        """
        params.append(limit)
        
        results = self._execute(query, tuple(params))
        return [
            {
                'family': row['family'],
                'species': row['species_count'],
                'records': row['record_count']
            }
            for row in results
        ]
```

### ObservationRepository.get_year_by_year_stats (was lines 524-587)

```python
    def get_year_by_year_stats(self, record_type: str = None) -> Dict[int, Dict[str, int]]:
        """
        Get statistics per year.
        
        Args:
            record_type: Optional filter
            
        Returns:
            Dict keyed by year with species, records, newSpecies counts
        """
        where = ""
        params = []
        
        if record_type:
            where = "WHERE record_type = ?"
            params.append(record_type)
        
        # Species and records per year
        query = f"""
            SELECT 
                CAST(strftime('%Y', date) AS INTEGER) as year,
                COUNT(DISTINCT species_tvk) as species_count,
                COUNT(*) as record_count
            FROM observations
            {where}
            GROUP BY year
            ORDER BY year DESC
            LIMIT 10
        """
        
        results = self._execute(query, tuple(params) if params else ())
        
        year_stats = {}
        for row in results:
            year = row['year']
            year_stats[year] = {
                'species': row['species_count'],
                'records': row['record_count'],
                'newSpecies': 0
            }
        
        # Calculate new species per year
        first_seen_query = f"""
            SELECT 
                species_tvk,
                MIN(CAST(strftime('%Y', date) AS INTEGER)) as first_year
            FROM observations
            WHERE species_tvk IS NOT NULL
            {('AND record_type = ?' if record_type else '')}
            GROUP BY species_tvk
        """
        
        first_params = [record_type] if record_type else []
        first_seen = self._execute(first_seen_query, tuple(first_params) if first_params else ())
        
        new_per_year = {}
        for row in first_seen:
            first_year = row['first_year']
            new_per_year[first_year] = new_per_year.get(first_year, 0) + 1
        
        for year in year_stats:
            year_stats[year]['newSpecies'] = new_per_year.get(year, 0)
        
        return year_stats
```

## Observatum/src/repositories/specimen_repository.py

### SpecimenRepository._execute_many (was lines 90-99)

```python
    def _execute_many(self, query: str, params_list: List[tuple]) -> int:
        """Execute a query with multiple parameter sets."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.executemany(query, params_list)
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()
```

### SpecimenRepository.delete_many (was lines 274-292)

```python
    def delete_many(self, specimen_ids: List[int]) -> int:
        """
        Delete multiple specimens.
        
        Args:
            specimen_ids: List of IDs to delete
            
        Returns:
            Number of records deleted
        """
        if not specimen_ids:
            return 0
        
        placeholders = ','.join('?' * len(specimen_ids))
        result = self._execute_write(
            f"DELETE FROM specimens WHERE id IN ({placeholders})",
            tuple(specimen_ids)
        )
        return result
```

### SpecimenRepository.count_by_storage_location (was lines 461-470)

```python
    def count_by_storage_location(self) -> Dict[str, int]:
        """Get specimen counts grouped by storage location."""
        rows = self._execute("""
            SELECT storage_location, COUNT(*) as count
            FROM specimens
            WHERE storage_location IS NOT NULL
            GROUP BY storage_location
            ORDER BY count DESC
        """)
        return {row['storage_location']: row['count'] for row in rows}
```

## Observatum/src/models/database.py

### DatabaseManager.table_exists (was lines 287-303)

```python
    def table_exists(self, table_name: str, database: str = 'main') -> bool:
        """
        Check if a table exists in the specified database.
        
        Args:
            table_name: Name of the table
            database: 'main' or 'uksi'
            
        Returns:
            True if table exists
        """
        query = "SELECT name FROM sqlite_master WHERE type='table' AND name=?"
        if database == 'main':
            results = self.execute_main(query, (table_name,))
        else:
            results = self.execute_uksi(query, (table_name,))
        return len(results) > 0
```

### DatabaseManager.get_table_info (was lines 305-324)

```python
    def get_table_info(self, table_name: str, database: str = 'main') -> List[Dict]:
        """
        Get column information for a table.
        
        Args:
            table_name: Name of the table
            database: 'main' or 'uksi'
            
        Returns:
            List of column info dicts
        """
        query = f"PRAGMA table_info({table_name})"
        if database == 'main':
            with self.main_connection() as conn:
                cursor = conn.execute(query)
                return [dict(row) for row in cursor.fetchall()]
        else:
            with self.uksi_connection() as conn:
                cursor = conn.execute(query)
                return [dict(row) for row in cursor.fetchall()]
```

### DatabaseManager.vacuum_main (was lines 326-329)

```python
    def vacuum_main(self) -> None:
        """Compact the main database (removes unused space)."""
        with self.main_connection() as conn:
            conn.execute("VACUUM")
```

## Observatum/src/services/search_service.py

### SearchService.get_species_details (was lines 297-315)

```python
    def get_species_details(self, tvk: str) -> Optional[Dict]:
        """
        Get full details for a species by TVK.
        
        Args:
            tvk: TaxonVersionKey
            
        Returns:
            Dict with species details or None
        """
        # Use repository if available (preferred)
        if self._uksi_repo:
            return self._get_species_details_via_repository(tvk)
        
        # Fallback to model
        if self.uksi_model:
            return self._get_species_details_via_model(tvk)
        
        return None
```

### SearchService.add_recorded_tvk (was lines 397-403)

```python
    def add_recorded_tvk(self, tvk: str) -> None:
        """
        Add a TVK to the recorded species cache.
        
        Call this after saving a new observation.
        """
        self._recorded_tvks.add(tvk)
```

### SearchService.get_recorded_tvks (was lines 405-409)

```python
    def get_recorded_tvks(self) -> set:
        """Get the set of TVKs the user has recorded."""
        if not self._cache_loaded:
            self.refresh_recorded_species()
        return self._recorded_tvks.copy()
```

### SearchService.get_recorded_count (was lines 411-415)

```python
    def get_recorded_count(self) -> int:
        """Get the count of distinct species recorded."""
        if not self._cache_loaded:
            self.refresh_recorded_species()
        return len(self._recorded_tvks)
```

## Observatum/src/services/export_service.py

### ExportService.get_observation_columns (was lines 76-101)

```python
    @staticmethod
    def get_observation_columns() -> tuple:
        """Get default columns for observation export."""
        columns = [
            'species_name', 'common_name', 'date', 'location', 'grid_ref',
            'vice_county', 'recorder', 'determiner', 'sex', 'stage',
            'quantity', 'method', 'type', 'comment', 'verification_status'
        ]
        headers = {
            'species_name': 'Species',
            'common_name': 'Common Name',
            'date': 'Date',
            'location': 'Location',
            'grid_ref': 'Grid Ref',
            'vice_county': 'Vice County',
            'recorder': 'Recorder',
            'determiner': 'Determiner',
            'sex': 'Sex',
            'stage': 'Stage',
            'quantity': 'Quantity',
            'method': 'Sample Method',
            'type': 'Observation Type',
            'comment': 'Comment',
            'verification_status': 'Verification'
        }
        return columns, headers
```

### ExportService.get_specimen_columns (was lines 103-126)

```python
    @staticmethod
    def get_specimen_columns() -> tuple:
        """Get default columns for specimen export."""
        columns = [
            'specimen_code', 'species_name', 'common_name', 'date_collected',
            'location', 'grid_ref', 'vice_county', 'collector', 'determiner',
            'sex', 'preparation_type', 'storage_location', 'notes'
        ]
        headers = {
            'specimen_code': 'Specimen Code',
            'species_name': 'Species',
            'common_name': 'Common Name',
            'date_collected': 'Date Collected',
            'location': 'Location',
            'grid_ref': 'Grid Ref',
            'vice_county': 'Vice County',
            'collector': 'Collector',
            'determiner': 'Determiner',
            'sex': 'Sex',
            'preparation_type': 'Preparation',
            'storage_location': 'Storage Location',
            'notes': 'Notes'
        }
        return columns, headers
```

## Observatum/src/services/recording_scheme_stats_service.py

### invalidate_recording_scheme_stats (was lines 597-601)

```python
def invalidate_recording_scheme_stats():
    """Invalidate the stats cache."""
    global _service_instance
    if _service_instance is not None:
        _service_instance.invalidate()
```

## Observatum/src/services/specimen_stats_service.py

### invalidate_specimen_stats (was lines 412-416)

```python
def invalidate_specimen_stats():
    """Invalidate the stats cache."""
    global _service_instance
    if _service_instance is not None:
        _service_instance.invalidate()
```

## Observatum/src/services/saved_filters_service.py

### get_saved_filters_service (was lines 142-147)

```python
def get_saved_filters_service() -> SavedFiltersService:
    """Get the saved filters service singleton."""
    global _service
    if _service is None:
        _service = SavedFiltersService()
    return _service
```

## Observatum/src/views/dialogs/observation_import_wizard/validation_worker.py

### _osgb36_to_wgs84 (was lines 193-226)

```python
def _osgb36_to_wgs84(easting, northing):
    """Convert OSGB36 eastings/northings to WGS84 lat/lon."""
    import math
    a, b = 6377563.396, 6356256.909
    F0 = 0.9996012717
    lat0, lon0 = math.radians(49), math.radians(-2)
    N0, E0 = -100000, 400000
    e2 = 1 - (b*b)/(a*a)
    n = (a-b)/(a+b)
    lat, M = lat0, 0
    for _ in range(20):
        lat = (northing - N0 - M)/(a*F0) + lat
        Ma = (1 + n + 1.25*n**2 + 1.25*n**3) * (lat-lat0)
        Mb = (3*n + 3*n**2 + 2.625*n**3) * math.sin(lat-lat0) * math.cos(lat+lat0)
        Mc = (1.875*n**2 + 1.875*n**3) * math.sin(2*(lat-lat0)) * math.cos(2*(lat+lat0))
        Md = (35/24)*n**3 * math.sin(3*(lat-lat0)) * math.cos(3*(lat+lat0))
        M = b * F0 * (Ma - Mb + Mc - Md)
        if abs(northing - N0 - M) < 0.00001:
            break
    cosLat, sinLat = math.cos(lat), math.sin(lat)
    nu = a*F0/math.sqrt(1-e2*sinLat**2)
    rho = a*F0*(1-e2)*(1-e2*sinLat**2)**(-1.5)
    eta2 = nu/rho-1
    tanLat = math.tan(lat)
    VII = tanLat/(2*rho*nu)
    VIII = tanLat/(24*rho*nu**3)*(5+3*tanLat**2+eta2-9*tanLat**2*eta2)
    IX = tanLat/(720*rho*nu**5)*(61+90*tanLat**2+45*tanLat**4)
    X = 1/(cosLat*nu)
    XI = 1/(cosLat*6*nu**3)*(nu/rho+2*tanLat**2)
    XII = 1/(cosLat*120*nu**5)*(5+28*tanLat**2+24*tanLat**4)
    dE = easting - E0
    latitude = math.degrees(lat - VII*dE**2 + VIII*dE**4 - IX*dE**6)
    longitude = math.degrees(lon0 + X*dE - XI*dE**3 + XII*dE**5)
    return round(latitude, 6), round(longitude, 6)
```

## shared/repositories/codex_repository.py

### CodexRepository.sensu_lato_counterpart (was lines 491-493)

```python
    def sensu_lato_counterpart(self, tvk):
        """(counterpart_tvk, 'sensu lato' | 'aggregate') for a species, or None."""
        return uksi_sensu_lato_map(self._uksi_path).get(tvk)
```

### CodexRepository.get_sqs (was lines 543-544)

```python
    def get_sqs(self, tvk, mode=AnalysisMode.CODEX_FULL):
        return self.get_sqs_scores([tvk], mode).get(tvk, 0)
```

### CodexRepository.is_key_species (was lines 546-547)

```python
    def is_key_species(self, tvk, mode=AnalysisMode.CODEX_FULL):
        return self.get_status_summary(tvk, mode).is_key
```

### CodexRepository.get_all_designations (was lines 549-556)

```python
    def get_all_designations(self, tvk):
        c = self._get_conn().cursor()
        c.execute("""SELECT designation_abbreviation, reporting_category,
                            designation, source, date_designated, iucn_version,
                            criteria_description
                     FROM designations WHERE tvk = ?
                     ORDER BY reporting_category""", (tvk,))
        return [dict(row) for row in c.fetchall()]
```

### CodexRepository.get_profile (was lines 558-566)

```python
    def get_profile(self, tvk):
        """Return just the profile paragraph for a species (or None)."""
        c = self._get_conn().cursor()
        c.execute("""SELECT profile_text, source, date_added, date_updated, added_by
                     FROM species_profiles WHERE tvk = ?""", (tvk,))
        r = c.fetchone()
        if not r:
            return None
        return dict(r)
```

### CodexRepository.get_key_species_from_list (was lines 708-710)

```python
    def get_key_species_from_list(self, tvks, mode=AnalysisMode.CODEX_FULL):
        """Invertebrate key species from a list. Non-inverts are never key."""
        return {tvk: s for tvk, s in self.get_statuses_batch(tvks, mode).items() if s.is_key}
```

### CodexRepository.get_key_species_by_tier (was lines 712-720)

```python
    def get_key_species_by_tier(self, tvks, mode=AnalysisMode.CODEX_FULL):
        key = self.get_key_species_from_list(tvks, mode)
        tiers = {"Rare": [], "Scarce": [], "Priority": []}
        for s in key.values():
            if s.tier.value in tiers:
                tiers[s.tier.value].append(s)
        for t in tiers.values():
            t.sort(key=lambda s: (-s.sqs, s.tvk))
        return tiers
```

### CodexRepository.compare_modes (was lines 745-765)

```python
    def compare_modes(self, tvks):
        """Side-by-side Codex vs Pantheon-only comparison."""
        c_sqi = self.compute_sqi(tvks, AnalysisMode.CODEX_FULL)
        p_sqi = self.compute_sqi(tvks, AnalysisMode.PANTHEON_ONLY)
        c_key = self.get_key_species_from_list(tvks, AnalysisMode.CODEX_FULL)
        p_key = self.get_key_species_from_list(tvks, AnalysisMode.PANTHEON_ONLY)
        total = len(set(tvks))
        c_pct = round(len(c_key) / total * 100, 1) if total else 0
        p_pct = round(len(p_key) / total * 100, 1) if total else 0
        codex_only = [s for tvk, s in c_key.items() if tvk not in p_key]
        return {
            "codex": {"sqi": c_sqi["sqi"], "key_count": len(c_key),
                      "key_pct": c_pct, "sqs_species": c_sqi["scoring_species"]},
            "pantheon": {"sqi": p_sqi["sqi"], "key_count": len(p_key),
                         "key_pct": p_pct, "sqs_species": p_sqi["scoring_species"]},
            "delta": {"sqi": c_sqi["sqi"] - p_sqi["sqi"],
                      "key_count": len(c_key) - len(p_key),
                      "key_pct": round(c_pct - p_pct, 1),
                      "sqs_species": c_sqi["scoring_species"] - p_sqi["scoring_species"]},
            "codex_only_key": codex_only,
        }
```

### CodexRepository.get_build_log (was lines 780-786)

```python
    def get_build_log(self, limit=10):
        """Latest build_log entries (most recent first)."""
        c = self._get_conn().cursor()
        c.execute("""SELECT timestamp, jncc_rows, pantheon_sqs, manual_entries,
                            bridge_resolved, profiles_count, notes
                     FROM build_log ORDER BY id DESC LIMIT ?""", (limit,))
        return [dict(r) for r in c.fetchall()]
```

### CodexRepository.get_conservation_for_export (was lines 836-861)

```python
    def get_conservation_for_export(self, tvks, mode=AnalysisMode.CODEX_FULL):
        """Batch lookup for export columns.

        Returns {tvk: {...}} with keys designed for spreadsheet export.
        Each value is a string (joined with '; ' for multi-entry tracks).
        """
        statuses = self.get_statuses_batch(tvks, mode)
        result = {}
        for tvk, s in statuses.items():
            result[tvk] = {
                "red_list":       _entry_value(s.threat_iucn_2001) or _entry_value(s.threat_iucn_legacy),
                "rarity":         _entry_value(s.rarity_modern) or _entry_value(s.rarity_legacy),
                "bocc":           _entry_value(s.bocc),
                "global_red_list": _entry_value(s.threat_global_iucn),
                "red_list_eng":   _entry_value(s.red_list_england),
                "red_list_wal":   _entry_value(s.red_list_wales),
                "priority":       "; ".join(e.value for e in s.priority),
                "legal":          "; ".join(
                    (e.detail or e.value) for e in s.legal_protection
                ),
                "sqs":            s.sqs,
                "status_display": s.display_status,
                "tier":           s.tier.value,
                "is_key":         s.is_key,
            }
        return result
```

### CodexRepository.get_review (was lines 885-902)

```python
    def get_review(self, review_id):
        c = self._get_conn().cursor()
        try:
            try:
                c.execute(f"""SELECT id, review_name, author, taxon_group,
                                status_track, date_published, date_imported,
                                source_file, {_LIVE_SPECIES_COUNT} AS species_count,
                                supersedes_id, notes
                         FROM reviews WHERE id = ?""", (review_id,))
            except sqlite3.OperationalError:      # old codex.db: stored count
                c.execute("""SELECT id, review_name, author, taxon_group,
                                status_track, date_published, date_imported,
                                source_file, species_count, supersedes_id, notes
                         FROM reviews WHERE id = ?""", (review_id,))
            row = c.fetchone()
            return dict(row) if row else None
        except sqlite3.OperationalError:
            return None
```

## shared/services/pantheon_analysis_service.py

### ComparisonResult (was lines 176-184)

```python
@dataclass
class ComparisonResult:
    codex: AnalysisResult = None
    pantheon: AnalysisResult = None
    sqi_delta: int = 0
    key_count_delta: int = 0
    key_pct_delta: float = 0.0
    sqs_species_delta: int = 0
    codex_only_key: list = field(default_factory=list)
```

### PantheonAnalysisService.compare (was lines 436-450)

```python
    def compare(self, tvks, species_names=None, jurisdiction="England"):
        c = self.analyse(tvks, species_names, AnalysisMode.CODEX_FULL, jurisdiction)
        p = self.analyse(tvks, species_names, AnalysisMode.PANTHEON_ONLY, jurisdiction)
        p_tvks = {k.tvk for k in p.key_species}
        codex_only = [k for k in c.key_species if k.tvk not in p_tvks]
        c_sqi = c.overall_sqi.sqi if c.overall_sqi else 0
        p_sqi = p.overall_sqi.sqi if p.overall_sqi else 0
        return ComparisonResult(
            codex=c, pantheon=p,
            sqi_delta=c_sqi - p_sqi,
            key_count_delta=c.key_species_count - p.key_species_count,
            key_pct_delta=round(c.key_species_pct - p.key_species_pct, 1),
            sqs_species_delta=c.species_with_sqs - p.species_with_sqs,
            codex_only_key=codex_only,
        )
```

## Examen/site_analysis_view.py

### SiteAnalysisView._country_for_vc (was lines 88-90)

```python
    @classmethod
    def _country_for_vc(cls, vc):
        return country_for_vc(vc)
```

## Lector/saved.py

### is_text_search (was lines 38-40)

```python
def is_text_search(conn, sid):
    r = conn.execute("SELECT text_search FROM saved_searches WHERE search_id=?", (sid,)).fetchone()
    return bool(r and r[0])
```

## Observatum/src/services/recording_scheme_stats_service.py (computation inside RecordingSchemeStatsService._compute / refresh; never read by any view or test)

```python
            # =============================================
            # SPECIES BY ORDER
            # =============================================
            order_query = f"""
                SELECT 
                    order_name as label, 
                    COUNT(DISTINCT species_tvk) as species,
                    COUNT(*) as records
                FROM recording_scheme
                WHERE order_name IS NOT NULL AND order_name != ''
                AND species_tvk IS NOT NULL
                
                GROUP BY order_name
                ORDER BY species DESC
            """
            result = self._db.execute_main(order_query)
            self._cache['species_by_order'] = [
                {'label': r['label'], 'species': r['species'], 'records': r['records']} 
                for r in result
            ] if result else []

            # =============================================
            # SPECIES BY FAMILY
            # =============================================
            family_query = f"""
                SELECT 
                    family,
                    COUNT(DISTINCT species_tvk) as species,
                    COUNT(*) as records
                FROM recording_scheme
                WHERE family IS NOT NULL AND family != ''
                AND species_tvk IS NOT NULL
                
                GROUP BY family
                ORDER BY species DESC
            """
            result = self._db.execute_main(family_query)
            self._cache['species_by_family'] = [
                {'family': r['family'], 'species': r['species'], 'records': r['records']} 
                for r in result
            ] if result else []
```

## shared/repositories/codex_repository.py (Round 3 alias constants; module level, between _legal_applies and the data classes)

```python
# Key-species classification thresholds
# Aliases of the shared rule (shared/key_species_rule.py, Telfer 2023), kept for importers.
RARE_IUCN_2001   = _ks.RARE_V2
SCARCE_IUCN_2001 = _ks.SCARCE_V2
RARE_LEGACY_RDB   = _ks.RARE_V1
SCARCE_LEGACY_RDB = set()          # RDB3 and RDBK are Rare (Telfer 2023)
SCARCE_LEGACY_RARITY = _ks.SCARCE_V1
```

## Observatum/src/services/saved_filters_service.py (module global that only the removed accessor used; it sat directly before get_saved_filters_service)

```python
_service: Optional[SavedFiltersService] = None


# Singleton accessor
```
