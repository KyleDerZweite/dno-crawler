"""
Crawl Job Steps

Pipeline:
    step_00: Gather Context    - Load DNO info, check cache
    step_01: Discover          - BFS crawl + pattern learning (NEW - replaces strategize + search)
    step_02: Download          - Download file to local storage
    step_03: Extract           - AI extraction (configurable provider)
    step_04: Validate          - Check data quality
    step_05: Finalize          - Save data, update learning profile
"""

from app.jobs.steps.step_00_gather_context import GatherContextStep
from app.jobs.steps.step_01_discover import DiscoverStep
from app.jobs.steps.step_02_download import DownloadStep
from app.jobs.steps.step_03_extract import ExtractStep
from app.jobs.steps.step_04_validate import ValidateStep
from app.jobs.steps.step_05_finalize import FinalizeStep

# Ordered list of steps for crawl jobs
CRAWL_JOB_STEPS = [
    GatherContextStep(),
    DiscoverStep(),
    DownloadStep(),
    ExtractStep(),
    ValidateStep(),
    FinalizeStep(),
]

__all__ = [
    "CRAWL_JOB_STEPS",
    "DiscoverStep",
    "DownloadStep",
    "ExtractStep",
    "FinalizeStep",
    "GatherContextStep",
    "ValidateStep",
]

