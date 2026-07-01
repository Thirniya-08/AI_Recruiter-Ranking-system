"""
Experience Scorer — evaluates years of experience against the JD's ideal range
plus career trajectory quality signals.
"""

import re
from scorer.config import CS_FIELDS


def _normalise(text: str) -> str:
    return " ".join(text.lower().split())


def _yoe_curve(years: float) -> float:
    """
    Score based on years-of-experience alignment with JD (5-9 ideal).
    Returns 0.0 - 1.0.
    """
    if years < 1:
        return 0.05
    if years < 2:
        return 0.10
    if years < 3:
        return 0.20
    if years < 4:
        return 0.35
    if years < 5:
        return 0.70
    if years <= 9:
        return 1.0   # sweet spot
    if years <= 11:
        return 0.80
    if years <= 14:
        return 0.55
    return 0.35  # 15+ — likely moved to management


def score_experience(candidate: dict) -> tuple[float, dict]:
    """
    Returns (score 0.0-1.0, detail_dict).
    
    Components:
      - YoE curve fit:           50% weight
      - Career trajectory:       30% weight (recency of coding, progression)
      - Education relevance:     20% weight
    """
    profile = candidate.get("profile", {})
    career = candidate.get("career_history", [])
    education = candidate.get("education", [])
    
    details = {}
    yoe = profile.get("years_of_experience", 0)
    
    # --- 1. YoE curve (50%) ---
    yoe_score = _yoe_curve(yoe)
    details["years_of_experience"] = yoe
    details["yoe_score"] = round(yoe_score, 3)
    
    # --- 2. Career trajectory (30%) ---
    traj_score = 0.5  # baseline
    
    if career:
        # Check if most recent role involves coding/technical work
        latest = career[0] if career else {}
        latest_desc = _normalise(latest.get("description", ""))
        coding_keywords = [
            "code", "coding", "python", "engineering", "built", "shipped",
            "implemented", "developed", "designed", "architecture",
            "system", "model", "pipeline", "api", "deployed",
            "machine learning", "ml", "ai", "data",
        ]
        recent_coding = sum(1 for kw in coding_keywords if kw in latest_desc)
        
        if recent_coding >= 5:
            traj_score += 0.3  # actively coding recently
        elif recent_coding >= 2:
            traj_score += 0.15
        
        # Check for management-only recent role (negative per JD)
        mgmt_keywords = ["managed", "led team", "team lead", "manager",
                         "director", "vp", "head of", "people management"]
        recent_mgmt = sum(1 for kw in mgmt_keywords if kw in latest_desc)
        
        if recent_mgmt >= 3 and recent_coding < 2:
            traj_score -= 0.2  # moved away from coding
        
        # Career progression quality — are they growing in the right direction?
        ml_progression = 0
        for i, role in enumerate(career):
            desc = _normalise(role.get("description", ""))
            ml_terms = sum(1 for kw in [
                "machine learning", "ml", "ai", "nlp", "embedding",
                "retrieval", "ranking", "deep learning", "model",
            ] if kw in desc)
            if ml_terms >= 2:
                ml_progression += 1
        
        if ml_progression >= 2:
            traj_score += 0.15  # multiple ML-relevant roles
        elif ml_progression == 1:
            traj_score += 0.05
        
        # Number of distinct companies — stability vs breadth
        companies = set(r.get("company", "") for r in career)
        if len(career) >= 4 and len(companies) >= 4:
            avg_tenure = sum(r.get("duration_months", 0) for r in career) / len(career)
            if avg_tenure < 15:
                traj_score -= 0.1  # too many short stints
    
    traj_score = max(0.0, min(traj_score, 1.0))
    details["trajectory_score"] = round(traj_score, 3)
    
    # --- 3. Education relevance (20%) ---
    edu_score = 0.3  # baseline — education is not critical per JD
    
    if education:
        best_field_score = 0.0
        best_tier_score = 0.0
        best_degree_score = 0.0
        
        for edu in education:
            field = _normalise(edu.get("field_of_study", ""))
            tier = edu.get("tier", "unknown")
            degree = _normalise(edu.get("degree", ""))
            
            # Field relevance
            field_relevant = any(f in field for f in CS_FIELDS)
            if field_relevant:
                best_field_score = max(best_field_score, 0.4)
            
            # Tier
            tier_map = {
                "tier_1": 0.30, "tier_2": 0.20,
                "tier_3": 0.10, "tier_4": 0.0, "unknown": 0.05,
            }
            best_tier_score = max(best_tier_score, tier_map.get(tier, 0.0))
            
            # Degree level
            if "ph.d" in degree or "phd" in degree:
                best_degree_score = max(best_degree_score, 0.15)
            elif "m.tech" in degree or "m.e." in degree or "m.sc" in degree:
                best_degree_score = max(best_degree_score, 0.12)
            elif "b.tech" in degree or "b.e." in degree:
                best_degree_score = max(best_degree_score, 0.08)
        
        edu_score = 0.3 + best_field_score + best_tier_score + best_degree_score
        edu_score = min(edu_score, 1.0)
    
    details["education_score"] = round(edu_score, 3)
    
    # --- Combine ---
    final = 0.50 * yoe_score + 0.30 * traj_score + 0.20 * edu_score
    final = max(0.0, min(final, 1.0))
    
    details["sub_scores"] = {
        "yoe_curve": round(yoe_score, 3),
        "trajectory": round(traj_score, 3),
        "education": round(edu_score, 3),
    }
    
    return round(final, 4), details
