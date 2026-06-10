"""
Statistics and Reports tab components.
"""

from .stats_reports_tab import StatsReportsTab
from .stat_widgets import (
    StatCard,
    HorizontalBarChart,
    MonthlyActivityChart,
    TopFamiliesList,
    YearByYearTable,
    RecentSpeciesList,
)
from .section_toggle import SectionToggle
from .personal_dashboard import PersonalStatsDashboard
from .commercial_dashboard import CommercialStatsDashboard
from .all_stats_dashboard import AllStatsDashboard
from .commercial_reports_dashboard import CommercialReportsDashboard
from .scheme_dashboard import SchemeDashboard
from .collection_dashboard import CollectionStatsDashboard
from .species_dashboard import SpeciesDashboard

__all__ = [
    'StatsReportsTab',
    'StatCard',
    'HorizontalBarChart',
    'MonthlyActivityChart',
    'TopFamiliesList',
    'YearByYearTable',
    'RecentSpeciesList',
    'SectionToggle',
    'PersonalStatsDashboard',
    'CommercialStatsDashboard',
    'AllStatsDashboard',
    'CommercialReportsDashboard',
    'SchemeDashboard',
    'CollectionStatsDashboard',
    'SpeciesDashboard',
]