"""Performance helpers for batch honeypot processing."""


def preprocess_candidate(candidate):
    """
    Optional optimization step.
    Extract frequently used values once.
    """
    candidate["_skill_count"] = len(candidate.get("skills", []))
    return candidate
