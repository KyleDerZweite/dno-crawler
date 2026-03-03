import sys
from pathlib import Path

# Add backend/app to path
sys.path.append(str(Path.cwd() / "backend"))

from app.services.extraction.pdf_extractor import extract_hlzf_from_pdf

pdf_path = "/data/downloads/dortmunder-netz-gmbh/dortmunder-netz-gmbh-hlzf-2025.pdf"
records = extract_hlzf_from_pdf(pdf_path)

print(f"Extracted {len(records)} records")
for r in records:
    print(r)
