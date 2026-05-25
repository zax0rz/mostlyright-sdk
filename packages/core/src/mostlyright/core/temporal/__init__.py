"""tradewinds.core.temporal — temporal-safety primitives.

Public exports:
- TimePoint (UTC-aware timestamp wrapper with DST + ns truncation handling)
- KnowledgeView (filter DataFrame by knowledge_time <= as_of; plain class with __slots__)
- LeakageDetector + assert_no_leakage (loud as-of cutoff enforcement)
"""

from tradewinds.core.temporal.knowledge_view import KnowledgeView
from tradewinds.core.temporal.leakage import LeakageDetector, assert_no_leakage
from tradewinds.core.temporal.timepoint import TimePoint

__all__ = [
    "KnowledgeView",
    "LeakageDetector",
    "TimePoint",
    "assert_no_leakage",
]
