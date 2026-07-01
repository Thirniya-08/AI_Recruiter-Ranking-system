"""Compatibility package for ranking pipeline imports."""

from .ranker import load_candidates, score_candidate

__all__ = ["load_candidates", "score_candidate"]
