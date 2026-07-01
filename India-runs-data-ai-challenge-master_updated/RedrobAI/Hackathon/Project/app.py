#!/usr/bin/env python3
"""
app.py — FastAPI web application for local Candidate Ranking System.
Provides upload handlers, ranking calculation, and XLSX export.
Runs 100% offline.
"""

import os
import sys
import random
import threading
import time
import tempfile
from io import BytesIO
from typing import Optional

from fastapi import FastAPI, File, UploadFile, Request, BackgroundTasks
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from openpyxl import Workbook

import uvicorn

# Add current path to sys.path so scorer modules can be loaded properly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from document_parser import load_file_candidates
from rank import score_candidate
from scorer.reasoning_generator import generate_reasoning
from skill_matcher import extract_jd_skills, match_candidate_skills, get_detailed_match_data
from scorer.evaluation_metrics import generate_test_metrics
from scorer.ranking_system_metrics import DashboardMetricsGenerator, generate_test_ranking_metrics

# --- App Setup ---
app = FastAPI(title="Redrob AI — Candidate Ranking Dashboard")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- Global State ---
global_candidates = []
global_scored_results = []
global_dataset_honeypot_count = 0
global_dataset_valid_count = 0
global_dataset_honeypot_samples = []
scoring_in_progress = False
scoring_progress = 0
scoring_start_time = None
background_thread = None
BATCH_SIZE = 1000
scored_candidates_index = 0


def build_honeypot_xai_reasoning(result: dict) -> str:
    """Return a compact, audit-friendly explanation for a flagged candidate."""
    details = result.get("details", {})
    hp_details = details.get("honeypot", {})
    reasons = result.get("hp_reasons") or hp_details.get("reasons") or []
    hp_score = hp_details.get("score", 0)
    classification = hp_details.get("classification", "FAKE" if result.get("is_honeypot") else "REAL")
    penalty = hp_details.get("penalty", 1.0)
    base_score = details.get("base_score_before_honeypot_penalty", result.get("score", 0))
    final_score = result.get("score", 0)

    if reasons:
        signal_text = "; ".join(reasons)
    else:
        signal_text = "the honeypot score crossed the configured detection threshold"

    return (
        f"Classified as {classification} because {signal_text}. "
        f"The detector assigned red_flag_score {hp_score}; scores >= 2 are FAKE. "
        f"Applied penalty weight {penalty}, "
        f"and reduced the base score from {base_score} to {final_score:.10f} before ranking."
    )


def format_honeypot_result(result: dict, rank_idx: int) -> dict:
    hp_details = result["details"].get("honeypot", {})
    return {
        "rank": rank_idx,
        "candidate_id": result["candidate_id"],
        "name": result["name"],
        "current_title": result["current_title"],
        "location": result["location"],
        "yoe": result["yoe"],
        "score": f"{result['score']:.10f}",
        "score_raw": result["score"],
        "reasoning": build_honeypot_xai_reasoning(result),
        "xai_reasoning": build_honeypot_xai_reasoning(result),
        "details": result["details"],
        "is_honeypot": result["is_honeypot"],
        "honeypot_reasons": result["hp_reasons"],
        "honeypot_score": hp_details.get("score", 0),
        "honeypot_penalty": hp_details.get("penalty", 1.0),
        "base_score_before_honeypot_penalty": result["details"].get("base_score_before_honeypot_penalty"),
        "skills": result["raw_candidate"].get("skills", []),
    }


def format_dataset_honeypot_sample(candidate: dict, dataset_position: int) -> dict:
    final_score, details, is_honeypot, hp_reasons = score_candidate(candidate)
    profile = candidate.get("profile", {})
    result = {
        "candidate_id": candidate.get("candidate_id", "CAND_UNKNOWN"),
        "name": profile.get("anonymized_name", "Anonymous"),
        "current_title": profile.get("current_title", "N/A"),
        "location": f"{profile.get('location', 'N/A')}, {profile.get('country', 'N/A')}",
        "yoe": profile.get("years_of_experience", 0.0),
        "score": final_score,
        "is_honeypot": is_honeypot,
        "hp_reasons": hp_reasons,
        "details": details,
        "raw_candidate": candidate,
    }
    formatted = format_honeypot_result(result, dataset_position)
    formatted["sample_source"] = "dataset"
    formatted["dataset_position"] = dataset_position
    return formatted


def update_dataset_honeypot_stats() -> tuple[int, int]:
    """Calculate and persist dataset-level honeypot counts from all candidates."""
    global global_dataset_honeypot_count, global_dataset_valid_count, global_dataset_honeypot_samples
    from honeypot_detection.detector import is_honeypot

    honeypots = 0
    honeypot_candidates = []
    for idx, candidate in enumerate(global_candidates, start=1):
        if is_honeypot(candidate):
            honeypots += 1
            honeypot_candidates.append((idx, candidate))

    global_dataset_honeypot_count = honeypots
    global_dataset_valid_count = len(global_candidates) - honeypots
    sample_pairs = random.Random(42).sample(honeypot_candidates, min(5, len(honeypot_candidates)))
    global_dataset_honeypot_samples = [
        format_dataset_honeypot_sample(candidate, idx)
        for idx, candidate in sample_pairs
    ]
    return global_dataset_valid_count, global_dataset_honeypot_count


# --- Pydantic Models ---
class RankRequest(BaseModel):
    top_n: int = 100

class ExportRequest(BaseModel):
    top_n: int = 100

class MatchSkillsRequest(BaseModel):
    candidate_id: str


# --- Routes ---

@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = os.path.join(BASE_DIR, "templates", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.post("/api/upload")
async def upload_files(files: list[UploadFile] = File(...)):
    global global_candidates, global_scored_results, scoring_in_progress, background_thread, scored_candidates_index
    global global_dataset_honeypot_count, global_dataset_valid_count, global_dataset_honeypot_samples

    if not files:
        return JSONResponse({"error": "No files selected"}, status_code=400)

    # Reset state on new upload session
    global_candidates = []
    global_scored_results = []
    scoring_in_progress = False
    scored_candidates_index = 0
    global_dataset_honeypot_count = 0
    global_dataset_valid_count = 0
    global_dataset_honeypot_samples = []

    new_candidates_count = 0
    errors = []

    for file in files[:1]:
        if not file.filename:
            continue
        # Save temp file
        suffix = os.path.splitext(file.filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=UPLOAD_FOLDER) as tmp:
            tmp.write(await file.read())
            temp_path = tmp.name

        try:
            parsed = load_file_candidates(temp_path)
            global_candidates.extend(parsed)
            new_candidates_count += len(parsed)
        except Exception as e:
            errors.append(f"Failed to process {file.filename}: {str(e)}")
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    if not global_candidates and errors:
        return JSONResponse({
            "success": False,
            "error": "No candidates were loaded. Fix the upload file and try again.",
            "errors": errors,
            "total_candidates": 0,
            "total_valid_candidates": 0,
            "total_honeypots": 0,
        }, status_code=400)

    # Quick honeypot detection for full-dataset dashboard stats.
    total_valid, total_honeypots = update_dataset_honeypot_stats()

    # Start background scoring
    if global_candidates and not scoring_in_progress:
        scoring_in_progress = True
        background_thread = threading.Thread(target=run_scoring_background, daemon=True)
        background_thread.start()

    return {
        "success": True,
        "new_candidates_added": new_candidates_count,
        "total_candidates": len(global_candidates),
        "total_valid_candidates": total_valid,
        "total_honeypots": total_honeypots,
        "errors": errors
    }


def score_batch(start_idx, end_idx):
    """Score a batch of candidates and return scored results."""
    global global_candidates
    results = []

    for i in range(start_idx, min(end_idx, len(global_candidates))):
        candidate = global_candidates[i]
        cid = candidate.get("candidate_id", "CAND_UNKNOWN")
        profile = candidate.get("profile", {})

        final_score, details, is_honeypot, hp_reasons = score_candidate(candidate)

        results.append({
            "candidate_id": cid,
            "name": profile.get("anonymized_name", "Anonymous"),
            "current_title": profile.get("current_title", "N/A"),
            "location": f"{profile.get('location', 'N/A')}, {profile.get('country', 'N/A')}",
            "yoe": profile.get("years_of_experience", 0.0),
            "score": final_score,
            "is_honeypot": is_honeypot,
            "hp_reasons": hp_reasons,
            "details": details,
            "raw_candidate": candidate,
        })

    return results


def run_scoring_pipeline():
    """Run candidate scoring and sorting logic in memory."""
    global global_candidates, global_scored_results
    results = []

    for candidate in global_candidates:
        cid = candidate.get("candidate_id", "CAND_UNKNOWN")
        profile = candidate.get("profile", {})

        final_score, details, is_honeypot, hp_reasons = score_candidate(candidate)

        results.append({
            "candidate_id": cid,
            "name": profile.get("anonymized_name", "Anonymous"),
            "current_title": profile.get("current_title", "N/A"),
            "location": f"{profile.get('location', 'N/A')}, {profile.get('country', 'N/A')}",
            "yoe": profile.get("years_of_experience", 0.0),
            "score": final_score,
            "is_honeypot": is_honeypot,
            "hp_reasons": hp_reasons,
            "details": details,
            "raw_candidate": candidate
        })

    results.sort(key=lambda x: (-x["score"], x["candidate_id"]))
    global_scored_results = results


def run_scoring_background():
    """Background task to score candidates in batches without blocking the API."""
    global scoring_in_progress, scoring_start_time, global_scored_results, global_candidates, scored_candidates_index
    try:
        scoring_start_time = time.time()
        total_candidates = len(global_candidates)

        for batch_start in range(0, total_candidates, BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, total_candidates)
            batch_results = score_batch(batch_start, batch_end)
            global_scored_results.extend(batch_results)
            global_scored_results.sort(key=lambda x: (-x["score"], x["candidate_id"]))
            scored_candidates_index = batch_end

    finally:
        scoring_in_progress = False


@app.post("/api/rank")
async def get_rankings(payload: RankRequest):
    global global_scored_results, global_candidates, scoring_in_progress

    top_n = payload.top_n

    if not global_scored_results and global_candidates:
        run_scoring_pipeline()

    if not global_scored_results:
        dataset_valid_count = global_dataset_valid_count
        dataset_honeypot_count = global_dataset_honeypot_count
        if global_candidates and dataset_honeypot_count == 0 and dataset_valid_count == 0:
            dataset_valid_count, dataset_honeypot_count = update_dataset_honeypot_stats()
        return {
            "results": [],
            "total_candidates": len(global_candidates),
            "total_valid": dataset_valid_count,
            "total_valid_candidates": dataset_valid_count,
            "top_100_honeypots": [],
            "sample_honeypots": global_dataset_honeypot_samples,
            "total_honeypots": dataset_honeypot_count,
            "honeypots_in_top_100": 0,
        }

    top_n = min(top_n, len(global_scored_results))
    top_n_results = global_scored_results[:top_n]
    top_100_results = global_scored_results[:100]
    dataset_honeypot_count = global_dataset_honeypot_count
    dataset_valid_count = global_dataset_valid_count
    if global_candidates and dataset_honeypot_count == 0 and dataset_valid_count == 0:
        dataset_valid_count, dataset_honeypot_count = update_dataset_honeypot_stats()
    ranked_honeypots = [
        format_honeypot_result(r, rank_idx)
        for rank_idx, r in enumerate(global_scored_results, start=1)
        if r["is_honeypot"]
    ]
    top_100_honeypots = [r for r in ranked_honeypots if r["rank"] <= 100]
    sample_honeypots = global_dataset_honeypot_samples or ranked_honeypots[:5]

    formatted_results = []
    for rank_idx, r in enumerate(top_n_results, start=1):
        reasoning = generate_reasoning(r["raw_candidate"], rank_idx, r["score"], r["details"])
        reasoning = reasoning.replace("\n", " ").replace("\r", " ")

        formatted_results.append({
            "rank": rank_idx,
            "candidate_id": r["candidate_id"],
            "name": r["name"],
            "current_title": r["current_title"],
            "location": r["location"],
            "yoe": r["yoe"],
            "score": f"{r['score']:.10f}",
            "score_raw": r["score"],
            "reasoning": reasoning,
            "details": r["details"],
            "is_honeypot": r["is_honeypot"],
            "honeypot_reasons": r["hp_reasons"],
            "skills": r["raw_candidate"].get("skills", [])
        })

    if scoring_in_progress:
        validation_report = {"pending": True, "ranked_basis": "Ranked Top 100 candidates"}
    else:
        # Generate validation report from the ranked Top 100, independent of the
        # currently displayed/exported top_n list size.
        raw_top_candidates = [r["raw_candidate"] for r in top_100_results]
        try:
            from scorer.custom_report import generate_custom_report
            validation_report = generate_custom_report(raw_top_candidates, global_candidates)
        except Exception as e:
            print(f"Error generating validation report: {e}")
            validation_report = {"error": str(e)}

    return {
        "results": formatted_results,
        "total_candidates": len(global_candidates),
        "total_valid": dataset_valid_count,
        "total_valid_candidates": dataset_valid_count,
        "total_honeypots": dataset_honeypot_count,
        "honeypots_in_top_n": sum(1 for r in top_n_results if r["is_honeypot"]),
        "honeypots_in_top_100": len(top_100_honeypots),
        "top_100_honeypots": top_100_honeypots,
        "sample_honeypots": sample_honeypots,
        "top_n_configured": top_n,
        "validation_report": validation_report
    }


@app.get("/api/ranking-status")
async def ranking_status():
    """Get the current status of background scoring."""
    global scoring_in_progress, global_scored_results, global_candidates, scoring_start_time, scored_candidates_index

    status = {
        "is_scoring": scoring_in_progress,
        "results_ready": len(global_scored_results) > 0,
        "total_candidates": len(global_candidates),
        "candidates_scored": scored_candidates_index,
        "partial_results_count": len(global_scored_results),
        "elapsed_time": time.time() - scoring_start_time if scoring_start_time else 0
    }

    if scoring_in_progress and len(global_candidates) > 0:
        if scored_candidates_index > 0:
            elapsed = time.time() - scoring_start_time
            percent_done = scored_candidates_index / len(global_candidates)
            if percent_done > 0:
                estimated_total = elapsed / percent_done
                status["estimated_time_remaining"] = max(0, estimated_total - elapsed)
            else:
                status["estimated_time_remaining"] = 60
        else:
            status["estimated_time_remaining"] = 60
    else:
        status["estimated_time_remaining"] = 0

    return status


def build_rankings_xlsx(top_n_results: list[dict]) -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Rankings"
    worksheet.append(["candidate_id", "rank", "score", "reasoning"])

    for rank_idx, r in enumerate(top_n_results, start=1):
        reasoning = generate_reasoning(r["raw_candidate"], rank_idx, r["score"], r["details"])
        reasoning = reasoning.replace("\n", " ").replace("\r", " ")
        worksheet.append([r["candidate_id"], rank_idx, f"{r['score']:.10f}", reasoning])

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output.getvalue()


@app.post("/api/export")
async def export_xlsx(payload: ExportRequest):
    global global_scored_results, global_candidates

    top_n = payload.top_n

    if not global_scored_results and global_candidates:
        run_scoring_pipeline()

    top_n = min(top_n, len(global_scored_results))
    top_n_results = global_scored_results[:top_n]

    output = build_rankings_xlsx(top_n_results)

    return StreamingResponse(
        iter([output]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=submission.xlsx"}
    )


@app.post("/api/match-skills")
async def match_skills(payload: MatchSkillsRequest):
    """Match a candidate's skills with JD skills."""
    global global_candidates

    candidate = next((c for c in global_candidates if c.get("candidate_id") == payload.candidate_id), None)
    if not candidate:
        return JSONResponse({"error": "Candidate not found"}, status_code=404)

    candidate_skills = candidate.get("skills", [])
    jd_skills = extract_jd_skills()
    matched = match_candidate_skills(candidate_skills, jd_skills)
    return matched


@app.post("/api/match-skills-visualization")
async def match_skills_visualization(payload: MatchSkillsRequest):
    """Get detailed semantic match data for donut graph visualization."""
    global global_candidates

    candidate = next((c for c in global_candidates if c.get("candidate_id") == payload.candidate_id), None)
    if not candidate:
        return JSONResponse({"error": "Candidate not found"}, status_code=404)

    candidate_skills = candidate.get("skills", [])
    jd_skills = extract_jd_skills()
    detailed_data = get_detailed_match_data(candidate_skills, jd_skills)
    return detailed_data


@app.get("/api/jd-skills")
async def get_jd_skills():
    """Get all JD skills categorized."""
    jd_skills = extract_jd_skills()
    return jd_skills


@app.get("/api/honeypot-metrics")
async def honeypot_metrics():
    """Get evaluation metrics for honeypot detection model."""
    try:
        metrics = generate_test_metrics()
        all_metrics = metrics.calculate_metrics()
        formatted = metrics.get_formatted_metrics()
        dashboard = metrics.get_summary_dashboard()

        return {
            "status": "success",
            "model_version": "2.0 - Enhanced with 5 fixes",
            "metrics": formatted,
            "dashboard": dashboard,
            "raw_metrics": all_metrics,
            "description": {
                "accuracy": "Overall correctness of predictions",
                "precision": "Of honeypots detected, how many were actually honeypots",
                "recall": "Of actual honeypots, how many were detected",
                "f1_score": "Harmonic mean of precision and recall",
                "specificity": "Of valid candidates, how many were correctly identified",
                "sensitivity": "Of actual honeypots, how many were detected (same as recall)",
                "balanced_accuracy": "Average of sensitivity and specificity",
                "mcc": "Matthews Correlation Coefficient (-1 to 1, 1 is perfect)",
                "false_positive_rate": "Valid candidates incorrectly flagged as honeypots",
                "false_negative_rate": "Honeypots missed by the model",
                "roc_auc": "Area under ROC curve (0.5 to 1.0, 1.0 is perfect)",
            }
        }
    except Exception as e:
        return JSONResponse({"error": str(e), "status": "error"}, status_code=500)


@app.get("/api/honeypot-confusion-matrix")
async def honeypot_confusion_matrix():
    """Get confusion matrix data for visualization."""
    try:
        metrics = generate_test_metrics()
        cm = metrics.get_confusion_matrix_dict()

        return {
            "confusion_matrix": cm,
            "total": sum(cm.values()),
            "correct_predictions": cm["true_positives"] + cm["true_negatives"],
            "incorrect_predictions": cm["false_positives"] + cm["false_negatives"],
        }
    except Exception as e:
        return JSONResponse({"error": str(e), "status": "error"}, status_code=500)


@app.get("/api/model-info")
async def model_info():
    """Get active REAL/FAKE honeypot detector information."""
    return {
        "model_name": "Rule-Based REAL/FAKE Honeypot Classifier",
        "version": "Feature Flags v1",
        "status": "Active in upload and ranking pipeline",
        "last_update": "2026-06-28",
        "improvements": [
            "Extracts mandatory core and derived honeypot features",
            "Classifies candidates as FAKE when red_flag_score >= 2",
            "Returns explicit reasons for every triggered red flag",
        ],
        "detection_methods": 5,
        "classification_rule": "red_flag_score >= 2 => FAKE, otherwise REAL",
        "features": {
            "Core": [
                "years_of_experience",
                "num_skills",
                "num_expert_skills",
                "avg_skill_duration",
                "total_endorsements",
                "profile_completeness_score",
            ],
            "Derived flags": {
                "expert_skill_duration_gap": "Any expert skill has duration < 12 months",
                "skill_explosion_flag": "num_skills > 10 and years_of_experience < 3",
                "low_credibility_flag": "total_endorsements < 5 and num_expert_skills > 0",
                "weak_profile_flag": "profile_completeness_score < 50",
                "unrealistic_summary_flag": "Summary contains AGI, Quantum AI, mastered everything, or expert in all domains",
            },
        }
    }


@app.get("/api/system-metrics")
async def system_metrics():
    """Get comprehensive ranking system evaluation metrics."""
    try:
        if global_scored_results:
            metrics_data = DashboardMetricsGenerator.format_for_dashboard(global_scored_results)
        else:
            metrics_data = generate_test_ranking_metrics()

        return {
            "status": "success",
            "system": metrics_data["system_info"],
            "key_metrics": metrics_data["key_metrics"],
            "ranking_metrics": metrics_data["ranking_metrics"],
            "component_performance": metrics_data["component_performance"],
            "tier_distribution": metrics_data["tier_distribution"],
            "score_stats": metrics_data["score_stats"],
            "health": metrics_data["system_health"],
            "insights": metrics_data["insights"],
        }
    except Exception as e:
        return JSONResponse({"error": str(e), "status": "error"}, status_code=500)


@app.get("/api/system-metrics/components")
async def system_metrics_components():
    """Get detailed component performance breakdown."""
    try:
        if global_scored_results:
            metrics_data = DashboardMetricsGenerator.format_for_dashboard(global_scored_results)
        else:
            metrics_data = generate_test_ranking_metrics()

        return {
            "status": "success",
            "components": metrics_data["component_performance"],
            "descriptions": {
                "title_career": "Job title and career alignment with JD",
                "skills": "Technical skills match with required skills",
                "experience": "Years of experience and relevance",
                "location": "Geographic preference and match",
                "behavioral": "Engagement, responsiveness, and profile quality",
            }
        }
    except Exception as e:
        return JSONResponse({"error": str(e), "status": "error"}, status_code=500)


@app.get("/api/system-metrics/tier-analysis")
async def system_metrics_tier_analysis():
    """Get tier distribution and analysis."""
    try:
        if global_scored_results:
            metrics_data = DashboardMetricsGenerator.format_for_dashboard(global_scored_results)
        else:
            metrics_data = generate_test_ranking_metrics()

        return {
            "status": "success",
            "tiers": metrics_data["tier_distribution"],
            "total_candidates": metrics_data["key_metrics"]["valid_candidates"],
        }
    except Exception as e:
        return JSONResponse({"error": str(e), "status": "error"}, status_code=500)


@app.get("/api/system-metrics/ranking-quality")
async def system_metrics_ranking_quality():
    """Get ranking quality metrics (NDCG, MAP, MRR)."""
    try:
        if global_scored_results:
            metrics_data = DashboardMetricsGenerator.format_for_dashboard(global_scored_results)
        else:
            metrics_data = generate_test_ranking_metrics()

        return {
            "status": "success",
            "ranking_metrics": metrics_data["ranking_metrics"],
            "descriptions": {
                "ndcg_at_10": "Normalized Discounted Cumulative Gain at position 10",
                "ndcg_at_20": "Normalized Discounted Cumulative Gain at position 20",
                "map_at_10": "Mean Average Precision at position 10",
                "map_at_20": "Mean Average Precision at position 20",
                "mrr": "Mean Reciprocal Rank of first relevant candidate",
            },
            "interpretation": {
                "excellent": "> 0.80",
                "good": "0.60 - 0.80",
                "fair": "0.40 - 0.60",
                "poor": "< 0.40",
            }
        }
    except Exception as e:
        return JSONResponse({"error": str(e), "status": "error"}, status_code=500)


@app.post("/api/clear")
async def clear_all():
    global global_candidates, global_scored_results, scoring_in_progress, scoring_start_time, scored_candidates_index
    global global_dataset_honeypot_count, global_dataset_valid_count, global_dataset_honeypot_samples
    global_candidates = []
    global_scored_results = []
    scoring_in_progress = False
    scoring_start_time = None
    scored_candidates_index = 0
    global_dataset_honeypot_count = 0
    global_dataset_valid_count = 0
    global_dataset_honeypot_samples = []
    return {"success": True}


@app.get("/api/honeypot-cv-metrics")
async def honeypot_cv_metrics():
    """
    Run Stratified 5-Fold cross-validation on the currently uploaded candidates
    using the live honeypot penalty detector.

    Since the detector is deterministic and rule-based (no training step),
    the full-dataset predictions serve as pseudo ground-truth labels.
    Each fold re-runs the detector on held-out candidates and compares vs
    the full-dataset result, measuring detection consistency and stability.

    Returns per-fold metrics + aggregate stats.
    """
    global global_candidates, global_scored_results
    from honeypot_detection.detector import evaluate_candidate
    import statistics as _stats

    if not global_candidates:
        return JSONResponse({"error": "No candidates uploaded yet"}, status_code=400)

    candidates = global_candidates
    n = len(candidates)

    # ── Step 1: Run detector on full dataset → pseudo ground truth ──────────
    full_predictions = []
    for c in candidates:
        hp_score, is_hp, reasons = evaluate_candidate(c)
        full_predictions.append({
            "is_honeypot": is_hp,
            "score": hp_score,
            "reason_count": len(reasons),
            "reasons": reasons[:3],  # keep first 3 for display
        })

    y_true = [1 if p["is_honeypot"] else 0 for p in full_predictions]
    total_honeypots = sum(y_true)
    total_valid     = n - total_honeypots

    # ── Step 2: Stratified K-Fold (pure Python) ─────────────────────────────
    K = min(5, min(total_honeypots, total_valid))  # can't have more folds than smallest class
    if K < 2:
        return {
            "error_note": f"Too few honeypots ({total_honeypots}) or valid ({total_valid}) candidates for CV",
            "total": n,
            "honeypots": total_honeypots,
            "valid": total_valid,
            "honeypot_rate": round(total_honeypots / n * 100, 2),
            "fold_metrics": [],
            "overall": _compute_hp_metrics(y_true, y_true),
        }

    def _stratified_folds(labels, k, seed=42):
        class_idx = {}
        for i, lbl in enumerate(labels):
            class_idx.setdefault(lbl, []).append(i)
        def _shuffle(lst, s):
            a, c, m = 1664525, 1013904223, 2**32
            for i in range(len(lst) - 1, 0, -1):
                s = (a * s + c) % m
                j = s % (i + 1)
                lst[i], lst[j] = lst[j], lst[i]
            return lst
        shuffled = {cls: _shuffle(list(idxs), seed + hash(cls) % 1000)
                    for cls, idxs in class_idx.items()}
        folds_pc = {cls: [idxs[i::k] for i in range(k)]
                    for cls, idxs in shuffled.items()}
        folds = []
        for fi in range(k):
            test, train = [], []
            for cls, cf in folds_pc.items():
                test.extend(cf[fi])
                for j, f in enumerate(cf):
                    if j != fi:
                        train.extend(f)
            folds.append((train, test))
        return folds

    folds = _stratified_folds(y_true, K)

    # ── Step 3: Evaluate each fold ──────────────────────────────────────────
    fold_metrics_list = []
    for fi, (_, test_idx) in enumerate(folds, 1):
        fold_true = [y_true[i] for i in test_idx]
        fold_pred = []
        for i in test_idx:
            _, is_hp, _ = evaluate_candidate(candidates[i])
            fold_pred.append(1 if is_hp else 0)

        m = _compute_hp_metrics(fold_true, fold_pred)
        m["fold"] = fi
        m["test_size"] = len(test_idx)
        m["honeypots_in_fold"] = sum(fold_true)
        m["detected_in_fold"]  = sum(fold_pred)
        fold_metrics_list.append(m)

    # ── Step 4: Overall metrics ─────────────────────────────────────────────
    y_pred_all = [p["is_honeypot"] for p in full_predictions]
    overall = _compute_hp_metrics(y_true, [1 if p else 0 for p in y_pred_all])

    # ── Step 5: CV summary (mean ± std across folds) ────────────────────────
    def _cv_summary(key):
        vals = [m[key] for m in fold_metrics_list]
        return {
            "mean": round(_stats.mean(vals), 4),
            "std":  round(_stats.stdev(vals) if len(vals) > 1 else 0.0, 4),
            "min":  round(min(vals), 4),
            "max":  round(max(vals), 4),
        }

    cv_summary = {
        "accuracy":    _cv_summary("accuracy"),
        "precision":   _cv_summary("precision"),
        "recall":      _cv_summary("recall"),
        "f1_score":    _cv_summary("f1_score"),
        "specificity": _cv_summary("specificity"),
        "mcc":         _cv_summary("mcc"),
    }

    # ── Top flagged reasons across all honeypots ────────────────────────────
    reason_counter = {}
    for p in full_predictions:
        if p["is_honeypot"]:
            for r in p["reasons"]:
                key = r.split(":")[0].strip()  # first part of reason
                reason_counter[key] = reason_counter.get(key, 0) + 1

    top_reasons = sorted(reason_counter.items(), key=lambda x: -x[1])[:5]

    return {
        "total_candidates": n,
        "total_honeypots":  total_honeypots,
        "total_valid":      total_valid,
        "honeypot_rate":    round(total_honeypots / n * 100, 2),
        "k_folds":          K,
        "fold_metrics":     fold_metrics_list,
        "cv_summary":       cv_summary,
        "overall":          overall,
        "top_flag_reasons": [{"reason": r, "count": c} for r, c in top_reasons],
    }


def _compute_hp_metrics(y_true, y_pred):
    """Compute classification metrics for honeypot detection."""
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
    tn = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 0)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)
    total = tp + tn + fp + fn

    accuracy    = round((tp + tn) / total if total else 0, 4)
    precision   = round(tp / (tp + fp) if (tp + fp) else 0, 4)
    recall      = round(tp / (tp + fn) if (tp + fn) else 0, 4)
    specificity = round(tn / (tn + fp) if (tn + fp) else 0, 4)
    f1          = round(2 * precision * recall / (precision + recall)
                        if (precision + recall) else 0, 4)
    denom       = ((tp+fp)*(tp+fn)*(tn+fp)*(tn+fn)) ** 0.5
    mcc         = round((tp*tn - fp*fn) / denom if denom else 0, 4)
    fpr         = round(fp / (fp + tn) if (fp + tn) else 0, 4)
    fnr         = round(fn / (fn + tp) if (fn + tp) else 0, 4)

    return dict(
        tp=tp, tn=tn, fp=fp, fn=fn,
        accuracy=accuracy, precision=precision,
        recall=recall, specificity=specificity,
        f1_score=f1, mcc=mcc, fpr=fpr, fnr=fnr,
    )


if __name__ == "__main__":
    print("Starting Redrob Ranking Web Server (FastAPI) on http://127.0.0.1:5000")
    uvicorn.run(app, host="127.0.0.1", port=5000, reload=False)
