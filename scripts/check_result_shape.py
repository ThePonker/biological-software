import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import dataclasses
from shared.services.pantheon_analysis_service import AnalysisResult, KeySpeciesEntry

for cls in (AnalysisResult, KeySpeciesEntry):
    print("===", cls.__name__)
    for f in dataclasses.fields(cls):
        print(f"   {f.name:28} {f.type}")
