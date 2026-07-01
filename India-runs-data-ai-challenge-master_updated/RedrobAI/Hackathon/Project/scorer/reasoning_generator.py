"""
Reasoning Generator — produces a unique, profile-grounded 1-2 sentence
justification for each ranked candidate.

The submission spec (Stage 4) checks that:
  - Reasoning references specific facts from the candidate's profile
  - No hallucinated skills/companies
  - Reasonings are substantively different (not templated)
  - Tone matches rank (rank-5 shouldn't have critical reasoning)
"""

import re


def _normalise(text: str) -> str:
    return " ".join(text.lower().split())


def _get_relevant_skills(candidate: dict, max_skills: int = 4) -> list[str]:
    """Pick the most relevant, trusted skills to mention."""
    skills = candidate.get("skills", [])
    signals = candidate.get("redrob_signals", {})
    assessments = signals.get("skill_assessment_scores", {})
    
    # Score each skill by relevance + trust
    AI_RELEVANT = [
        "nlp", "machine learning", "deep learning", "pytorch", "tensorflow",
        "bert", "transformer", "embeddings", "faiss", "pinecone", "weaviate",
        "qdrant", "elasticsearch", "python", "ranking", "retrieval",
        "recommendation", "search", "vector", "xgboost", "lightgbm",
        "lora", "qlora", "peft", "fine-tuning", "llm", "rag",
        "sentence-transformers", "huggingface", "mlops", "airflow",
        "mlflow", "wandb", "docker", "kubernetes",
        "scikit-learn", "sklearn", "numpy", "pandas",
    ]
    
    scored = []
    for s in skills:
        name = s.get("name", "")
        name_lower = _normalise(name)
        
        relevant = any(kw in name_lower for kw in AI_RELEVANT)
        if not relevant:
            continue
        
        trust = 0.5
        if s.get("endorsements", 0) >= 5:
            trust += 0.2
        if s.get("duration_months", 0) >= 12:
            trust += 0.2
        if name in assessments and assessments[name] >= 50:
            trust += 0.2
        
        scored.append((trust, name))
    
    scored.sort(key=lambda x: -x[0])
    return [name for _, name in scored[:max_skills]]


def _describe_career_highlight(candidate: dict) -> str:
    """Extract a specific career highlight to mention in reasoning."""
    career = candidate.get("career_history", [])
    if not career:
        return ""
    
    # Look for the most relevant role description
    best_role = None
    best_score = -1
    
    highlight_terms = [
        "ranking", "retrieval", "embeddings", "recommendation",
        "search", "nlp", "machine learning", "ml", "ai",
        "deployed", "shipped", "production", "built", "designed",
        "vector", "transformer", "model", "pipeline",
    ]
    
    for role in career:
        desc = _normalise(role.get("description", ""))
        score = sum(1 for t in highlight_terms if t in desc)
        if score > best_score:
            best_score = score
            best_role = role
    
    if best_role and best_score >= 3:
        company = best_role.get("company", "")
        title = best_role.get("title", "")
        return f"{title} at {company}" if company and title else ""
    
    return ""


def generate_reasoning(
    candidate: dict,
    rank: int,
    final_score: float,
    score_details: dict,
) -> str:
    """
    Generate a 1-2 sentence reasoning for this candidate at this rank.
    Each reasoning is unique because it references specific profile data.
    """
    profile = candidate.get("profile", {})
    signals = candidate.get("redrob_signals", {})
    
    current_title = profile.get("current_title", "Unknown")
    yoe = profile.get("years_of_experience", 0)
    current_company = profile.get("current_company", "")
    location = profile.get("location", "")
    country = profile.get("country", "")
    
    parts = []
    concerns = []
    
    # --- Lead: title + experience ---
    parts.append(f"{current_title} with {yoe:.1f} years of experience")
    
    if current_company:
        parts[-1] += f" at {current_company}"
    
    # --- Career highlight ---
    highlight = _describe_career_highlight(candidate)
    if highlight:
        parts.append(f"previously worked as {highlight}")
    
    # --- Relevant skills ---
    rel_skills = _get_relevant_skills(candidate)
    if rel_skills:
        if len(rel_skills) <= 2:
            parts.append(f"skilled in {' and '.join(rel_skills)}")
        else:
            parts.append(
                f"skilled in {', '.join(rel_skills[:-1])} and {rel_skills[-1]}"
            )
    
    # --- Behavioral positives ---
    rr = signals.get("recruiter_response_rate", 0)
    github = signals.get("github_activity_score", -1)
    
    behavioral_positives = []
    if rr >= 0.7:
        behavioral_positives.append("strong recruiter engagement")
    if github >= 50:
        behavioral_positives.append("active GitHub contributor")
    if signals.get("open_to_work_flag", False):
        behavioral_positives.append("open to opportunities")
    
    if behavioral_positives:
        parts.append("; ".join(behavioral_positives))
    
    # --- Location note ---
    loc_details = score_details.get("location", {})
    geo_score = loc_details.get("geo_score", 0.5)
    if geo_score >= 0.85:
        pass  # No need to mention — good location is implicit
    elif geo_score >= 0.45:
        if location:
            concerns.append(f"based in {location}")
    else:
        if location and country:
            concerns.append(f"based in {location}, {country}")
        elif country:
            concerns.append(f"based in {country}")
    
    # --- Concerns (honesty per spec) ---
    notice = signals.get("notice_period_days", 60)
    if notice > 60:
        concerns.append(f"notice period ({notice}d) may slow hiring")
    
    if rr < 0.3 and rr > 0:
        concerns.append(f"low recruiter response rate ({rr:.0%})")
    
    beh_details = score_details.get("behavioral", {})
    days_inactive = beh_details.get("days_since_active", 0)
    if days_inactive > 90:
        concerns.append("limited recent platform activity")
    
    # Career concerns
    tc_details = score_details.get("title_career", {})
    if tc_details.get("consulting_roles", 0) == tc_details.get("total_roles", 1) and tc_details.get("total_roles", 0) > 0:
        concerns.append("career primarily in consulting/services")
    
    # Experience concern
    if yoe < 4:
        concerns.append("below the preferred experience range")
    elif yoe > 12:
        concerns.append("above the typical experience band for this role")
    
    # --- Assemble ---
    positive_text = "; ".join(parts)
    
    if concerns and rank > 50:
        # For lower-ranked candidates, be more explicit about gaps
        concern_text = "; ".join(concerns)
        reasoning = f"{positive_text}. Concerns: {concern_text}."
    elif concerns:
        # For higher-ranked candidates, mention concerns briefly
        concern_text = concerns[0]  # just the top concern
        reasoning = f"{positive_text}; {concern_text}."
    else:
        reasoning = f"{positive_text}."
    
    # Ensure it's not too long (spec says 1-2 sentences)
    if len(reasoning) > 300:
        reasoning = reasoning[:297] + "..."
    
    # Clean up double spaces and punctuation
    reasoning = re.sub(r"\s+", " ", reasoning)
    reasoning = reasoning.replace("; .", ".")
    reasoning = reasoning.replace(".. ", ". ")
    
    return reasoning
