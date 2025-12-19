from app.jobs.steps.step_00_parse_input import ParseInputStep
from app.jobs.steps.step_01_check_cache import CheckCacheStep
from app.jobs.steps.step_02_external_search import ExternalSearchStep
from app.jobs.steps.step_03_find_pdf import FindPDFStep
from app.jobs.steps.step_04_download_pdf import DownloadPDFStep
from app.jobs.steps.step_05_validate_pdf import ValidatePDFStep
from app.jobs.steps.step_06_extract_data import ExtractDataStep
from app.jobs.steps.step_07_finalize import FinalizeStep

SEARCH_JOB_STEPS = [
    ParseInputStep(),
    CheckCacheStep(),
    ExternalSearchStep(),
    FindPDFStep(),
    DownloadPDFStep(),
    ValidatePDFStep(),
    ExtractDataStep(),
    FinalizeStep(),
]

__all__ = [
    "ParseInputStep",
    "CheckCacheStep",
    "ExternalSearchStep",
    "FindPDFStep",
    "DownloadPDFStep",
    "ValidatePDFStep",
    "ExtractDataStep",
    "FinalizeStep",
    "SEARCH_JOB_STEPS",
]
