"""
skill_matcher.py - JD skill categorization and semantic candidate matching.
"""

import os
import re
import math
from collections import Counter
from typing import List, Dict, Set


JD_SKILL_CONCEPTS = {
    "must_have": [
        {
            "label": "Production embeddings retrieval",
            "description": "deployed semantic search retrieval using embeddings, dense vectors, sentence transformers, bge e5 openai embeddings, index refresh, drift, retrieval quality regression",
        },
        {
            "label": "Vector or hybrid search infrastructure",
            "description": "operating vector databases and hybrid search infrastructure with pinecone weaviate qdrant milvus opensearch elasticsearch faiss bm25 indexes at production scale",
        },
        {
            "label": "Strong Python engineering",
            "description": "strong python software engineering code quality production backend systems services data pipelines maintainable implementation",
        },
        {
            "label": "Ranking evaluation frameworks",
            "description": "ranking system evaluation ndcg mrr map offline benchmark online correlation relevance metrics search quality measurement evaluation framework",
        },
        {
            "label": "A/B testing and online evaluation",
            "description": "ab testing online experiments recruiter feedback loops engagement metrics experiment interpretation production model evaluation",
        },
    ],
    "nice_to_have": [
        {
            "label": "LLM fine-tuning",
            "description": "large language model fine tuning adaptation lora qlora peft instruction tuning model customization transformers",
        },
        {
            "label": "Learning-to-rank models",
            "description": "learning to rank relevance optimization xgboost neural ranking reranking recommendation ranking model training",
        },
        {
            "label": "HR-tech or marketplace products",
            "description": "hr tech recruiting talent marketplace platform candidate matching recruiter workflow job marketplace product experience",
        },
        {
            "label": "Distributed systems or inference optimization",
            "description": "distributed systems large scale inference optimization latency throughput serving architecture scalable ml systems",
        },
        {
            "label": "AI/ML open-source contributions",
            "description": "open source ai machine learning contributions github libraries research code public projects community validation",
        },
    ],
}

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
    "have", "in", "is", "it", "of", "on", "or", "the", "to", "with", "you",
    "your", "using", "used", "built", "worked", "experience", "skills",
}

SEMANTIC_EXPANSIONS = {
    "ab": ["experiment", "online", "testing"],
    "bm25": ["lexical", "retrieval", "search", "ranking"],
    "elasticsearch": ["search", "retrieval", "index", "hybrid", "infrastructure"],
    "faiss": ["vector", "retrieval", "index", "semantic", "search"],
    "lora": ["fine", "tuning", "parameter", "efficient", "language", "model"],
    "map": ["ranking", "evaluation", "relevance", "metric"],
    "milvus": ["vector", "database", "retrieval", "infrastructure"],
    "mrr": ["ranking", "evaluation", "relevance", "metric"],
    "ndcg": ["ranking", "evaluation", "relevance", "metric"],
    "opensearch": ["search", "retrieval", "index", "hybrid", "infrastructure"],
    "peft": ["fine", "tuning", "parameter", "efficient", "language", "model"],
    "pinecone": ["vector", "database", "retrieval", "infrastructure"],
    "qdrant": ["vector", "database", "retrieval", "infrastructure"],
    "qlora": ["fine", "tuning", "parameter", "efficient", "language", "model"],
    "weaviate": ["vector", "database", "retrieval", "infrastructure"],
    "xgboost": ["learning", "rank", "ranking", "model"],
}

def extract_jd_skills() -> Dict[str, List[str]]:
    """
    Extract skills from the Job Description.
    Returns only the two JD categories requested by the role: must-have and nice-to-have.
    """

    # Keep this path available for future custom-JD parsing; current concepts are
    # derived from the checked-in JD and intentionally grouped semantically.
    current_dir = os.path.dirname(os.path.abspath(__file__))
    jd_file = os.path.join(current_dir, "job_description_extracted.txt")

    return {
        "must_have": [skill["label"] for skill in JD_SKILL_CONCEPTS["must_have"]],
        "nice_to_have": [skill["label"] for skill in JD_SKILL_CONCEPTS["nice_to_have"]],
    }


def normalize_skill(skill: str) -> str:
    """Normalize skill name for comparison (lowercase, remove special chars)."""
    return re.sub(r'[^\w\s-]', '', skill.lower().strip())


def _tokens(text: str) -> List[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if len(token) > 1 and token not in STOPWORDS
    ]


def _char_ngrams(text: str, size: int = 4) -> List[str]:
    compact = re.sub(r"[^a-z0-9]+", "", text.lower())
    if len(compact) <= size:
        return [compact] if compact else []
    return [compact[i:i + size] for i in range(len(compact) - size + 1)]


def _semantic_vector(text: str) -> Counter:
    vector = Counter()
    for token in _tokens(text):
        vector[f"tok:{token}"] += 1.0
        for expanded in SEMANTIC_EXPANSIONS.get(token, []):
            vector[f"tok:{expanded}"] += 0.75
    for gram in _char_ngrams(text):
        vector[f"chr:{gram}"] += 0.35
    return vector


def _cosine_similarity(left: Counter, right: Counter) -> float:
    if not left or not right:
        return 0.0
    shared = set(left) & set(right)
    dot = sum(left[key] * right[key] for key in shared)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def _candidate_skill_text(skill) -> str:
    if isinstance(skill, dict):
        pieces = [
            str(skill.get("name", "")),
            str(skill.get("proficiency", "")),
        ]
        duration = skill.get("duration_months")
        if duration:
            pieces.append(f"{duration} months")
        return " ".join(piece for piece in pieces if piece)
    return str(skill)


def _candidate_skill_name(skill) -> str:
    if isinstance(skill, dict):
        return str(skill.get("name", "")).strip()
    return str(skill).strip()


def _semantic_matches(candidate_skills: List, threshold: float = 0.18) -> Dict[str, List[Dict]]:
    candidate_entries = []
    for skill in candidate_skills or []:
        name = _candidate_skill_name(skill)
        if not name:
            continue
        text = _candidate_skill_text(skill)
        candidate_entries.append({
            "name": name,
            "vector": _semantic_vector(text),
        })

    results = {"must_have": [], "nice_to_have": []}
    for category, concepts in JD_SKILL_CONCEPTS.items():
        for concept in concepts:
            concept_text = f"{concept['label']} {concept['description']}"
            concept_vector = _semantic_vector(concept_text)
            best = {"candidate_skill": None, "score": 0.0}
            for entry in candidate_entries:
                score = _cosine_similarity(entry["vector"], concept_vector)
                if score > best["score"]:
                    best = {"candidate_skill": entry["name"], "score": score}

            results[category].append({
                "skill": concept["label"],
                "matched": best["score"] >= threshold,
                "candidate_skill": best["candidate_skill"],
                "semantic_score": round(best["score"], 3),
            })
    return results


def match_candidate_skills(candidate_skills: List, jd_skills: Dict[str, List[str]]) -> Dict:
    """
    Match candidate skills with JD skills using local semantic similarity.
    
    Args:
        candidate_skills: List of skills from candidate profile
        jd_skills: Dictionary with 'must_have' and 'nice_to_have'
    
    Returns:
        Dictionary with matched skills categorized
    """
    
    semantic_results = _semantic_matches(candidate_skills)
    matched_must_have = [item["skill"] for item in semantic_results["must_have"] if item["matched"]]
    matched_nice_to_have = [item["skill"] for item in semantic_results["nice_to_have"] if item["matched"]]

    total_matched = len(matched_must_have) + len(matched_nice_to_have)
    total_jd_skills = len(jd_skills["must_have"]) + len(jd_skills["nice_to_have"])
    match_percentage = (total_matched / total_jd_skills * 100) if total_jd_skills > 0 else 0
    
    return {
        "matched_must_have": matched_must_have,
        "matched_nice_to_have": matched_nice_to_have,
        "matched_technologies": [],
        "total_matched": total_matched,
        "match_percentage": round(match_percentage, 2),
        "jd_coverage": {
            "must_have": f"{len(matched_must_have)}/{len(jd_skills['must_have'])}",
            "nice_to_have": f"{len(matched_nice_to_have)}/{len(jd_skills['nice_to_have'])}",
        },
        "semantic_matches": semantic_results,
    }


def get_all_jd_skills_flat() -> Set[str]:
    """Get all JD skills as a flat, normalized set for quick lookup."""
    jd_skills = extract_jd_skills()
    all_skills = set()
    
    for skill in jd_skills["must_have"] + jd_skills["nice_to_have"]:
        all_skills.add(normalize_skill(skill))
    
    return all_skills


def get_detailed_match_data(candidate_skills: List, jd_skills: Dict[str, List[str]]) -> Dict:
    """
    Get detailed semantic matching data for a two-category donut visualization.
    """
    semantic_results = _semantic_matches(candidate_skills)
    categories = {}
    total_matched = 0
    total_skills = 0

    for category, items in semantic_results.items():
        matched = [item for item in items if item["matched"]]
        unmatched = [item for item in items if not item["matched"]]
        total_matched += len(matched)
        total_skills += len(items)
        categories[category] = {
            "label": "Must-have skills" if category == "must_have" else "Nice-to-have skills",
            "matched": matched,
            "unmatched": unmatched,
            "matched_count": len(matched),
            "total": len(items),
            "coverage": round((len(matched) / len(items) * 100), 1) if items else 0.0,
        }

    return {
        "chart_type": "donut",
        "matching_method": "local_semantic_similarity",
        "categories": categories,
        "total_matched": total_matched,
        "total_skills": total_skills,
        "overall_coverage": round((total_matched / total_skills * 100), 1) if total_skills else 0.0,
    }
