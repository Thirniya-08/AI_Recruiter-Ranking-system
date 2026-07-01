#!/usr/bin/env python3
"""
app_fastapi.py — FastAPI web application for local Candidate Ranking System.
Provides upload handlers, ranking calculation, and XLSX export.
Runs 100% offline. 3-5x faster than Flask.
"""

import os
import sys
import tempfile
import asyncio
import time
import random
from io import BytesIO
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openpyxl import Workbook
from typing import List, Optional, Dict, Any

# Add current path to sys.path so scorer modules can be loaded properly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from document_parser import load_file_candidates
from rank import score_candidate
from scorer.reasoning_generator import generate_reasoning
from skill_matcher import extract_jd_skills, match_candidate_skills, get_detailed_match_data
from jd_manager import jd_manager
from recruiter_preferences import preferences_manager, RecruiterPreferences
from unified_uploader import unified_uploader

app = FastAPI(
    title="Redrob Candidate Ranking System",
    description="Fast async candidate ranking system",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Global in-memory storage for uploaded candidates
global_candidates = []
global_scored_results = []
global_dataset_honeypot_count = 0
global_dataset_valid_count = 0
global_dataset_honeypot_samples = []
scoring_in_progress = False
scoring_progress = 0
scoring_start_time = None
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


# Request/Response Models
class RankRequest(BaseModel):
    top_n: int = 100


class MatchSkillsRequest(BaseModel):
    candidate_id: str


class ExportRequest(BaseModel):
    top_n: int = 100


class UploadResponse(BaseModel):
    success: bool
    new_candidates_added: int
    total_candidates: int
    total_valid_candidates: int
    total_honeypots: int
    errors: List[str] = []


@app.get("/")
async def index():
    """Serve the main HTML page."""
    with open(os.path.join(TEMPLATE_DIR, "index.html"), "r") as f:
        return {"html": f.read()}


@app.post("/api/upload", response_model=UploadResponse)
async def upload_files(files: List[UploadFile] = File(...), background_tasks: BackgroundTasks = None):
    """Upload and parse candidate files, start background scoring."""
    global global_candidates, global_scored_results, scoring_in_progress
    global global_dataset_honeypot_count, global_dataset_valid_count, global_dataset_honeypot_samples
    
    if not files:
        raise HTTPException(status_code=400, detail="No files selected")
    
    new_candidates_count = 0
    errors = []
    
    # Reset state on new upload session
    global_candidates = []
    global_scored_results = []
    scoring_in_progress = False
    global_dataset_honeypot_count = 0
    global_dataset_valid_count = 0
    global_dataset_honeypot_samples = []
    
    for file in files[:1]:
        if not file.filename:
            continue
        
        # Save uploaded file
        temp_path = os.path.join(UPLOAD_FOLDER, file.filename)
        try:
            contents = await file.read()
            with open(temp_path, "wb") as f:
                f.write(contents)
            
            # Parse candidates from this file
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
    
    # Run quick honeypot detection for full-dataset dashboard stats.
    total_valid, total_honeypots = update_dataset_honeypot_stats()
    
    # Start background scoring
    if global_candidates and not scoring_in_progress:
        scoring_in_progress = True
        background_tasks.add_task(run_scoring_background)
    
    return UploadResponse(
        success=True,
        new_candidates_added=new_candidates_count,
        total_candidates=len(global_candidates),
        total_valid_candidates=total_valid,
        total_honeypots=total_honeypots,
        errors=errors
    )


# ======================== UNIFIED UPLOAD ENDPOINT ========================

class UnifiedUploadResponse(BaseModel):
    success: bool
    job_title: Optional[str]
    company: Optional[str]
    experience_required: Optional[int]
    must_have_skills: int
    nice_to_have_skills: int
    preferred_skills: int
    total_candidates: int
    valid_candidates: int
    honeypots: int
    file_type: str
    message: str
    candidates_ranked: bool = False


@app.post("/api/unified-upload", response_model=UnifiedUploadResponse)
async def unified_upload(file: UploadFile = File(...), auto_rank: bool = True, background_tasks: BackgroundTasks = None):
    """
    Upload single file containing BOTH Job Description and Candidates.
    
    Supported formats:
    - ZIP file with JD + candidate files
    - JSON with {job_description, candidates} structure
    - Excel with JD sheet + candidate sheet(s)
    
    auto_rank: If true, automatically ranks candidates after upload
    """
    global global_candidates, global_scored_results, scoring_in_progress, jd_manager
    global global_dataset_honeypot_count, global_dataset_valid_count, global_dataset_honeypot_samples
    
    try:
        # Save uploaded file temporarily
        temp_path = os.path.join(UPLOAD_FOLDER, file.filename)
        contents = await file.read()
        with open(temp_path, "wb") as f:
            f.write(contents)
        
        # Parse combined file
        parse_result = unified_uploader.parse_combined_file(temp_path)
        
        if not parse_result['success']:
            raise HTTPException(status_code=400, detail=parse_result.get('error', 'Failed to parse file'))
        
        # Extract JD and candidates
        jd_text = parse_result['jd_text']
        candidates_raw = parse_result['candidates']
        file_type = parse_result['file_type']
        
        # Load JD into manager
        jd_info = jd_manager.load_jd(jd_text, file_type)
        jd_summary = jd_manager.get_jd_summary()
        
        # Reset candidates state
        global_candidates = []
        global_scored_results = []
        global_dataset_honeypot_count = 0
        global_dataset_valid_count = 0
        global_dataset_honeypot_samples = []
        scoring_in_progress = False
        
        # Process candidates
        # If candidates are already in the right format, use them
        # Otherwise try to convert them
        total_candidates = 0
        errors = []
        
        for i, candidate in enumerate(candidates_raw):
            try:
                # If candidate already has required fields, use as-is
                if isinstance(candidate, dict) and 'profile' in candidate and 'skills' in candidate:
                    global_candidates.append(candidate)
                    total_candidates += 1
                # Otherwise, try to standardize the format
                elif isinstance(candidate, dict):
                    standardized = _standardize_candidate(candidate)
                    global_candidates.append(standardized)
                    total_candidates += 1
                else:
                    errors.append(f"Candidate {i} is not a valid dictionary")
            except Exception as e:
                errors.append(f"Error processing candidate {i}: {str(e)}")
        
        # Detect honeypots for full-dataset dashboard stats.
        total_valid, total_honeypots = update_dataset_honeypot_stats()
        
        # Auto-rank if requested
        candidates_ranked = False
        if auto_rank and global_candidates:
            scoring_in_progress = True
            background_tasks.add_task(run_scoring_background)
            candidates_ranked = True
        
        # Clean up
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        return UnifiedUploadResponse(
            success=True,
            job_title=jd_summary.get('job_title', 'Not specified'),
            company=jd_summary.get('company', 'Not specified'),
            experience_required=jd_summary.get('experience_required', None),
            must_have_skills=jd_summary['must_have_skills'],
            nice_to_have_skills=jd_summary['nice_to_have_skills'],
            preferred_skills=jd_summary['preferred_skills'],
            total_candidates=total_candidates,
            valid_candidates=total_valid,
            honeypots=total_honeypots,
            file_type=file_type,
            message=f"Unified upload successful! Loaded JD and {total_candidates} candidates",
            candidates_ranked=candidates_ranked
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process unified file: {str(e)}")


def _standardize_candidate(candidate: Dict) -> Dict:
    """
    Convert candidate data to standard format if not already in it.
    """
    if 'profile' in candidate and 'skills' in candidate:
        return candidate
    
    # Try to build standard format from available fields
    standardized = {
        'candidate_id': candidate.get('id') or candidate.get('candidate_id') or 'CAND_UNKNOWN',
        'profile': {
            'anonymized_name': candidate.get('name') or candidate.get('full_name') or 'Anonymous',
            'current_title': candidate.get('title') or candidate.get('current_title') or 'N/A',
            'location': candidate.get('location') or candidate.get('city') or 'N/A',
            'country': candidate.get('country') or 'N/A',
            'years_of_experience': candidate.get('experience') or candidate.get('yoe') or 0,
        },
        'skills': candidate.get('skills') or []
    }
    
    return standardized


@app.get("/api/unified-upload/formats")
async def get_supported_formats():
    """Get information about supported unified upload formats."""
    return JSONResponse({
        "supported_formats": [
            {
                "format": "ZIP",
                "extension": ".zip",
                "description": "ZIP archive containing JD file (PDF/DOCX/TXT/JSON) and candidate files (JSONL/JSON/CSV)",
                "example": "archive.zip with jd.pdf and candidates.jsonl"
            },
            {
                "format": "JSON",
                "extension": ".json",
                "description": "JSON object with 'job_description' and 'candidates' keys",
                "example": {
                    "job_description": "Senior Engineer role...",
                    "candidates": [{"name": "...", "skills": [...]}, ...]
                }
            },
            {
                "format": "Excel",
                "extension": ".xlsx or .xls",
                "description": "Excel workbook with JD in first sheet, candidates in subsequent sheets",
                "example": "Sheet1: JD data, Sheet2: Candidates with headers"
            }
        ],
        "notes": [
            "JD files are auto-detected from ZIP archives",
            "Candidate data can be in multiple formats (JSONL, JSON, CSV)",
            "Automatic ranking can be enabled with ?auto_rank=true parameter",
            "System automatically converts candidate formats to standard schema"
        ]
    })


def score_batch(start_idx: int, end_idx: int) -> List[Dict[str, Any]]:
    """Score a batch of candidates and return scored results."""
    global global_candidates
    results = []
    
    for i in range(start_idx, min(end_idx, len(global_candidates))):
        candidate = global_candidates[i]
        cid = candidate.get("candidate_id", "CAND_UNKNOWN")
        profile = candidate.get("profile", {})
        
        # Calculate scores
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


async def run_scoring_background():
    """Background task to score candidates in batches."""
    global scoring_in_progress, scoring_start_time, global_scored_results, global_candidates, scored_candidates_index
    try:
        scoring_start_time = time.time()
        total_candidates = len(global_candidates)
        
        for batch_start in range(0, total_candidates, BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, total_candidates)
            
            # Score this batch
            batch_results = score_batch(batch_start, batch_end)
            global_scored_results.extend(batch_results)
            
            # Sort by penalized score; honeypot candidates remain visible but pushed down.
            global_scored_results.sort(key=lambda x: (-x["score"], x["candidate_id"]))
            scored_candidates_index = batch_end
            
            # Yield to event loop
            await asyncio.sleep(0)
    finally:
        scoring_in_progress = False


def run_scoring_pipeline():
    """Run candidate scoring synchronously (fallback)."""
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


@app.post("/api/rank")
async def get_rankings(request: RankRequest):
    """Get ranked candidates."""
    global global_scored_results, global_candidates
    
    if not global_scored_results and global_candidates:
        run_scoring_pipeline()
    
    if not global_scored_results:
        dataset_valid_count = global_dataset_valid_count
        dataset_honeypot_count = global_dataset_honeypot_count
        if global_candidates and dataset_honeypot_count == 0 and dataset_valid_count == 0:
            dataset_valid_count, dataset_honeypot_count = update_dataset_honeypot_stats()
        return JSONResponse({
            "results": [],
            "total_candidates": len(global_candidates),
            "total_valid": dataset_valid_count,
            "total_valid_candidates": dataset_valid_count,
            "top_100_honeypots": [],
            "sample_honeypots": global_dataset_honeypot_samples,
            "total_honeypots": dataset_honeypot_count,
            "honeypots_in_top_100": 0,
            "top_n_configured": request.top_n
        })
    
    top_n = min(request.top_n, len(global_scored_results))
    top_n_results = global_scored_results[:top_n]
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
            "score_raw": r['score'],
            "reasoning": reasoning,
            "details": r["details"],
            "is_honeypot": r["is_honeypot"],
            "honeypot_reasons": r["hp_reasons"],
            "skills": r["raw_candidate"].get("skills", [])
        })
    
    return JSONResponse({
        "results": formatted_results,
        "total_candidates": len(global_candidates),
        "total_valid": dataset_valid_count,
        "total_valid_candidates": dataset_valid_count,
        "total_honeypots": dataset_honeypot_count,
        "honeypots_in_top_n": sum(1 for r in top_n_results if r["is_honeypot"]),
        "honeypots_in_top_100": len(top_100_honeypots),
        "top_100_honeypots": top_100_honeypots,
        "sample_honeypots": sample_honeypots,
        "top_n_configured": top_n
    })


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
    
    # Estimate time remaining
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
    
    return JSONResponse(status)


def build_rankings_xlsx(top_n_results: List[Dict[str, Any]]) -> bytes:
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
async def export_xlsx(request: ExportRequest):
    """Export rankings to XLSX file."""
    global global_scored_results, global_candidates
    
    if not global_scored_results and global_candidates:
        run_scoring_pipeline()
    
    top_n = min(request.top_n, len(global_scored_results))
    top_n_results = global_scored_results[:top_n]
    
    output = build_rankings_xlsx(top_n_results)
    
    # Save to temp file
    temp_xlsx = tempfile.NamedTemporaryFile(mode="w+b", delete=False, suffix=".xlsx")
    try:
        temp_xlsx.write(output)
        temp_xlsx.close()
        return FileResponse(
            temp_xlsx.name,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename="submission.xlsx"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export XLSX: {str(e)}")


@app.post("/api/match-skills")
async def match_skills(request: MatchSkillsRequest):
    """Match a candidate's skills with JD skills."""
    global global_candidates
    
    candidate = next((c for c in global_candidates if c.get("candidate_id") == request.candidate_id), None)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    candidate_skills = candidate.get("skills", [])
    jd_skills = extract_jd_skills()
    matched = match_candidate_skills(candidate_skills, jd_skills)
    
    return JSONResponse(matched)


@app.post("/api/match-skills-visualization")
async def match_skills_visualization(request: MatchSkillsRequest):
    """Get detailed semantic match data for donut graph visualization."""
    global global_candidates
    
    candidate = next((c for c in global_candidates if c.get("candidate_id") == request.candidate_id), None)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    candidate_skills = candidate.get("skills", [])
    jd_skills = extract_jd_skills()
    detailed_data = get_detailed_match_data(candidate_skills, jd_skills)
    
    return JSONResponse(detailed_data)


@app.get("/api/jd-skills")
async def get_jd_skills():
    """Get all JD skills categorized."""
    jd_skills = extract_jd_skills()
    return JSONResponse(jd_skills)


@app.post("/api/clear")
async def clear_all():
    """Clear all data."""
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
    return JSONResponse({"success": True})


@app.get("/api/honeypot-cv-metrics")
async def honeypot_cv_metrics():
    """
    Return stratified k-fold metrics for the same honeypot detector used during
    upload and ranking.

    If uploaded records contain labels, those labels are used as ground truth.
    Supported label fields:
      - label: "fake"/"honeypot"/"valid"/"real"
      - is_honeypot: bool
      - expected_honeypot: bool

    Candidate uploads usually do not include labels, so the endpoint falls back
    to detector-generated pseudo labels. In that mode the metrics describe fold
    stability/consistency for the exact detections used by the ranking penalty.
    """
    global global_candidates
    from honeypot_detection.detector import evaluate_candidate
    import statistics as _stats

    if not global_candidates:
        return JSONResponse({"error": "No candidates uploaded yet"}, status_code=400)

    candidates = global_candidates
    n = len(candidates)

    detection_results = []
    for candidate in candidates:
        hp_score, is_hp, reasons = evaluate_candidate(candidate)
        detection_results.append({
            "is_honeypot": bool(is_hp),
            "score": hp_score,
            "reasons": reasons,
        })

    labelled = [
        _candidate_truth_label(candidate)
        for candidate, result in zip(candidates, detection_results)
    ]
    labeled_indices = [i for i, (_, has_label) in enumerate(labelled) if has_label]
    has_ground_truth = len(labeled_indices) > 0
    eval_indices = labeled_indices if has_ground_truth else list(range(n))
    y_true = [
        labelled[i][0] if has_ground_truth else (1 if detection_results[i]["is_honeypot"] else 0)
        for i in eval_indices
    ]
    y_pred_eval = [1 if detection_results[i]["is_honeypot"] else 0 for i in eval_indices]
    y_pred_all = [1 if result["is_honeypot"] else 0 for result in detection_results]
    total_honeypots = sum(y_pred_all)
    total_valid = n - total_honeypots
    true_honeypots = sum(y_true)
    true_valid = len(y_true) - true_honeypots

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

        shuffled = {
            cls: _shuffle(list(idxs), seed + (17 if cls else 0))
            for cls, idxs in class_idx.items()
        }
        folds_per_class = {
            cls: [idxs[i::k] for i in range(k)]
            for cls, idxs in shuffled.items()
        }

        folds = []
        for fi in range(k):
            test = []
            train = []
            for cls_folds in folds_per_class.values():
                test.extend(cls_folds[fi])
                for j, fold in enumerate(cls_folds):
                    if j != fi:
                        train.extend(fold)
            folds.append((train, test))
        return folds

    smallest_class = min(true_honeypots, true_valid)
    k_folds = min(5, smallest_class)
    overall = _compute_hp_metrics(y_true, y_pred_eval)

    if k_folds < 2:
        return JSONResponse({
            "error_note": (
                f"Too few samples in one class for stratified CV "
                f"(honeypot={true_honeypots}, valid={true_valid})"
            ),
            "label_source": "uploaded_labels" if has_ground_truth else "detector_pseudo_labels",
            "label_note": _label_note(has_ground_truth, len(labeled_indices), n),
            "total_candidates": n,
            "total_honeypots": total_honeypots,
            "total_valid": total_valid,
            "evaluated_samples": len(eval_indices),
            "true_honeypots": true_honeypots,
            "true_valid": true_valid,
            "honeypot_rate": round(total_honeypots / n * 100, 2),
            "k_folds": k_folds,
            "fold_metrics": [],
            "cv_summary": {},
            "overall": overall,
            "top_flag_reasons": _top_honeypot_reasons(detection_results),
        })

    folds = _stratified_folds(y_true, k_folds)
    fold_metrics = []
    for fold_number, (_, test_idxs) in enumerate(folds, 1):
        fold_true = [y_true[i] for i in test_idxs]
        fold_pred = [y_pred_eval[i] for i in test_idxs]

        metrics = _compute_hp_metrics(fold_true, fold_pred)
        metrics["fold"] = fold_number
        metrics["test_size"] = len(test_idxs)
        metrics["honeypots_in_fold"] = sum(fold_true)
        metrics["detected_in_fold"] = sum(fold_pred)
        fold_metrics.append(metrics)

    def _cv_summary(key):
        vals = [m[key] for m in fold_metrics]
        return {
            "mean": round(_stats.mean(vals), 4),
            "std": round(_stats.stdev(vals) if len(vals) > 1 else 0.0, 4),
            "min": round(min(vals), 4),
            "max": round(max(vals), 4),
        }

    cv_summary = {
        "accuracy": _cv_summary("accuracy"),
        "precision": _cv_summary("precision"),
        "recall": _cv_summary("recall"),
        "f1_score": _cv_summary("f1_score"),
        "specificity": _cv_summary("specificity"),
        "mcc": _cv_summary("mcc"),
    }

    return JSONResponse({
        "label_source": "uploaded_labels" if has_ground_truth else "detector_pseudo_labels",
        "label_note": _label_note(has_ground_truth, len(labeled_indices), n),
        "total_candidates": n,
        "total_honeypots": total_honeypots,
        "total_valid": total_valid,
        "evaluated_samples": len(eval_indices),
        "true_honeypots": true_honeypots,
        "true_valid": true_valid,
        "honeypot_rate": round(total_honeypots / n * 100, 2),
        "k_folds": k_folds,
        "fold_metrics": fold_metrics,
        "cv_summary": cv_summary,
        "overall": overall,
        "top_flag_reasons": _top_honeypot_reasons(detection_results),
    })


def _compute_hp_metrics(y_true, y_pred):
    """Compute binary classification metrics for honeypot detection."""
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
    tn = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 0)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)
    total = tp + tn + fp + fn

    accuracy = (tp + tn) / total if total else 0
    precision = tp / (tp + fp) if (tp + fp) else 0
    recall = tp / (tp + fn) if (tp + fn) else 0
    specificity = tn / (tn + fp) if (tn + fp) else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0
    denom = ((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn)) ** 0.5
    mcc = (tp * tn - fp * fn) / denom if denom else 0
    fpr = fp / (fp + tn) if (fp + tn) else 0
    fnr = fn / (fn + tp) if (fn + tp) else 0

    return {
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "specificity": round(specificity, 4),
        "f1_score": round(f1, 4),
        "balanced_accuracy": round((recall + specificity) / 2, 4),
        "mcc": round(mcc, 4),
        "fpr": round(fpr, 4),
        "fnr": round(fnr, 4),
    }


def _top_honeypot_reasons(detection_results):
    """Return the most common detector rules behind dropped candidates."""
    reason_counts = {}
    for result in detection_results:
        if not result["is_honeypot"]:
            continue
        for reason in result["reasons"][:3]:
            key = reason.split(":")[0].strip()
            reason_counts[key] = reason_counts.get(key, 0) + 1

    return [
        {"reason": reason, "count": count}
        for reason, count in sorted(reason_counts.items(), key=lambda item: -item[1])[:5]
    ]


@app.get("/api/honeypot-metrics")
async def honeypot_metrics():
    """Return modal metrics for uploaded candidates vs truth labels when present."""
    evaluation = _evaluate_uploaded_honeypot_detection()
    raw = evaluation["overall"]

    return JSONResponse({
        "status": "success",
        "model_version": "Stage 1 Rules",
        "label_source": evaluation["label_source"],
        "label_note": evaluation["label_note"],
        "metrics": _format_hp_metrics(raw, evaluation),
        "raw_metrics": raw,
        "dashboard": {
            "performance": {
                "accuracy": f"{raw['accuracy']:.1%}",
                "precision": f"{raw['precision']:.1%}",
                "recall": f"{raw['recall']:.1%}",
                "f1_score": f"{raw['f1_score']:.3f}",
            },
            "confusion_matrix": {
                "TP": raw["tp"],
                "TN": raw["tn"],
                "FP": raw["fp"],
                "FN": raw["fn"],
            },
            "sample_count": evaluation["evaluated_samples"],
        },
        "description": {
            "accuracy": "Overall correctness against uploaded truth labels",
            "precision": "Of candidates dropped as honeypots, how many were truly honeypots",
            "recall": "Of true honeypots, how many were dropped",
            "specificity": "Of true valid candidates, how many were kept",
            "false_positive_rate": "Truth-valid candidates incorrectly dropped",
            "false_negative_rate": "Truth-honeypots missed by the detector",
        }
    })


@app.get("/api/honeypot-confusion-matrix")
async def honeypot_confusion_matrix():
    """Return confusion matrix for the model metrics modal."""
    evaluation = _evaluate_uploaded_honeypot_detection()
    raw = evaluation["overall"]
    cm = {
        "true_positives": raw["tp"],
        "true_negatives": raw["tn"],
        "false_positives": raw["fp"],
        "false_negatives": raw["fn"],
    }

    return JSONResponse({
        "confusion_matrix": cm,
        "total": sum(cm.values()),
        "correct_predictions": cm["true_positives"] + cm["true_negatives"],
        "incorrect_predictions": cm["false_positives"] + cm["false_negatives"],
        "label_source": evaluation["label_source"],
        "label_note": evaluation["label_note"],
    })


@app.get("/api/model-info")
async def model_info():
    """Return the active REAL/FAKE honeypot detector rule set."""
    return JSONResponse({
        "model_name": "Rule-Based REAL/FAKE Honeypot Classifier",
        "version": "Feature Flags v1",
        "status": "Active in FastAPI upload and ranking pipeline",
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
    })


def _evaluate_uploaded_honeypot_detection():
    """Evaluate current uploaded candidates against truth labels when present."""
    from honeypot_detection.detector import evaluate_candidate

    candidates = global_candidates
    detection_results = []
    labels = []
    for candidate in candidates:
        hp_score, is_hp, reasons = evaluate_candidate(candidate)
        detection_results.append({
            "is_honeypot": bool(is_hp),
            "score": hp_score,
            "reasons": reasons,
        })
        labels.append(_candidate_truth_label(candidate))

    labeled_indices = [i for i, (_, has_label) in enumerate(labels) if has_label]
    has_ground_truth = len(labeled_indices) > 0
    eval_indices = labeled_indices if has_ground_truth else list(range(len(candidates)))
    y_true = [
        labels[i][0] if has_ground_truth else (1 if detection_results[i]["is_honeypot"] else 0)
        for i in eval_indices
    ]
    y_pred = [1 if detection_results[i]["is_honeypot"] else 0 for i in eval_indices]
    y_pred_all = [1 if result["is_honeypot"] else 0 for result in detection_results]

    return {
        "total_candidates": len(candidates),
        "evaluated_samples": len(eval_indices),
        "total_honeypots": sum(y_pred_all),
        "total_valid": len(candidates) - sum(y_pred_all),
        "true_honeypots": sum(y_true),
        "true_valid": len(y_true) - sum(y_true),
        "label_source": "uploaded_labels" if has_ground_truth else "detector_pseudo_labels",
        "label_note": _label_note(has_ground_truth, len(labeled_indices), len(candidates)),
        "overall": _compute_hp_metrics(y_true, y_pred),
        "top_flag_reasons": _top_honeypot_reasons(detection_results),
    }


def _candidate_truth_label(candidate):
    """Return (label, has_label), where 1 means honeypot and 0 means valid."""
    label_fields = ("truth_label", "ground_truth", "label", "expected_label")
    for field in label_fields:
        if field not in candidate:
            continue
        raw_label = candidate.get(field)
        if isinstance(raw_label, str):
            label = raw_label.strip().lower()
            if label in {"fake", "honeypot", "hp", "fraud", "invalid", "1", "true"}:
                return 1, True
            if label in {"real", "valid", "genuine", "not_honeypot", "0", "false"}:
                return 0, True
        elif raw_label is not None:
            return 1 if bool(raw_label) else 0, True

    bool_fields = ("is_honeypot", "expected_honeypot", "honeypot")
    for field in bool_fields:
        if field in candidate:
            return 1 if bool(candidate.get(field)) else 0, True

    return 0, False


def _label_note(has_ground_truth, labeled_count, total_count):
    if total_count == 0:
        return "No uploaded candidates available for honeypot evaluation."
    if has_ground_truth and labeled_count == total_count:
        return "Metrics are computed against truth labels in the uploaded dataset."
    if has_ground_truth:
        return (
            f"Metrics are computed against truth labels for {labeled_count} "
            f"of {total_count} uploaded candidates."
        )
    return (
        "No truth labels were found in the uploaded dataset. Counts show the "
        "Stage 1 detector output; accuracy-style metrics are detector consistency only."
    )


def _format_hp_metrics(raw, evaluation):
    """Return strings expected by static/metrics.js."""
    total = evaluation["total_candidates"]
    detected = evaluation["total_honeypots"]
    evaluated = evaluation["evaluated_samples"]
    true_honeypots = evaluation["true_honeypots"]

    return {
        "accuracy": f"{raw['accuracy']:.2%}",
        "precision": f"{raw['precision']:.2%}",
        "recall": f"{raw['recall']:.2%}",
        "f1_score": f"{raw['f1_score']:.2%}",
        "specificity": f"{raw['specificity']:.2%}",
        "sensitivity": f"{raw['recall']:.2%}",
        "balanced_accuracy": f"{raw['balanced_accuracy']:.2%}",
        "mcc": f"{raw['mcc']:.4f}",
        "false_positive_rate": f"{raw['fpr']:.2%}",
        "false_negative_rate": f"{raw['fnr']:.2%}",
        "roc_auc": "N/A",
        "total_samples": str(evaluated),
        "honeypot_rate": f"{(true_honeypots / evaluated):.2%}" if evaluated else "0.00%",
        "detection_rate": f"{(detected / total):.2%}" if total else "0.00%",
    }


# ======================== JOB DESCRIPTION ENDPOINTS ========================

class JDUploadResponse(BaseModel):
    success: bool
    job_title: Optional[str]
    company: Optional[str]
    experience_required: Optional[int]
    must_have_skills: int
    nice_to_have_skills: int
    preferred_skills: int
    file_type: str
    message: str


@app.post("/api/jd/upload", response_model=JDUploadResponse)
async def upload_jd(file: UploadFile = File(...)):
    """
    Upload and parse Job Description file.
    Supports: PDF, DOCX, TXT, JSON, CSV
    """
    try:
        # Save temporarily
        temp_path = os.path.join(UPLOAD_FOLDER, file.filename)
        contents = await file.read()
        with open(temp_path, "wb") as f:
            f.write(contents)
        
        # Parse JD
        jd_text, file_type = jd_manager.parse_jd_file(temp_path)
        jd_info = jd_manager.load_jd(jd_text, file_type)
        summary = jd_manager.get_jd_summary()
        
        # Clean up
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        return JDUploadResponse(
            success=True,
            job_title=summary['job_title'],
            company=summary['company'],
            experience_required=summary['experience_required'],
            must_have_skills=summary['must_have_skills'],
            nice_to_have_skills=summary['nice_to_have_skills'],
            preferred_skills=summary['preferred_skills'],
            file_type=file_type,
            message=f"JD loaded successfully from {file_type} file"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse JD: {str(e)}")


@app.get("/api/jd/summary")
async def get_jd_summary():
    """Get current JD summary and extracted skills."""
    if not jd_manager.current_jd:
        raise HTTPException(status_code=404, detail="No JD loaded")
    
    summary = jd_manager.get_jd_summary()
    return JSONResponse(summary)


@app.post("/api/jd/clear")
async def clear_jd():
    """Clear current JD."""
    jd_manager.clear_jd()
    return JSONResponse({"success": True, "message": "JD cleared"})


# ======================== RECRUITER PREFERENCES ENDPOINTS ========================

@app.post("/api/preferences/set")
async def set_preferences(prefs: RecruiterPreferences):
    """Set recruiter ranking preferences."""
    try:
        result = preferences_manager.set_preferences(prefs.dict())
        return JSONResponse({
            "success": True,
            "message": "Preferences updated",
            "preferences": result.dict()
        })
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid preferences: {str(e)}")


@app.get("/api/preferences/get")
async def get_preferences():
    """Get current preferences."""
    prefs = preferences_manager.get_preferences()
    return JSONResponse(prefs.dict())


@app.post("/api/preferences/strategy/{strategy}")
async def apply_strategy(strategy: str):
    """
    Apply a preset ranking strategy.
    Options: balanced, skill_focused, experience_focused, title_focused, quick_hire, elite
    """
    result = preferences_manager.apply_ranking_strategy(strategy)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return JSONResponse(result)


@app.get("/api/preferences/strategies")
async def get_available_strategies():
    """Get available ranking strategies and recommendations."""
    if not jd_manager.current_jd:
        strategies = ["balanced", "skill_focused", "experience_focused", "title_focused", "quick_hire", "elite"]
        return JSONResponse({
            "available_strategies": strategies,
            "recommendations": []
        })
    
    recommendations = preferences_manager.get_strategy_recommendations(jd_manager.jd_metadata)
    return JSONResponse({
        "available_strategies": ["balanced", "skill_focused", "experience_focused", "title_focused", "quick_hire", "elite"],
        "recommendations": recommendations
    })


@app.post("/api/preferences/reset")
async def reset_preferences():
    """Reset preferences to defaults."""
    prefs = preferences_manager.reset_to_defaults()
    return JSONResponse({
        "success": True,
        "message": "Preferences reset to defaults",
        "preferences": prefs.dict()
    })


# ======================== ENHANCED RANKING WITH JD ========================

@app.post("/api/rank-with-jd")
async def get_rankings_with_jd(request: RankRequest):
    """
    Get ranked candidates using uploaded JD and recruiter preferences.
    Uses dynamic skill matching and weighted scoring.
    """
    global global_scored_results, global_candidates
    
    if not jd_manager.current_jd:
        raise HTTPException(status_code=400, detail="No JD loaded. Please upload a Job Description first.")
    
    if not global_scored_results and global_candidates:
        run_scoring_pipeline()
    
    if not global_scored_results:
        return JSONResponse({
            "results": [],
            "total_candidates": 0,
            "total_valid": 0,
            "top_n_configured": request.top_n,
            "jd_info": jd_manager.get_jd_summary()
        })
    
    # Apply preferences and filters
    filtered_results = []
    for r in global_scored_results:
        passes_filter, filter_messages = preferences_manager.apply_filters(
            r["raw_candidate"],
            jd_manager.jd_skills
        )
        
        if passes_filter:
            filtered_results.append(r)
    
    # Sort by score
    filtered_results.sort(key=lambda x: (-x["score"], x["candidate_id"]))
    
    top_n = min(request.top_n, len(filtered_results))
    top_n_results = filtered_results[:top_n]
    
    formatted_results = []
    for rank_idx, r in enumerate(top_n_results, start=1):
        reasoning = generate_reasoning(r["raw_candidate"], rank_idx, r["score"], r["details"])
        reasoning = reasoning.replace("\n", " ").replace("\r", " ")
        
        candidate_skills = r["raw_candidate"].get("skills", [])
        skill_match = match_candidate_skills(candidate_skills, jd_manager.jd_skills)
        
        formatted_results.append({
            "rank": rank_idx,
            "candidate_id": r["candidate_id"],
            "name": r["name"],
            "current_title": r["current_title"],
            "location": r["location"],
            "yoe": r["yoe"],
            "score": f"{r['score']:.10f}",
            "score_raw": r['score'],
            "reasoning": reasoning,
            "details": r["details"],
            "skills": candidate_skills,
            "jd_skill_match": skill_match
        })
    
    return JSONResponse({
        "results": formatted_results,
        "total_candidates": len(global_candidates),
        "total_valid": len(filtered_results),
        "top_n_configured": top_n,
        "jd_info": jd_manager.get_jd_summary(),
        "preferences_applied": preferences_manager.get_preferences().dict()
    })


@app.post("/api/candidate-match-score")
async def get_candidate_match_score(request: MatchSkillsRequest):
    """
    Get detailed match score for a candidate against current JD.
    """
    global global_candidates
    
    if not jd_manager.current_jd:
        raise HTTPException(status_code=400, detail="No JD loaded")
    
    candidate = next((c for c in global_candidates if c.get("candidate_id") == request.candidate_id), None)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    candidate_skills = candidate.get("skills", [])
    skill_match = match_candidate_skills(candidate_skills, jd_manager.jd_skills)
    
    # Calculate match percentages
    must_have_matched = sum(1 for s in skill_match.get("must_have_matched", []))
    must_have_total = len(jd_manager.jd_skills["must_have"])
    must_have_percentage = (must_have_matched / must_have_total * 100) if must_have_total > 0 else 0
    
    nice_to_have_matched = sum(1 for s in skill_match.get("nice_to_have_matched", []))
    nice_to_have_total = len(jd_manager.jd_skills["nice_to_have"])
    nice_to_have_percentage = (nice_to_have_matched / nice_to_have_total * 100) if nice_to_have_total > 0 else 0
    
    preferred_matched = sum(1 for s in skill_match.get("preferred_matched", []))
    preferred_total = len(jd_manager.jd_skills["preferred"])
    preferred_percentage = (preferred_matched / preferred_total * 100) if preferred_total > 0 else 0
    
    # Calculate overall match
    overall_match = (
        (must_have_percentage * 0.6) +
        (nice_to_have_percentage * 0.3) +
        (preferred_percentage * 0.1)
    )
    
    return JSONResponse({
        "candidate_id": request.candidate_id,
        "candidate_name": candidate.get("profile", {}).get("anonymized_name", "Unknown"),
        "must_have_match": {
            "matched": must_have_matched,
            "total": must_have_total,
            "percentage": must_have_percentage
        },
        "nice_to_have_match": {
            "matched": nice_to_have_matched,
            "total": nice_to_have_total,
            "percentage": nice_to_have_percentage
        },
        "preferred_match": {
            "matched": preferred_matched,
            "total": preferred_total,
            "percentage": preferred_percentage
        },
        "overall_match_percentage": overall_match,
        "detailed_skills": skill_match
    })


@app.post("/api/candidates/filter-by-jd")
async def filter_candidates_by_jd(request: RankRequest):
    """
    Filter candidates based on current JD and preferences.
    Returns candidates that meet minimum criteria.
    """
    global global_scored_results, global_candidates
    
    if not jd_manager.current_jd:
        raise HTTPException(status_code=400, detail="No JD loaded")
    
    if not global_scored_results and global_candidates:
        run_scoring_pipeline()
    
    prefs = preferences_manager.get_preferences()
    
    # Filter candidates
    filtered = []
    for r in global_scored_results:
        passes_filter, filter_messages = preferences_manager.apply_filters(
            r["raw_candidate"],
            jd_manager.jd_skills
        )
        
        if passes_filter:
            # Check minimum score
            if r["score"] >= prefs.minimum_overall_score:
                filtered.append({
                    "candidate_id": r["candidate_id"],
                    "name": r["name"],
                    "title": r["current_title"],
                    "location": r["location"],
                    "yoe": r["yoe"],
                    "score": r["score"],
                    "filter_notes": []
                })
        else:
            # Track why they were filtered out
            filtered.append({
                "candidate_id": r["candidate_id"],
                "name": r["name"],
                "title": r["current_title"],
                "location": r["location"],
                "yoe": r["yoe"],
                "score": r["score"],
                "filtered_out": True,
                "filter_reasons": filter_messages
            })
    
    # Sort by score
    filtered.sort(key=lambda x: (-x["score"], x["candidate_id"]))
    
    qualified = [c for c in filtered if not c.get("filtered_out", False)]
    filtered_out = [c for c in filtered if c.get("filtered_out", False)]
    
    return JSONResponse({
        "total_candidates": len(global_candidates),
        "qualified_candidates": len(qualified),
        "filtered_out_candidates": len(filtered_out),
        "qualified": qualified[:request.top_n],
        "filtered_out": filtered_out[:50],
        "criteria": {
            "minimum_experience": prefs.minimum_experience,
            "minimum_skill_match": prefs.minimum_skill_match,
            "minimum_overall_score": prefs.minimum_overall_score,
            "exclude_honeypots": prefs.exclude_honeypots
        }
    })


if __name__ == "__main__":
    import uvicorn
    print("Starting Redrob Ranking Web Server on http://127.0.0.1:8000")
    print("API Docs available at http://127.0.0.1:8000/docs")
    uvicorn.run(app, host="127.0.0.1", port=8000)
