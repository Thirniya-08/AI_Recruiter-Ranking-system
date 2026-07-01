"""
Location + Logistics Scorer — evaluates geographic fit, notice period,
work-mode compatibility, and relocation willingness.
"""

import re
from scorer.config import PREFERRED_CITIES, ACCEPTABLE_CITIES, INDIA_COUNTRY_NAMES


def _normalise(text: str) -> str:
    return " ".join(text.lower().split())


def score_location(candidate: dict) -> tuple[float, dict]:
    """
    Returns (score 0.0-1.0, detail_dict).
    
    Components:
      - Geographic match:    40% weight
      - Notice period:       30% weight
      - Work mode:           15% weight
      - Relocation + salary: 15% weight
    """
    profile = candidate.get("profile", {})
    signals = candidate.get("redrob_signals", {})
    
    details = {}
    location = _normalise(profile.get("location", ""))
    country = _normalise(profile.get("country", ""))
    
    # --- 1. Geographic match (40%) ---
    geo_score = 0.3  # baseline for unknown
    
    is_india = any(c in country for c in INDIA_COUNTRY_NAMES)
    in_preferred = any(city in location for city in PREFERRED_CITIES)
    in_acceptable = any(city in location for city in ACCEPTABLE_CITIES)
    willing_to_relocate = signals.get("willing_to_relocate", False)
    
    if in_preferred:
        geo_score = 1.0
    elif in_acceptable:
        geo_score = 0.85
    elif is_india and willing_to_relocate:
        geo_score = 0.70
    elif is_india and not willing_to_relocate:
        geo_score = 0.45
    elif not is_india and willing_to_relocate:
        geo_score = 0.30
    elif not is_india and not willing_to_relocate:
        geo_score = 0.10
    
    details["location"] = profile.get("location", "")
    details["country"] = profile.get("country", "")
    details["is_india"] = is_india
    details["geo_score"] = round(geo_score, 3)
    
    # --- 2. Notice period (30%) ---
    notice_days = signals.get("notice_period_days", 60)
    
    if notice_days <= 15:
        notice_score = 1.0
    elif notice_days <= 30:
        notice_score = 0.95  # JD: "we'd love sub-30-day notice"
    elif notice_days <= 45:
        notice_score = 0.85
    elif notice_days <= 60:
        notice_score = 0.75
    elif notice_days <= 90:
        notice_score = 0.55
    elif notice_days <= 120:
        notice_score = 0.35
    else:
        notice_score = 0.20  # 120+ days is very high friction
    
    details["notice_period_days"] = notice_days
    details["notice_score"] = round(notice_score, 3)
    
    # --- 3. Work mode compatibility (15%) ---
    work_mode = signals.get("preferred_work_mode", "flexible")
    
    # JD says hybrid — flexible cadence
    mode_scores = {
        "hybrid": 1.0,     # perfect match
        "flexible": 0.95,  # great
        "onsite": 0.85,    # fine, may be over-committed
        "remote": 0.60,    # mismatch — JD expects some office time
    }
    work_score = mode_scores.get(work_mode, 0.70)
    
    details["preferred_work_mode"] = work_mode
    details["work_mode_score"] = round(work_score, 3)
    
    # --- 4. Relocation + salary reasonableness (15%) ---
    misc_score = 0.5  # baseline
    
    if willing_to_relocate:
        misc_score += 0.2
    
    # Salary range — JD doesn't specify but senior AI engineer at Series A
    # in India is roughly 25-50 LPA. Candidates expecting 80+ may be misaligned.
    salary = signals.get("expected_salary_range_inr_lpa", {})
    sal_min = salary.get("min", 0)
    sal_max = salary.get("max", 0)
    
    if sal_max > 0:
        if 15 <= sal_max <= 60:
            misc_score += 0.2  # reasonable range
        elif sal_max <= 15:
            misc_score += 0.15  # underpriced — still fine
        elif sal_max <= 80:
            misc_score += 0.1  # on the high side
        else:
            misc_score += 0.0  # very high expectations
    
    misc_score = min(misc_score, 1.0)
    
    details["willing_to_relocate"] = willing_to_relocate
    details["salary_range"] = salary
    details["misc_score"] = round(misc_score, 3)
    
    # --- Combine ---
    final = (
        0.40 * geo_score
        + 0.30 * notice_score
        + 0.15 * work_score
        + 0.15 * misc_score
    )
    final = max(0.0, min(final, 1.0))
    
    details["sub_scores"] = {
        "geo": round(geo_score, 3),
        "notice": round(notice_score, 3),
        "work_mode": round(work_score, 3),
        "misc": round(misc_score, 3),
    }
    
    return round(final, 4), details
