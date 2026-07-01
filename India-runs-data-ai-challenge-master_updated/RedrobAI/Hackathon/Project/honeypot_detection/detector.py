"""Rule-based REAL/FAKE honeypot detection engine.

Classification rule:
    red_flag_score >= 2 -> FAKE
    red_flag_score < 2  -> REAL
"""

UNREALISTIC_SUMMARY_KEYWORDS = (
    "agi",
    "quantum ai",
    "mastered everything",
    "expert in all domains",
)


def _safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _is_expert(skill):
    return str(skill.get("proficiency", "")).strip().lower() == "expert"


def extract_features(candidate):
    """Extract mandatory core and derived honeypot features."""
    profile = candidate.get("profile", {}) or {}
    skills = candidate.get("skills", []) or []
    signals = candidate.get("redrob_signals", {}) or {}

    years_of_experience = _safe_float(profile.get("years_of_experience", 0))
    num_skills = len(skills)
    expert_skills = [skill for skill in skills if _is_expert(skill)]
    num_expert_skills = len(expert_skills)
    skill_durations = [_safe_float(skill.get("duration_months", 0)) for skill in skills]
    avg_skill_duration = sum(skill_durations) / num_skills if num_skills else 0.0
    total_endorsements = int(sum(_safe_float(skill.get("endorsements", 0)) for skill in skills))
    profile_completeness_score = _safe_float(
        signals.get(
            "profile_completeness_score",
            profile.get("profile_completeness_score", 0),
        )
    )
    summary = str(profile.get("summary", "") or "")
    summary_lower = summary.lower()

    expert_skill_duration_gap = any(
        _safe_float(skill.get("duration_months", 0)) < 12
        for skill in expert_skills
    )
    skill_explosion_flag = num_skills > 10 and years_of_experience < 3
    low_credibility_flag = total_endorsements < 5 and num_expert_skills > 0
    weak_profile_flag = profile_completeness_score < 50
    unrealistic_summary_flag = any(
        keyword in summary_lower
        for keyword in UNREALISTIC_SUMMARY_KEYWORDS
    )

    return {
        "years_of_experience": years_of_experience,
        "num_skills": num_skills,
        "num_expert_skills": num_expert_skills,
        "avg_skill_duration": round(avg_skill_duration, 2),
        "total_endorsements": total_endorsements,
        "profile_completeness_score": profile_completeness_score,
        "expert_skill_duration_gap": expert_skill_duration_gap,
        "skill_explosion_flag": skill_explosion_flag,
        "low_credibility_flag": low_credibility_flag,
        "weak_profile_flag": weak_profile_flag,
        "unrealistic_summary_flag": unrealistic_summary_flag,
    }


def evaluate_flags(features):
    """Return the mandatory boolean red flags from extracted features."""
    return {
        "expert_skill_duration_gap": bool(features["expert_skill_duration_gap"]),
        "skill_explosion_flag": bool(features["skill_explosion_flag"]),
        "low_credibility_flag": bool(features["low_credibility_flag"]),
        "weak_profile_flag": bool(features["weak_profile_flag"]),
        "unrealistic_summary_flag": bool(features["unrealistic_summary_flag"]),
    }


def explain_flags(features, flags):
    """Generate human-readable reasons for all triggered red flags."""
    reasons = []

    if flags["expert_skill_duration_gap"]:
        reasons.append(
            "expert_skill_duration_gap: at least one expert skill has duration under 12 months"
        )
    if flags["skill_explosion_flag"]:
        reasons.append(
            "skill_explosion_flag: candidate lists "
            f"{features['num_skills']} skills with only "
            f"{features['years_of_experience']:.1f} years of experience"
        )
    if flags["low_credibility_flag"]:
        reasons.append(
            "low_credibility_flag: expert skills are claimed but total endorsements "
            f"are only {features['total_endorsements']}"
        )
    if flags["weak_profile_flag"]:
        reasons.append(
            "weak_profile_flag: profile completeness score is "
            f"{features['profile_completeness_score']:.1f}, below 50"
        )
    if flags["unrealistic_summary_flag"]:
        reasons.append(
            "unrealistic_summary_flag: summary contains unrealistic claim keywords"
        )

    return reasons


def analyze_candidate(candidate):
    """Run the full REAL/FAKE honeypot classification process."""
    features = extract_features(candidate)
    flags = evaluate_flags(features)
    red_flag_score = sum(1 for value in flags.values() if value)
    classification = "FAKE" if red_flag_score >= 2 else "REAL"
    reasons = explain_flags(features, flags)

    return {
        "features": features,
        "flags": flags,
        "red_flag_score": red_flag_score,
        "classification": classification,
        "is_honeypot": classification == "FAKE",
        "reasons": reasons,
    }


def compute_honeypot_score(candidate):
    """Return the red flag score."""
    return analyze_candidate(candidate)["red_flag_score"]


def is_honeypot(candidate):
    return analyze_candidate(candidate)["is_honeypot"]


def is_honeypot_score(score):
    return score >= 2


def evaluate_candidate(candidate):
    analysis = analyze_candidate(candidate)
    return (
        analysis["red_flag_score"],
        analysis["is_honeypot"],
        explain_honeypot(candidate, analysis["red_flag_score"]),
    )


def explain_honeypot(candidate, score=None):
    analysis = analyze_candidate(candidate)
    reasons = list(analysis["reasons"])

    if not reasons and score:
        reasons.append(f"red_flag_score={score}")

    return reasons
