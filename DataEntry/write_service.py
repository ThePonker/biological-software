"""Field guard and fixed values for Data Entry's write to Observatum (commit_service).

The first hot-loop write path (build_observation_kwargs / write_record, used only by the
retired EntryPage) was a second, drifted copy of commit_service's write -- it turned an
unreadable No. into 1 and wrote no comment or taxonomy. Retired 10 Oct 2026 (review DE10)
to _archive/dataentry_hot_loop_20261010/ with entry_page.py; commit_service is the one path.
"""
from __future__ import annotations

CERTAINTY = "Certain"  # fixed per design (26 §3.1)

# Observation dataclass fields this tool sets. Kept as a guard so a typo can't silently
# create an attribute the model ignores.
_ALLOWED_FIELDS = {
    "species_name", "species_tvk", "common_name", "order_name", "family", "taxon_rank",
    "recorder_certainty", "date", "date_type", "grid_ref", "vice_county", "vc_number",
    "site_name", "recorder", "determiner", "sex", "stage", "quantity", "method",
    "record_type", "project_name", "client", "embargo_until",
    "comment",   # the grid's Comment column -- was dropped at commit until 8 Oct 2026
    "latitude", "longitude", "geodetic_datum",   # from the grid ref at commit (9 Oct 2026)
    "kingdom", "taxon_group",                    # from UKSI at commit (9 Oct 2026, OBS-11)
}
