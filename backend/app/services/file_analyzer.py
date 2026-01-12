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
            "netzentgelte": 5,  # Plural form for exact token matching
            "preise": 5,        # Price sheets are netzentgelte
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
            "regelung": 5,   # Regulatory documents often contain HLZF
            "regelungen": 5, # Plural form
        }
    }

    # Minimum score threshold to be confident in detection
    MIN_SCORE_THRESHOLD = 5

    # Valid year range for 2-digit year detection (20-30 = 2020-2030)
    VALID_YEAR_RANGE = (20, 30)

    def _extract_year_from_6digit_date(self, date_str: str) -> int | None:
        """
        Extract year from a 6-digit date string.

        Tries to parse as YYMMDD, DDMMYY, or MMDDYY format by validating
        that month (01-12) and day (01-31) are in valid ranges.

        Args:
            date_str: 6-digit string like "260101"

        Returns:
            4-digit year (e.g., 2026) or None if no valid format detected
        """
        if len(date_str) != 6 or not date_str.isdigit():
            return None

        p1, p2, p3 = int(date_str[0:2]), int(date_str[2:4]), int(date_str[4:6])

        def is_valid_month(m: int) -> bool:
            return 1 <= m <= 12

        def is_valid_day(d: int) -> bool:
            return 1 <= d <= 31

        def is_valid_year(y: int) -> bool:
            return self.VALID_YEAR_RANGE[0] <= y <= self.VALID_YEAR_RANGE[1]

        # Try YYMMDD first (most common for German documents)
        # e.g., 260101 = 2026-01-01
        if is_valid_year(p1) and is_valid_month(p2) and is_valid_day(p3):
            return 2000 + p1

        # Try DDMMYY (common European format)
        # e.g., 010126 = 01-01-2026
        if is_valid_day(p1) and is_valid_month(p2) and is_valid_year(p3):
            return 2000 + p3

        # Try MMDDYY (US format, less common in Germany)
        # e.g., 010126 = 01-01-2026
        if is_valid_month(p1) and is_valid_day(p2) and is_valid_year(p3):
            return 2000 + p3

        return None

    def analyze(self, file_path: Path | str) -> tuple[str | None, int | None]:
        """
        Analyze file to detect data type and year.

        Uses filename-first approach with weighted keyword scoring.

        Args:
            file_path: Path to file or filename string

        Returns:
            (data_type, year) - either or both may be None if not detected
        """
        filename = file_path if isinstance(file_path, str) else file_path.name

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

        # Extract year - try multiple strategies
        detected_year = None

        # Strategy 1: Look for explicit 4-digit years (2014, 2025, etc.)
        # Take the LAST year found to handle date-prefixed filenames
        # e.g., "20201026_NetzeBW_2021" should detect 2021, not 2020
        year_matches = re.findall(r"(20\d{2})", fn)
        if year_matches:
            detected_year = int(year_matches[-1])

        # Strategy 2: Fallback to 6-digit date patterns (YYMMDD, DDMMYY, MMDDYY)
        # Can appear anywhere in filename: "260101_Preisblatt.pdf" or "Preisblatt_260101.pdf"
        if detected_year is None:
            date_matches = re.findall(r"(\d{6})", fn)
            for date_str in date_matches:
                year = self._extract_year_from_6digit_date(date_str)
                if year is not None:
                    detected_year = year
                    break  # Use first valid match

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
