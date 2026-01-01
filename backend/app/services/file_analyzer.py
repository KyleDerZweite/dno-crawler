"""
File Analyzer - Detects data type and year from filename.

Uses weighted keyword scoring to determine file category.
Filename-first approach avoids "content contamination" issues
where a Netzentgelte PDF might mention HLZF in the fine print.
"""

import re
from pathlib import Path

import structlog

logger = structlog.get_logger()


class FileAnalyzer:
    """Analyze filenames to detect data type and year."""
    
    # Weighted mapping: higher score = more specific to that category
    FILENAME_MAPPING = {
        "netzentgelte": {
            "preisblatt": 5,
            "preisblaetter": 5,
            "netzentgelt": 5,
            "netznutzung": 3,
            "entgelt": 3,
            "strom": 1,  # Low weight, just a modifier
        },
        "hlzf": {
            "zeitfenster": 5,
            "hlzf": 5,
            "atypisch": 5,
            "hochlast": 5,
            "benutzungsstunden": 3,
        }
    }
    
    # Minimum score threshold to be confident in detection
    MIN_SCORE_THRESHOLD = 5
    
    def analyze(self, file_path: Path | str) -> tuple[str | None, int | None]:
        """
        Analyze file to detect data type and year.
        
        Uses filename-first approach with weighted keyword scoring.
        
        Args:
            file_path: Path to file or filename string
        
        Returns:
            (data_type, year) - either or both may be None if not detected
        """
        if isinstance(file_path, str):
            filename = file_path
        else:
            filename = file_path.name
        
        return self._analyze_filename(filename)
    
    def _analyze_filename(self, filename: str) -> tuple[str | None, int | None]:
        """Analyze filename using weighted keyword matching."""
        fn = filename.lower()
        scores = {"netzentgelte": 0, "hlzf": 0}
        
        # Tokenize filename (handles -, _, ., and spaces)
        tokens = re.split(r'[-_.\s]', fn)
        
        for category, weights in self.FILENAME_MAPPING.items():
            for word, weight in weights.items():
                if word in tokens:
                    scores[category] += weight
        
        # Determine type based on score threshold
        detected_type = None
        if (scores["netzentgelte"] >= self.MIN_SCORE_THRESHOLD and 
            scores["netzentgelte"] > scores["hlzf"]):
            detected_type = "netzentgelte"
        elif (scores["hlzf"] >= self.MIN_SCORE_THRESHOLD and 
              scores["hlzf"] > scores["netzentgelte"]):
            detected_type = "hlzf"
        
        # Extract year (matches 2014, 2025, etc.)
        # Take the first year found in the filename
        year_match = re.search(r"(20\d{2})", fn)
        detected_year = int(year_match.group(1)) if year_match else None
        
        logger.debug(
            "Filename analysis",
            filename=filename,
            scores=scores,
            detected_type=detected_type,
            detected_year=detected_year,
        )
        
        return detected_type, detected_year


# Singleton instance
file_analyzer = FileAnalyzer()
