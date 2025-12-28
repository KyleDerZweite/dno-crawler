import os
import sys
from pathlib import Path

# Add backend to path (resolve relative to this script)
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(backend_path)

from app.services.extraction.ai_extractor import AIExtractor
from app.core.config import settings

# Mock settings just in case
# ai_enabled is a property derived from these
settings.ai_api_key = "dummy" 
settings.ai_api_url = "https://dummy.com"
settings.ai_model = "dummy"

def test_pdf_optimization():
    # Check if fitz is installed
    try:
        import fitz
    except ImportError:
        print("Error: 'pymupdf' (fitz) is not installed. Run 'pip install pymupdf' to run this test locally.")
        return

    extractor = AIExtractor()
    
    # Path locally
    base_dir = Path(os.path.abspath(os.path.join(backend_path, "../data/downloads/netze-bw-gmbh")))
    files = [
        ("netze-bw-gmbh-hlzf-2024.pdf", "context: HLZF Hochlastzeitfenster"),
        ("netze-bw-gmbh-netzentgelte-2024.pdf", "context: Netzentgelte Strom Netzwerk"),
    ]
    
    print(f"Testing PDF optimization on {base_dir}...\n")
    
    for filename, prompt in files:
        file_path = base_dir / filename
        if not file_path.exists():
            print(f"Skipping {filename} (not found)")
            continue
            
        print(f"--- Processing {filename} ---")
        print(f"Original size: {file_path.stat().st_size / 1024:.2f} KB")
        
        # Run optimization
        subset_bytes, was_optimized = extractor._preprocess_pdf(file_path, prompt)
        print(f"Was optimized: {was_optimized}")
        
        # Analyze results
        try:
            doc_orig = fitz.open(file_path)
            doc_subset = fitz.open("pdf", subset_bytes)
            print(f"Original pages: {doc_orig.page_count}")
            print(f"Subset pages:  {doc_subset.page_count}")
            doc_orig.close()
            doc_subset.close()
        except Exception as e:
            print(f"Could not analyze page counts: {e}")

        # Save for inspection
        output_filename = f"subset_{filename}"
        output_path = base_dir / output_filename
        with open(output_path, "wb") as f:
            f.write(subset_bytes)
            
        print(f"Subset size:   {len(subset_bytes) / 1024:.2f} KB")
        print(f"Saved to:      {output_path}")
        print("-" * 40 + "\n")

if __name__ == "__main__":
    test_pdf_optimization()
