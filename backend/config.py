from __future__ import annotations

import os
from pathlib import Path


DOCS_OUTPUT_DIR = Path(os.getenv("DOCS_OUTPUT_DIR", "data/output/docs"))
MODULES_DIR = DOCS_OUTPUT_DIR / "modules"
GRAPH_JSON_PATH = Path(os.getenv("GRAPH_JSON_PATH", "data/output/graph/graph.json"))
README_PATH = DOCS_OUTPUT_DIR / "README.md"
INDEX_PATH = DOCS_OUTPUT_DIR / "INDEX.md"

MAX_PIPELINE_EVENTS = 600
