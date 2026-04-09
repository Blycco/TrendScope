"""Pipeline stage modules — one file per processing stage."""

from backend.processor.stages.cache import stage_warm_cache
from backend.processor.stages.cluster import stage_cluster
from backend.processor.stages.dedupe import stage_dedupe
from backend.processor.stages.keywords import stage_extract_keywords
from backend.processor.stages.match_existing import stage_match_existing_groups
from backend.processor.stages.normalize import stage_normalize
from backend.processor.stages.save import stage_save
from backend.processor.stages.score import stage_score
from backend.processor.stages.spam_filter import stage_spam_filter
from backend.processor.stages.summarize import stage_summarize

__all__ = [
    "stage_dedupe",
    "stage_normalize",
    "stage_spam_filter",
    "stage_extract_keywords",
    "stage_match_existing_groups",
    "stage_cluster",
    "stage_score",
    "stage_summarize",
    "stage_save",
    "stage_warm_cache",
]
