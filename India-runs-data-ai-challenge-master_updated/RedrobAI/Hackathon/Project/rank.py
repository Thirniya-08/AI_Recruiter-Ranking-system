#!/usr/bin/env python3
"""
rank.py — Main ranking pipeline for the Redrob Hackathon.

Usage:
    python rank.py --candidates ./candidates.jsonl --out ./submission.csv

Produces a CSV with the top 100 candidates ranked best-fit first for the
Senior AI Engineer job description.

Designed to run within:
  - 5 minutes wall-clock
  - 16 GB RAM
  - CPU only, no network
"""

import argparse
import csv
import gzip
import json
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from scorer.config import (
    W_TITLE_CAREER, W_SKILLS, W_EXPERIENCE, W_LOCATION, W_BEHAVIORAL,
)
from honeypot_detection.detector import analyze_candidate, evaluate_candidate
from honeypot_detection.penalty import apply_penalty, get_penalty
from scorer.title_career_scorer import score_title_career
from scorer.skills_scorer import score_skills
from scorer.experience_scorer import score_experience
from scorer.location_scorer import score_location
from scorer.behavioral_scorer import score_behavioral
from scorer.reasoning_generator import generate_reasoning


def build_honeypot_xai_reasoning(candidate_id: str, score: float, details: dict) -> str:
    """Build a concise explanation for Top 100 honeypot reporting."""
    hp_details = details.get("honeypot", {})
    reasons = hp_details.get("reasons") or []
    hp_score = hp_details.get("score", 0)
    classification = hp_details.get("classification", "FAKE")
    penalty = hp_details.get("penalty", 1.0)
    base_score = details.get("base_score_before_honeypot_penalty", score)
    signal_text = "; ".join(reasons) if reasons else "the honeypot score crossed the configured detection threshold"

    return (
        f"{candidate_id}: classified as {classification} because {signal_text}. "
        f"red_flag_score {hp_score}; scores >= 2 are FAKE. Penalty weight {penalty}, "
        f"base score {base_score} -> final score {score:.10f}."
    )


def load_candidates(path: str):
    """
    Stream candidates from JSONL (plain or gzipped).
    Yields one candidate dict at a time to keep memory low.
    """
    p = Path(path)
    
    if p.suffix == ".gz":
        opener = gzip.open
    elif p.suffix == ".jsonl":
        opener = open
    elif p.suffix == ".json":
        # sample_candidates.json is a JSON array, not JSONL
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            yield from data
            return
        else:
            yield data
            return
    else:
        opener = open
    
    with opener(p, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def score_candidate(candidate: dict) -> tuple[float, dict, bool, list[str]]:
    """
    Score a single candidate.
    Returns (final_score, details_dict, is_honeypot, honeypot_reasons).
    """
    # Step 1: Score all ranking dimensions
    tc_score, tc_details = score_title_career(candidate)
    sk_score, sk_details = score_skills(candidate)
    ex_score, ex_details = score_experience(candidate)
    lo_score, lo_details = score_location(candidate)
    be_score, be_details = score_behavioral(candidate)
    
    # Step 2: Combine with weights
    composite = (
        W_TITLE_CAREER * tc_score
        + W_SKILLS * sk_score
        + W_EXPERIENCE * ex_score
        + W_LOCATION * lo_score
        + W_BEHAVIORAL * be_score
    )
    
    # Step 3: Apply behavioral modifier (multiplicative)
    modifier = be_details.get("modifier", 1.0)
    base_final = composite * modifier

    # Step 4: Apply modular honeypot penalty. Suspicious candidates are pushed
    # down instead of being removed outright.
    hp_score, is_honeypot, hp_reasons = evaluate_candidate(candidate)
    hp_analysis = analyze_candidate(candidate)
    hp_penalty = get_penalty(hp_score)
    final = apply_penalty(base_final, hp_score)
    
    # Clamp to [0, 1]
    final = max(0.0, min(final, 1.0))
    
    details = {
        "title_career": tc_details,
        "skills": sk_details,
        "experience": ex_details,
        "location": lo_details,
        "behavioral": be_details,
        "component_scores": {
            "title_career": tc_score,
            "skills": sk_score,
            "experience": ex_score,
            "location": lo_score,
            "behavioral": be_score,
        },
        "composite_before_modifier": round(composite, 6),
        "modifier": round(modifier, 4),
        "base_score_before_honeypot_penalty": round(base_final, 10),
        "honeypot": {
            "score": hp_score,
            "red_flag_score": hp_score,
            "classification": hp_analysis["classification"],
            "is_honeypot": is_honeypot,
            "penalty": hp_penalty,
            "reasons": hp_reasons,
            "features": hp_analysis["features"],
            "flags": hp_analysis["flags"],
        },
    }
    
    return round(final, 10), details, is_honeypot, hp_reasons


def main():
    parser = argparse.ArgumentParser(
        description="Rank candidates for the Senior AI Engineer JD."
    )
    parser.add_argument(
        "--candidates", required=True,
        help="Path to candidates.jsonl (or .jsonl.gz or .json)"
    )
    parser.add_argument(
        "--out", required=True,
        help="Output CSV path"
    )
    parser.add_argument(
        "--top-n", type=int, default=100,
        help="Number of candidates to include in output (default: 100)"
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Print progress and stats"
    )
    args = parser.parse_args()
    
    start_time = time.time()
    
    if args.verbose:
        print(f"Loading and scoring candidates from: {args.candidates}")
    
    # -----------------------------------------------------------------------
    # Phase 1: Score all candidates (streaming — low memory)
    # -----------------------------------------------------------------------
    scored = []  # list of (score, candidate_id, candidate, details)
    honeypot_count = 0
    total_count = 0
    
    for candidate in load_candidates(args.candidates):
        total_count += 1
        cid = candidate.get("candidate_id", "")
        
        final_score, details, is_honeypot, hp_reasons = score_candidate(candidate)
        
        if is_honeypot:
            honeypot_count += 1
        
        scored.append((final_score, cid, candidate, details))
        
        if args.verbose and total_count % 10000 == 0:
            elapsed = time.time() - start_time
            print(f"  Processed {total_count:,} candidates in {elapsed:.1f}s")
    
    elapsed = time.time() - start_time
    if args.verbose:
        print(f"\nScored {len(scored):,} candidates ({honeypot_count} honeypots penalized)")
        print(f"Scoring phase: {elapsed:.1f}s")
    
    # -----------------------------------------------------------------------
    # Phase 2: Sort and pick top N
    # -----------------------------------------------------------------------
    # Sort by score descending, then candidate_id ascending for tiebreak
    scored.sort(key=lambda x: (-x[0], x[1]))
    top_n = scored[:args.top_n]
    top_100 = scored[:100]
    top_100_honeypots = [
        (rank_idx, score, cid, candidate, details)
        for rank_idx, (score, cid, candidate, details) in enumerate(top_100, start=1)
        if details.get("honeypot", {}).get("is_honeypot")
    ]
    
    if args.verbose:
        print(f"\nTop {args.top_n} score range: {top_n[0][0]:.4f} - {top_n[-1][0]:.4f}")
        print(f"Honeypots in full dataset: {honeypot_count}")
        print(f"Honeypots in Top 100: {len(top_100_honeypots)}")
        if top_100_honeypots:
            print("\n--- Top 100 Honeypot Explainable AI ---")
            for rank_idx, score, cid, candidate, details in top_100_honeypots:
                print(f"  Rank {rank_idx:>3}: {build_honeypot_xai_reasoning(cid, score, details)}")
    
    # -----------------------------------------------------------------------
    # Phase 3: Generate reasoning for top N
    # -----------------------------------------------------------------------
    rows = []
    for rank_idx, (score, cid, candidate, details) in enumerate(top_n, start=1):
        reasoning = generate_reasoning(candidate, rank_idx, score, details)
        
        # Escape reasoning for CSV (the csv module handles this, but let's
        # make sure there are no bare newlines)
        reasoning = reasoning.replace("\n", " ").replace("\r", " ")
        
        rows.append({
            "candidate_id": cid,
            "rank": rank_idx,
            "score": f"{score:.4f}",
            "reasoning": reasoning,
        })
    
    # -----------------------------------------------------------------------
    # Phase 4: Write CSV
    # -----------------------------------------------------------------------
    out_path = Path(args.out)
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["candidate_id", "rank", "score", "reasoning"],
            quoting=csv.QUOTE_MINIMAL,
        )
        writer.writeheader()
        writer.writerows(rows)
    
    total_time = time.time() - start_time
    
    if args.verbose:
        print(f"\nWrote {len(rows)} rows to {out_path}")
        print(f"Total time: {total_time:.1f}s")
        print(f"\n--- Top 10 ---")
        for row in rows[:10]:
            print(f"  Rank {row['rank']:>3}: {row['candidate_id']}  "
                  f"score={row['score']}  {row['reasoning'][:80]}...")
    
    print(f"\n[SUCCESS] Done. {len(rows)} candidates ranked in {total_time:.1f}s -> {out_path}")


if __name__ == "__main__":
    main()
