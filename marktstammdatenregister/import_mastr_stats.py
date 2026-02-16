#!/usr/bin/env python3
"""Compatibility wrapper for the canonical backend MaStR import script."""

import runpy
import sys
from pathlib import Path


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    target = repo_root / "backend" / "scripts" / "import_mastr_stats.py"
    if not target.exists():
        raise FileNotFoundError(f"Backend import script not found: {target}")

    sys.argv[0] = str(target)
    runpy.run_path(str(target), run_name="__main__")


if __name__ == "__main__":
    main()
