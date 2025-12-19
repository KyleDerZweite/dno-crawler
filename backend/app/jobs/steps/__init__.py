"""
Crawl Job Steps

Pipeline:
    step_00: Gather Context  - Load DNO info, check cache
    step_01: Strategize      - Decide: cache / pattern / search
    step_02: Search          - DuckDuckGo queries (if needed)
    step_03: Download        - Download file to local storage
    step_04: Extract         - AI extraction (configurable provider)
    step_05: Validate        - Check data quality
    step_06: Finalize        - Save data, update learning profile
"""

from app.jobs.steps.step_00_gather_context import GatherContextStep
from app.jobs.steps.step_01_strategize import StrategizeStep
from app.jobs.steps.step_02_search import SearchStep
from app.jobs.steps.step_03_download import DownloadStep
from app.jobs.steps.step_04_extract import ExtractStep
from app.jobs.steps.step_05_validate import ValidateStep
from app.jobs.steps.step_06_finalize import FinalizeStep

# Ordered list of steps for crawl jobs
CRAWL_JOB_STEPS = [
    GatherContextStep(),
    StrategizeStep(),
    SearchStep(),
    DownloadStep(),
    ExtractStep(),
    ValidateStep(),
    FinalizeStep(),
]

__all__ = [
    "GatherContextStep",
    "StrategizeStep",
    "SearchStep",
    "DownloadStep",
    "ExtractStep",
    "ValidateStep",
    "FinalizeStep",
    "CRAWL_JOB_STEPS",
]
