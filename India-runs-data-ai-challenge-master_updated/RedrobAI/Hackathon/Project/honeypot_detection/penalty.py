"""Penalty helpers for reducing suspicious candidates' ranking scores."""

from .config import PENALTY_WEIGHTS


def get_penalty(score):
    return PENALTY_WEIGHTS.get(score, 0.05)


def apply_penalty(base_score, honeypot_score):
    penalty = get_penalty(honeypot_score)
    return base_score * penalty
