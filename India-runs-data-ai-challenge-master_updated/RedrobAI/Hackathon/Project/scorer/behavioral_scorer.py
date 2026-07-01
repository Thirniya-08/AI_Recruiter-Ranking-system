"""
Behavioral Scorer — evaluates Redrob platform engagement signals.

The JD explicitly states: "A perfect-on-paper candidate who hasn't logged in
for 6 months and has a 5% response rate is, for hiring purposes, not actually
available. Down-weight them appropriately."

This scorer produces both an additive component score and a multiplicative
modifier that can be applied to the overall composite.
"""

from datetime import date
from scorer.config import TODAY, BEHAVIORAL


def score_behavioral(candidate: dict) -> tuple[float, dict]:
    """
    Returns (score 0.0-1.0, detail_dict).
    
    The score is an additive component.  The detail_dict also contains
    a 'modifier' key (0.3-1.5) that can be used multiplicatively.
    """
    signals = candidate.get("redrob_signals", {})
    details = {}
    
    # --- 1. Availability & recency (25%) ---
    availability_score = 0.5
    
    # Open to work
    if signals.get("open_to_work_flag", False):
        availability_score += 0.2
    
    # Last active recency
    last_active_str = signals.get("last_active_date", "")
    days_since_active = 999
    if last_active_str:
        try:
            last_active = date.fromisoformat(last_active_str)
            days_since_active = (TODAY - last_active).days
        except (ValueError, TypeError):
            pass
    
    if days_since_active <= BEHAVIORAL["active_days_excellent"]:
        availability_score += 0.3
    elif days_since_active <= BEHAVIORAL["active_days_good"]:
        availability_score += 0.2
    elif days_since_active <= BEHAVIORAL["active_days_ok"]:
        availability_score += 0.1
    elif days_since_active <= BEHAVIORAL["active_days_stale"]:
        availability_score -= 0.1
    else:
        availability_score -= 0.3  # ghost profile
    
    availability_score = max(0.0, min(availability_score, 1.0))
    details["days_since_active"] = days_since_active
    details["open_to_work"] = signals.get("open_to_work_flag", False)
    
    # --- 2. Responsiveness (25%) ---
    response_score = 0.5
    
    rr = signals.get("recruiter_response_rate", 0.0)
    if rr >= BEHAVIORAL["response_rate_high"]:
        response_score += 0.3
    elif rr >= BEHAVIORAL["response_rate_ok"]:
        response_score += 0.15
    elif rr >= BEHAVIORAL["response_rate_low"]:
        response_score += 0.0
    else:
        response_score -= 0.2  # very unresponsive
    
    art = signals.get("avg_response_time_hours", 999)
    if art <= BEHAVIORAL["response_time_fast_hrs"]:
        response_score += 0.15
    elif art <= BEHAVIORAL["response_time_ok_hrs"]:
        response_score += 0.05
    else:
        response_score -= 0.1
    
    response_score = max(0.0, min(response_score, 1.0))
    details["recruiter_response_rate"] = rr
    details["avg_response_time_hours"] = art
    
    # --- 3. Platform credibility (20%) ---
    cred_score = 0.5
    
    # Verified accounts
    if signals.get("verified_email", False):
        cred_score += 0.1
    if signals.get("verified_phone", False):
        cred_score += 0.1
    if signals.get("linkedin_connected", False):
        cred_score += 0.1
    
    # Profile completeness
    pcs = signals.get("profile_completeness_score", 0)
    if pcs >= BEHAVIORAL["completeness_good"]:
        cred_score += 0.15
    elif pcs >= 60:
        cred_score += 0.05
    elif pcs < 40:
        cred_score -= 0.1
    
    cred_score = max(0.0, min(cred_score, 1.0))
    details["profile_completeness"] = pcs
    
    # --- 4. External validation (15%) ---
    external_score = 0.5
    
    # GitHub activity
    github = signals.get("github_activity_score", -1)
    if github >= BEHAVIORAL["github_strong"]:
        external_score += 0.3
    elif github >= BEHAVIORAL["github_moderate"]:
        external_score += 0.15
    elif github >= 0:
        external_score += 0.05
    # -1 means no GitHub — neutral for non-tech roles, slight negative for AI
    elif github == -1:
        external_score -= 0.05
    
    # Saved by recruiters
    saved = signals.get("saved_by_recruiters_30d", 0)
    if saved >= BEHAVIORAL["saved_by_high"]:
        external_score += 0.15
    elif saved >= BEHAVIORAL["saved_by_moderate"]:
        external_score += 0.08
    
    external_score = max(0.0, min(external_score, 1.0))
    details["github_activity_score"] = github
    details["saved_by_recruiters_30d"] = saved
    
    # --- 5. Interview track record (15%) ---
    interview_score = 0.5
    
    icr = signals.get("interview_completion_rate", 0.0)
    if icr >= BEHAVIORAL["interview_good"]:
        interview_score += 0.25
    elif icr >= BEHAVIORAL["interview_bad"]:
        interview_score += 0.1
    else:
        interview_score -= 0.15
    
    oar = signals.get("offer_acceptance_rate", -1)
    if oar >= 0.7:
        interview_score += 0.15
    elif oar >= 0.4:
        interview_score += 0.05
    elif oar >= 0 and oar < 0.3:
        interview_score -= 0.1  # rejects a lot of offers
    # -1 means no offer history — neutral
    
    interview_score = max(0.0, min(interview_score, 1.0))
    details["interview_completion_rate"] = icr
    details["offer_acceptance_rate"] = oar
    
    # --- Combine into additive score ---
    additive = (
        0.25 * availability_score
        + 0.25 * response_score
        + 0.20 * cred_score
        + 0.15 * external_score
        + 0.15 * interview_score
    )
    additive = max(0.0, min(additive, 1.0))
    
    # --- Compute multiplicative modifier ---
    # This captures the "ghost profile" penalty more aggressively
    modifier = 1.0
    
    if signals.get("open_to_work_flag", False):
        modifier *= 1.08
    
    if days_since_active <= 7:
        modifier *= 1.10
    elif days_since_active <= 30:
        modifier *= 1.05
    elif days_since_active <= 90:
        modifier *= 0.97
    elif days_since_active <= 180:
        modifier *= 0.82
    else:
        modifier *= 0.55  # ghost — heavy penalty
    
    if rr >= 0.7:
        modifier *= 1.08
    elif rr < 0.2:
        modifier *= 0.75
    
    if icr >= 0.8:
        modifier *= 1.04
    elif icr < 0.5:
        modifier *= 0.88
    
    if pcs >= 80:
        modifier *= 1.04
    
    if github >= 50:
        modifier *= 1.08
    elif github >= 20:
        modifier *= 1.03
    
    modifier = max(0.35, min(modifier, 1.50))
    
    details["modifier"] = round(modifier, 3)
    details["sub_scores"] = {
        "availability": round(availability_score, 3),
        "response": round(response_score, 3),
        "credibility": round(cred_score, 3),
        "external": round(external_score, 3),
        "interview": round(interview_score, 3),
    }
    
    return round(additive, 4), details
