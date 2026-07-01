"""Lightweight honeypot rules built for high-volume candidate ranking."""


def skill_mismatch(skills, thresholds):
    expert_zero = 0
    expert_count = 0

    for skill in skills:
        if skill.get("proficiency") == "expert":
            expert_count += 1
            if skill.get("duration_months", 0) == 0:
                expert_zero += 1

    score = 0
    if expert_zero >= thresholds["expert_zero_limit"]:
        score += 1
    if expert_count > thresholds["max_expert_skills"]:
        score += 1

    return score


def experience_mismatch(profile, career):
    if not career:
        return 0

    start_years = [_extract_year(job, "start") for job in career]
    end_years = [_extract_year(job, "end") for job in career]
    start_years = [year for year in start_years if year]
    end_years = [year for year in end_years if year]

    if not start_years or not end_years:
        return 0

    career_span = max(end_years) - min(start_years)
    experience = profile.get("years_of_experience", 0)

    return 1 if experience > career_span + 1 else 0


def education_conflict(education, career):
    for edu in education:
        for job in career:
            start_year = _extract_year(job, "start")
            edu_end_year = edu.get("end_year")
            if start_year and edu_end_year and start_year < edu_end_year - 1:
                return 1
    return 0


def skill_density(skills, thresholds):
    return 1 if len(skills) > thresholds["max_total_skills"] else 0


def _extract_year(item, field_prefix):
    year = item.get(f"{field_prefix}_year")
    if year:
        return year

    date_value = item.get(f"{field_prefix}_date")
    if isinstance(date_value, str) and len(date_value) >= 4:
        try:
            return int(date_value[:4])
        except ValueError:
            return None

    return None
