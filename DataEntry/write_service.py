"""Write path for DataEntry.

Reuses Observatum's canonical write (ObservationModel.create -> full INSERT + observatum_key)
and then sets the three Session-26 survey-axis columns (sub_location, trap_number,
visit_number) that create() doesn't yet handle, via a supplementary UPDATE on the new id.

build_observation_kwargs is pure (no Observatum import) so it can be unit-tested. write_record
does the real create() + UPDATE and is exercised in tests against a stand-in model.
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
}


def build_observation_kwargs(header, species: dict, stage: str, sex: str, quantity) -> dict:
    """Map a SessionHeader + one hot-loop row to kwargs for Observatum's Observation.

    `species` is the dict emitted by SpeciesSearch: tvk / scientific_name / common_name /
    family / order / rank. Only concrete-dated records are written (caller guards this).
    """
    try:
        qty = int(quantity)
    except (TypeError, ValueError):
        qty = 1
    if qty < 1:
        qty = 1

    vc_number = None
    if str(getattr(header, "vc_number", "") or "").strip().isdigit():
        vc_number = int(header.vc_number)

    kwargs = {
        "species_name": species.get("scientific_name") or "",
        "species_tvk": species.get("tvk"),
        "common_name": species.get("common_name"),
        "order_name": species.get("order"),
        "family": species.get("family"),
        "taxon_rank": species.get("rank"),
        "recorder_certainty": CERTAINTY,
        "date": header.date,
        "date_type": "D",
        "grid_ref": header.grid_ref or None,
        "vice_county": header.vice_county or None,
        "vc_number": vc_number,
        "site_name": header.site_name or None,
        "recorder": header.recorder or None,
        "determiner": header.determiner or None,
        "sex": sex or None,
        "stage": stage or None,
        "quantity": qty,
        "method": header.method or None,
        "record_type": header.mode or "Personal",
        "project_name": header.project_name or None,
        "client": header.client or None,
        "embargo_until": header.embargo_until or None,
    }
    # Guard: never emit an unknown field name.
    return {k: v for k, v in kwargs.items() if k in _ALLOWED_FIELDS}


def write_record(db, model, header, species: dict, stage: str, sex: str, quantity) -> int:
    """Create the observation via Observatum's model, then set the 3 internal columns.

    Returns the new record id. `db` is the DatabaseManager (already pointed at the dev copy);
    `model` is an ObservationModel bound to it.
    """
    from src.models.observation import Observation  # lazy: only on the real machine

    kwargs = build_observation_kwargs(header, species, stage, sex, quantity)
    obs = Observation(**kwargs)
    new_id = model.create(obs)

    if new_id and (header.sub_location or header.trap_number or header.visit_number):
        db.execute_main_write(
            "UPDATE observations SET sub_location=?, trap_number=?, visit_number=? WHERE id=?",
            (
                header.sub_location or None,
                header.trap_number or None,
                header.visit_number or None,
                new_id,
            ),
        )
    return new_id
