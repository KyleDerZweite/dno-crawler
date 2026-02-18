"""
Crawl Job Steps

Pipeline:
    step_00: Gather Context    - Load DNO info, pre-flight checks, check cache
    step_01: Discover          - Data-type agnostic URL discovery
    step_02: Download          - Bulk download candidates
    step_03: Classify          - Post-download classification via regex extractors
    step_04: Extract           - AI extraction (configurable provider)
    step_05: Validate          - Check data quality
    step_06: Finalize          - Save data, update learning profile
"""

from app.jobs.steps.step_00_gather_context import GatherContextStep
from app.jobs.steps.step_01_discover import DiscoverStep
from app.jobs.steps.step_02_download import DownloadStep
from app.jobs.steps.step_03_classify import ClassifyStep
from app.jobs.steps.step_04_extract import ExtractStep
from app.jobs.steps.step_05_validate import ValidateStep
from app.jobs.steps.step_06_finalize import FinalizeStep

# Ordered list of steps for crawl jobs (steps 0-3)
CRAWL_JOB_STEPS = [
    GatherContextStep(),
    DiscoverStep(),
    DownloadStep(),
    ClassifyStep(),
]

# Ordered list of steps for extract jobs (steps 4-6)
EXTRACT_JOB_STEPS = [
    ExtractStep(),
    ValidateStep(),
    FinalizeStep(),
]

__all__ = [
    "CRAWL_JOB_STEPS",
    "EXTRACT_JOB_STEPS",
    "ClassifyStep",
    "DiscoverStep",
    "DownloadStep",
    "ExtractStep",
    "FinalizeStep",
    "GatherContextStep",
    "ValidateStep",
]
