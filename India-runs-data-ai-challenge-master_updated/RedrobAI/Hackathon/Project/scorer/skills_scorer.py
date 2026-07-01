"""
Skills Scorer — matches candidate skills against JD requirements
with trap-awareness and trust validation.

The JD explicitly warns about keyword stuffers — candidates who list all
the right AI keywords as skills but whose actual career history shows no
relevant work.  This scorer validates skills against career descriptions
and assessment scores.
"""

import re
from scorer.config import (
    MUST_HAVE_SKILL_GROUPS,
    NICE_TO_HAVE_SKILL_GROUPS,
)


def _normalise(text: str) -> str:
    return " ".join(text.lower().split())


def _skill_trust_score(skill: dict, assessments: dict) -> float:
    """
    Compute a trust multiplier (0.0 - 1.0) for a single skill entry.
    
    High trust: high proficiency + endorsements + duration + assessment score.
    Low trust:  "expert" with 0 endorsements, 0 duration, no assessment.
    """
    name = skill.get("name", "")
    proficiency = skill.get("proficiency", "beginner")
    endorsements = skill.get("endorsements", 0)
    duration = skill.get("duration_months", 0)
    
    # Base from proficiency
    prof_map = {"beginner": 0.3, "intermediate": 0.6, "advanced": 0.85, "expert": 1.0}
    base = prof_map.get(proficiency, 0.3)
    
    # Trust signals
    trust = 0.5  # neutral start
    
    # Endorsements — social validation
    if endorsements >= 20:
        trust += 0.2
    elif endorsements >= 5:
        trust += 0.1
    elif endorsements == 0 and proficiency in ("advanced", "expert"):
        trust -= 0.2  # suspicious
    
    # Duration — time invested
    if duration >= 24:
        trust += 0.15
    elif duration >= 12:
        trust += 0.1
    elif duration == 0 and proficiency in ("advanced", "expert"):
        trust -= 0.2  # suspicious
    
    # Assessment score — platform-validated
    if name in assessments:
        ascore = assessments[name]
        if ascore >= 70:
            trust += 0.25
        elif ascore >= 50:
            trust += 0.15
        elif ascore < 30:
            trust -= 0.1  # low score despite claiming skill
    
    trust = max(0.1, min(trust, 1.0))
    return base * trust


def score_skills(candidate: dict) -> tuple[float, dict]:
    """
    Returns (score 0.0-1.0, detail_dict).
    
    Scoring:
      - Must-have skill groups matched:  60% weight
      - Nice-to-have skill groups:       25% weight
      - Skill trust validation:          15% weight (penalise stuffers)
    """
    skills = candidate.get("skills", [])
    signals = candidate.get("redrob_signals", {})
    assessments = signals.get("skill_assessment_scores", {})
    career = candidate.get("career_history", [])
    
    details = {}
    
    # Build normalised skill name set
    skill_names = [_normalise(s.get("name", "")) for s in skills]
    skill_names_set = set(skill_names)
    
    # Also search career descriptions for implicit skill evidence
    all_desc = _normalise(
        " ".join(r.get("description", "") for r in career)
    )
    
    # --- 1. Must-have groups (60%) ---
    must_have_hits = {}
    for group_name, keywords in MUST_HAVE_SKILL_GROUPS.items():
        # Check both explicit skills and career descriptions
        found_in_skills = any(
            any(kw in sn for kw in keywords)
            for sn in skill_names
        )
        found_in_career = any(kw in all_desc for kw in keywords)
        
        if found_in_skills and found_in_career:
            must_have_hits[group_name] = "validated"  # both skill list AND career
        elif found_in_career:
            must_have_hits[group_name] = "career_only"  # implicit but real
        elif found_in_skills:
            must_have_hits[group_name] = "skill_only"  # listed but unvalidated
    
    # Score must-have groups
    total_groups = len(MUST_HAVE_SKILL_GROUPS)
    must_score = 0.0
    for group, status in must_have_hits.items():
        if status == "validated":
            must_score += 1.0
        elif status == "career_only":
            must_score += 0.8  # career evidence is strong even without explicit skill
        elif status == "skill_only":
            must_score += 0.4  # listed but not validated in career
    must_score = must_score / total_groups if total_groups else 0.0
    
    details["must_have_groups"] = must_have_hits
    
    # --- 2. Nice-to-have groups (25%) ---
    nice_hits = {}
    for group_name, keywords in NICE_TO_HAVE_SKILL_GROUPS.items():
        found_in_skills = any(
            any(kw in sn for kw in keywords)
            for sn in skill_names
        )
        found_in_career = any(kw in all_desc for kw in keywords)
        
        if found_in_skills or found_in_career:
            nice_hits[group_name] = (
                "validated" if (found_in_skills and found_in_career)
                else ("career_only" if found_in_career else "skill_only")
            )
    
    total_nice = len(NICE_TO_HAVE_SKILL_GROUPS)
    nice_score = 0.0
    for group, status in nice_hits.items():
        if status == "validated":
            nice_score += 1.0
        elif status == "career_only":
            nice_score += 0.7
        elif status == "skill_only":
            nice_score += 0.3
    nice_score = nice_score / total_nice if total_nice else 0.0
    
    details["nice_to_have_groups"] = nice_hits
    
    # --- 3. Trust score (15%) ---
    # Average trust across all skills — penalises stuffers
    if skills:
        trust_scores = [
            _skill_trust_score(s, assessments) for s in skills
        ]
        avg_trust = sum(trust_scores) / len(trust_scores)
        
        # Extra penalty: if many expert skills with no backing
        expert_count = sum(
            1 for s in skills if s.get("proficiency") == "expert"
        )
        if expert_count >= 8:
            backed = sum(
                1 for s in skills
                if s.get("proficiency") == "expert"
                and (s.get("endorsements", 0) >= 5 or s.get("duration_months", 0) >= 12)
            )
            if backed < expert_count * 0.3:
                avg_trust *= 0.5  # severe stuffer penalty
    else:
        avg_trust = 0.2  # no skills listed at all
    
    details["avg_trust"] = round(avg_trust, 3)
    details["skill_count"] = len(skills)
    
    # --- Combine ---
    final = 0.60 * must_score + 0.25 * nice_score + 0.15 * avg_trust
    final = max(0.0, min(final, 1.0))
    
    details["sub_scores"] = {
        "must_have": round(must_score, 3),
        "nice_to_have": round(nice_score, 3),
        "trust": round(avg_trust, 3),
    }
    
    return round(final, 4), details
