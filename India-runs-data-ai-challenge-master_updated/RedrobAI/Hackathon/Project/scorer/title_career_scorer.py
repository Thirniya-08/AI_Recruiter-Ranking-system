"""
Title + Career History Scorer — the most important scoring component.

The JD explicitly warns: "The right answer is NOT find candidates whose skills
section contains the most AI keywords."  Career history and actual work
descriptions are weighted far more heavily than skill keyword lists.
"""

import re
from scorer.config import (
    TIER_1_TITLES, TIER_2_TITLES, TIER_3_TITLES, IRRELEVANT_TITLES,
    TITLE_TIER_SCORES, CAREER_KW_HIGH, CAREER_KW_MED,
    CONSULTING_COMPANIES,
)


def _normalise(text: str) -> str:
    """Lowercase, collapse whitespace."""
    return " ".join(text.lower().split())


def _classify_title(title: str) -> int:
    """Return tier number (1-3) or 'irrelevant' or 'unknown'."""
    t = _normalise(title)
    for kw in TIER_1_TITLES:
        if kw in t:
            return 1
    for kw in TIER_2_TITLES:
        if kw in t:
            return 2
    for kw in TIER_3_TITLES:
        if kw in t:
            return 3
    for kw in IRRELEVANT_TITLES:
        if kw in t:
            return "irrelevant"
    return "unknown"


def _keyword_density(text: str, keywords: list[str]) -> int:
    """Count how many distinct keywords appear in text."""
    t = _normalise(text)
    return sum(1 for kw in keywords if kw in t)


def _is_consulting_company(company: str) -> bool:
    c = _normalise(company)
    return any(cc in c for cc in CONSULTING_COMPANIES)


def score_title_career(candidate: dict) -> tuple[float, dict]:
    """
    Returns (score 0.0-1.0, detail_dict).

    Scoring breakdown:
      - Current title tier:        30% of this component
      - Career-history titles:     20% of this component
      - Career descriptions (KW):  35% of this component
      - Company quality:           15% of this component
    """
    profile = candidate.get("profile", {})
    career = candidate.get("career_history", [])

    details = {}

    # --- 1. Current title score (30%) ---
    current_title = profile.get("current_title", "")
    current_tier = _classify_title(current_title)
    current_title_score = TITLE_TIER_SCORES.get(current_tier, 0.20)
    details["current_title"] = current_title
    details["current_tier"] = current_tier

    # --- 2. Career-history title score (20%) ---
    # Best historical title matters — shows career trajectory
    career_title_scores = []
    for role in career:
        tier = _classify_title(role.get("title", ""))
        career_title_scores.append(TITLE_TIER_SCORES.get(tier, 0.20))

    # Weight by recency — most recent roles matter more
    if career_title_scores:
        # career_history is usually ordered most-recent-first
        weighted_sum = 0.0
        weight_total = 0.0
        for i, s in enumerate(career_title_scores):
            w = 1.0 / (1 + i * 0.5)  # decay: 1.0, 0.67, 0.5, 0.4, ...
            weighted_sum += s * w
            weight_total += w
        career_title_avg = weighted_sum / weight_total if weight_total else 0.0
    else:
        career_title_avg = 0.0

    # Best title ever — gives credit to candidates who held relevant roles
    best_title_score = max(career_title_scores) if career_title_scores else 0.0
    hist_title_score = 0.6 * career_title_avg + 0.4 * best_title_score
    details["best_historical_tier"] = (
        max(
            (_classify_title(r.get("title", "")) for r in career),
            key=lambda t: TITLE_TIER_SCORES.get(t, 0),
            default="unknown",
        )
        if career
        else "unknown"
    )

    # --- 3. Career description keyword analysis (35%) ---
    all_descriptions = " ".join(
        role.get("description", "") for role in career
    )
    high_hits = _keyword_density(all_descriptions, CAREER_KW_HIGH)
    med_hits = _keyword_density(all_descriptions, CAREER_KW_MED)

    # Normalise: having 15+ high keywords is excellent
    desc_high_score = min(high_hits / 12.0, 1.0)
    desc_med_score = min(med_hits / 15.0, 1.0)
    desc_score = 0.70 * desc_high_score + 0.30 * desc_med_score

    details["career_kw_high_count"] = high_hits
    details["career_kw_med_count"] = med_hits

    # --- 4. Company quality (15%) ---
    total_roles = len(career)
    consulting_roles = sum(
        1 for r in career if _is_consulting_company(r.get("company", ""))
    )

    if total_roles == 0:
        company_score = 0.3
    elif consulting_roles == total_roles:
        # Entire career at consulting = red flag per JD
        company_score = 0.10
    elif consulting_roles > 0:
        # Mix — some product experience
        product_ratio = 1 - (consulting_roles / total_roles)
        company_score = 0.30 + 0.70 * product_ratio
    else:
        # No consulting at all — good
        company_score = 0.80

    # Bonus for current company not being consulting
    current_company = profile.get("current_company", "")
    if current_company and not _is_consulting_company(current_company):
        company_score = min(company_score + 0.15, 1.0)

    details["consulting_roles"] = consulting_roles
    details["total_roles"] = total_roles
    details["current_company"] = current_company

    # --- 5. Title-hopping penalty ---
    # >3 companies in <=5 years with ascending titles = title chaser
    hop_penalty = 0.0
    if total_roles >= 4:
        short_stints = sum(
            1 for r in career if r.get("duration_months", 99) < 18
        )
        if short_stints >= 3:
            hop_penalty = 0.15
            details["title_hopper_flag"] = True

    # --- Combine ---
    raw = (
        0.30 * current_title_score
        + 0.20 * hist_title_score
        + 0.35 * desc_score
        + 0.15 * company_score
    )
    final = max(0.0, min(raw - hop_penalty, 1.0))

    details["sub_scores"] = {
        "current_title": round(current_title_score, 3),
        "hist_title": round(hist_title_score, 3),
        "desc_keywords": round(desc_score, 3),
        "company_quality": round(company_score, 3),
        "hop_penalty": round(hop_penalty, 3),
    }

    return round(final, 4), details
