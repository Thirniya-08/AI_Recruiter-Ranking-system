import json
import os
import statistics


def _normalise_candidate_container(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("candidates", "sample_candidates", "data", "records"):
            value = data.get(key)
            if isinstance(value, list):
                return value
        return [data]
    return []


def _load_reference_candidates():
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    hackathon_dir = os.path.dirname(project_dir)
    sample_path = os.path.join(hackathon_dir, "ProjectObjective", "sample_candidates.json")

    try:
        if not os.path.exists(sample_path) or os.path.getsize(sample_path) == 0:
            return [], sample_path
        with open(sample_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        candidates = _normalise_candidate_container(data)
        return candidates, sample_path
    except Exception as e:
        print("Failed to load reference sample_candidates for report:", sample_path, e)

    return [], "reference_sample_candidates_missing"


def generate_custom_report(top_candidates, reference_candidates=None):
    # `reference_candidates` is intentionally ignored. The reference column must
    # always represent ProjectObjective/sample_candidates.json, never uploads.
    sample_candidates, reference_source = _load_reference_candidates()

    def get_stats(candidates):
        yoes = []
        skills_counts = []
        rrrs = []
        
        for c in candidates:
            profile = c.get("profile", {})
            yoe = profile.get("years_of_experience")
            if yoe is not None:
                yoes.append(float(yoe))
                
            skills = c.get("skills")
            if skills is not None:
                skills_counts.append(len(skills))
                
            signals = c.get("redrob_signals", {})
            rrr = signals.get("recruiter_response_rate")
            if rrr is not None:
                rrrs.append(float(rrr))
                
        stats = {
            "yoe": {
                "mean": statistics.mean(yoes) if yoes else 0,
                "median": statistics.median(yoes) if yoes else 0,
                "min": min(yoes) if yoes else 0,
                "max": max(yoes) if yoes else 0,
                "count": len(yoes),
            },
            "skills": {
                "mean": statistics.mean(skills_counts) if skills_counts else 0,
                "median": statistics.median(skills_counts) if skills_counts else 0,
                "min": min(skills_counts) if skills_counts else 0,
                "max": max(skills_counts) if skills_counts else 0,
                "count": len(skills_counts),
            },
            "rrr": {
                "mean": statistics.mean(rrrs) if rrrs else 0,
                "median": statistics.median(rrrs) if rrrs else 0,
                "min": min(rrrs) if rrrs else 0,
                "max": max(rrrs) if rrrs else 0,
                "count": len(rrrs),
            }
        }
        stats["has_data"] = any(
            stats[key]["count"] > 0
            for key in ("yoe", "skills", "rrr")
        )
        return stats

    sample_stats = get_stats(sample_candidates)
    top_stats = get_stats(top_candidates)

    return {
        "reference": sample_stats,
        "top": top_stats,
        "ranked_basis": "Ranked Top 100 candidates",
        "reference_source": reference_source,
        "reference_file": "ProjectObjective/sample_candidates.json",
        "reference_count": len(sample_candidates),
        "reference_has_data": sample_stats["has_data"],
        "ranked_count": len(top_candidates),
    }
