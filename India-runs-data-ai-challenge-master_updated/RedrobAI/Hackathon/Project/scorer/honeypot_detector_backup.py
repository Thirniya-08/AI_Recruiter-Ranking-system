"""
Honeypot Detector — identifies candidates with subtly impossible profiles.

The dataset contains ~80 honeypots that are forced to relevance tier 0.
Submissions with honeypot rate >10% in top 100 are disqualified.
"""

from datetime import date
from scorer.config import TODAY


def detect_honeypot(candidate: dict) -> tuple[bool, list[str]]:
    """
    Returns (is_honeypot: bool, reasons: list[str]).
    A candidate is flagged as a honeypot if they trigger 2+ red flags.
    """
    red_flags = []

    profile = candidate.get("profile", {})
    career = candidate.get("career_history", [])
    education = candidate.get("education", [])
    skills = candidate.get("skills", [])
    signals = candidate.get("redrob_signals", {})

    yoe = profile.get("years_of_experience", 0)

    # -------------------------------------------------------------------------
    # Check 1: Expert-level skills with zero duration or zero endorsements
    # -------------------------------------------------------------------------
    expert_skills = [s for s in skills if s.get("proficiency") == "expert"]
    expert_zero_duration = [
        s for s in expert_skills if s.get("duration_months", 0) == 0
    ]
    expert_zero_endorsements = [
        s for s in expert_skills if s.get("endorsements", 0) == 0
    ]

    if len(expert_skills) >= 8 and len(expert_zero_duration) >= 5:
        red_flags.append(
            f"{len(expert_skills)} expert skills but {len(expert_zero_duration)} "
            f"have 0 months duration"
        )

    if len(expert_skills) >= 8 and len(expert_zero_endorsements) >= 6:
        red_flags.append(
            f"{len(expert_skills)} expert skills but {len(expert_zero_endorsements)} "
            f"have 0 endorsements"
        )

    # -------------------------------------------------------------------------
    # Check 2: Career timeline impossibility — total duration >> years_of_exp
    # -------------------------------------------------------------------------
    if career:
        total_career_months = sum(
            r.get("duration_months", 0) for r in career
        )
        yoe_months = yoe * 12
        # Allow some overlap (parallel roles) but flag extreme cases
        if yoe_months > 0 and total_career_months > yoe_months * 2.0:
            red_flags.append(
                f"Total career months ({total_career_months}) is >{2}x "
                f"years_of_experience ({yoe} yrs = {yoe_months:.0f} months)"
            )

    # -------------------------------------------------------------------------
    # Check 3: Impossible tenure at a company
    # -------------------------------------------------------------------------
    for role in career:
        start_str = role.get("start_date")
        duration = role.get("duration_months", 0)
        if start_str and duration:
            try:
                start = date.fromisoformat(start_str)
                # If they claim e.g. 96 months at a company but start_date
                # is only 36 months ago, that's impossible
                months_since_start = (TODAY.year - start.year) * 12 + (
                    TODAY.month - start.month
                )
                if months_since_start > 0 and duration > months_since_start + 6:
                    red_flags.append(
                        f"Role at {role.get('company', '?')}: claims "
                        f"{duration} months but start_date is only "
                        f"{months_since_start} months ago"
                    )
            except (ValueError, TypeError):
                pass

    # -------------------------------------------------------------------------
    # Check 4: Education impossibility
    # -------------------------------------------------------------------------
    for edu in education:
        start_y = edu.get("start_year", 0)
        end_y = edu.get("end_year", 0)
        if start_y and end_y:
            if end_y < start_y:
                red_flags.append(
                    f"Education end_year ({end_y}) < start_year ({start_y})"
                )
            duration_yrs = end_y - start_y
            degree = edu.get("degree", "").lower()
            # A bachelor's in <2 years or >8 years is suspicious
            if "b." in degree or "bachelor" in degree:
                if duration_yrs < 2 or duration_yrs > 8:
                    red_flags.append(
                        f"Bachelor's degree in {duration_yrs} years "
                        f"({start_y}-{end_y})"
                    )

    # -------------------------------------------------------------------------
    # Check 5: Experience vs graduation date
    # -------------------------------------------------------------------------
    if education:
        earliest_grad = min(
            (e.get("end_year", 9999) for e in education), default=9999
        )
        if earliest_grad < 9999 and yoe > 0:
            # Implied start of career
            implied_career_start_year = TODAY.year - yoe
            # If they supposedly started working >3 years before graduating
            if implied_career_start_year < earliest_grad - 3:
                red_flags.append(
                    f"Implied career start ({implied_career_start_year:.0f}) "
                    f"is >3 years before earliest graduation ({earliest_grad})"
                )

    # -------------------------------------------------------------------------
    # Check 6: Extremely high skill count with all "expert" and no validation
    # -------------------------------------------------------------------------
    if len(expert_skills) >= 10:
        # Check if assessment scores exist for any of them
        assessments = signals.get("skill_assessment_scores", {})
        assessed_experts = sum(
            1 for s in expert_skills if s["name"] in assessments
        )
        if assessed_experts == 0:
            red_flags.append(
                f"{len(expert_skills)} expert-level skills with "
                f"0 platform assessments completed"
            )

    # -------------------------------------------------------------------------
    # Check 7: Overlapping employment dates
    # -------------------------------------------------------------------------
    dated_roles = []
    for role in career:
        start_str = role.get("start_date")
        end_str = role.get("end_date")
        if start_str:
            try:
                s = date.fromisoformat(start_str)
                e = (
                    date.fromisoformat(end_str)
                    if end_str
                    else TODAY
                )
                dated_roles.append((s, e, role.get("company", "?")))
            except (ValueError, TypeError):
                pass

    dated_roles.sort(key=lambda x: x[0])
    overlap_count = 0
    for i in range(len(dated_roles) - 1):
        _, end_i, _ = dated_roles[i]
        start_next, _, _ = dated_roles[i + 1]
        # Allow 30 days overlap (notice period transition)
        if end_i > start_next and (end_i - start_next).days > 30:
            overlap_count += 1
    if overlap_count >= 2:
        red_flags.append(
            f"{overlap_count} overlapping employment periods (>30 days each)"
        )

    # -------------------------------------------------------------------------
    # Check 8: Skill assessment scores impossibly perfect
    # -------------------------------------------------------------------------
    assessments = signals.get("skill_assessment_scores", {})
    if len(assessments) >= 5:
        perfect_scores = sum(1 for v in assessments.values() if v == 100)
        if perfect_scores >= 5:
            red_flags.append(
                f"{perfect_scores} perfect (100) assessment scores"
            )

    # -------------------------------------------------------------------------
    # Decision: 2+ red flags = honeypot
    # -------------------------------------------------------------------------
    is_honeypot = len(red_flags) >= 2
    return is_honeypot, red_flags
