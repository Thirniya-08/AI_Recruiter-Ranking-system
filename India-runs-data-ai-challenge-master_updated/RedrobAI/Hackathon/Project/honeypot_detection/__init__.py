"""Fast, offline honeypot detection package for ranking integration."""

from .detector import compute_honeypot_score, evaluate_candidate, is_honeypot
from .penalty import apply_penalty, get_penalty

__all__ = [
    "apply_penalty",
    "compute_honeypot_score",
    "evaluate_candidate",
    "get_penalty",
    "is_honeypot",
]
