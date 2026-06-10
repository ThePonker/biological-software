"""
Observatum V2 - Repository Layer

Clean data access layer abstracting database operations.
Repositories provide a consistent interface for CRUD operations,
search, and statistics without raw SQL in the rest of the app.

Usage:
    from src.repositories import (
        ObservationRepository,
        SpecimenRepository,
        RecordingSchemeRepository,
        UKSIRepository
    )
    
    # Observations
    obs_repo = ObservationRepository()
    stats = obs_repo.get_quick_stats()
    observations = obs_repo.search(species_name="Pterostichus")
    
    # Specimens (Insect Collection)
    spec_repo = SpecimenRepository()
    specimens = spec_repo.search()
    collection_stats = spec_repo.get_quick_stats()
    
    # Recording Scheme (Longhorn Beetles)
    scheme_repo = RecordingSchemeRepository()
    records = scheme_repo.search(subfamily="Lamiinae")
    county_stats = scheme_repo.get_county_stats()
    
    # UKSI (Species Reference - read-only)
    uksi_repo = UKSIRepository()
    results = uksi_repo.search_species("Rutpela")
    species = uksi_repo.get_species_by_tvk("NBNSYS0000024889")
"""

from .observation_repository import ObservationRepository
from .specimen_repository import SpecimenRepository
from .recording_scheme_repository import RecordingSchemeRepository
from .uksi_repository import UKSIRepository

__all__ = [
    'ObservationRepository',
    'SpecimenRepository',
    'RecordingSchemeRepository',
    'UKSIRepository',
]
