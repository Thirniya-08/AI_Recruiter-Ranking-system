"""Compatibility wrapper around the existing project ranker."""

from rank import load_candidates, score_candidate

__all__ = ["load_candidates", "score_candidate"]
