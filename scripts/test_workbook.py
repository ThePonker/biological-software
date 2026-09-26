import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Examen.examen_data import load_all_projects, load_project_detail
from Examen.workbook_export import export_workbook
from shared.repositories.codex_repository import CodexRepository, AnalysisMode
from shared.repositories.pantheon_repository import PantheonRepository
from shared.services.pantheon_analysis_service import PantheonAnalysisService

projects = load_all_projects(AnalysisMode.CODEX_FULL, by_year=True)
p = next(x for x in projects if "Glory Park" in x.project_name)
print("project:", p.project_name, p.survey_year, p.client)

detail = load_project_detail(p.project_name, p.client, AnalysisMode.CODEX_FULL,
                             survey_year=p.survey_year or None)

tvks  = [s.tvk for s in detail.species_list if s.tvk]
names = {s.tvk: s.name for s in detail.species_list if s.tvk}

service = PantheonAnalysisService(PantheonRepository(), CodexRepository())
result = service.analyse(tvks, names, AnalysisMode.CODEX_FULL)
print("species:", result.total_species, " key:", result.key_species_count,
      " sqi:", getattr(result.overall_sqi, "sqi", "?"))

out = os.path.join(os.path.expanduser("~"), "Desktop", "Examen_workbook_test.xlsx")
print("written:", export_workbook(result, detail, p, out))
