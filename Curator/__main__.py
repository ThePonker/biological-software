import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import paths  # noqa: F401  (sets up the suite paths)

from .collection_planner import main

main()
