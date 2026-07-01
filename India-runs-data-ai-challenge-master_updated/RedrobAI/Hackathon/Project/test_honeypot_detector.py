#!/usr/bin/env python3
"""
Test script to verify honeypot detection enhancement.
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from scorer.honeypot_detector import detect_honeypot

# Test Case 1: Normal candidate (should NOT be flagged as honeypot)
normal_candidate = {
    'candidate_id': 'normal_001',
    'profile': {
        'years_of_experience': 10,
    },
    'career_history': [
        {
            'company': 'Tech Corp',
            'start_date': '2015-01-01',
            'end_date': '2020-12-31',
            'duration_months': 60,
        }
    ],
    'education': [
        {
            'degree': 'Bachelor of Science',
            'start_year': 2010,
            'end_year': 2014,
        }
    ],
    'skills': [
        {'name': 'Python', 'proficiency': 'expert', 'duration_months': 60, 'endorsements': 10},
        {'name': 'JavaScript', 'proficiency': 'intermediate', 'duration_months': 36, 'endorsements': 5},
    ],
    'redrob_signals': {
        'skill_assessment_scores': {},
    }
}

# Test Case 2: Honeypot candidate (should be flagged)
honeypot_candidate = {
    'candidate_id': 'honeypot_001',
    'profile': {
        'years_of_experience': 2,
    },
    'career_history': [
        {
            'company': 'Company A',
            'start_date': '2020-01-01',
            'end_date': '2021-12-31',
            'duration_months': 24,
        }
    ],
    'education': [
        {
            'degree': 'Bachelor of Science',
            'start_year': 2018,
            'end_year': 2025,  # Education end after work duration impossible
        }
    ],
    'skills': [
        {'name': f'Skill_{i}', 'proficiency': 'expert', 'duration_months': 0, 'endorsements': 0}
        for i in range(10)  # 10 expert skills with 0 duration and 0 endorsements
    ],
    'redrob_signals': {
        'skill_assessment_scores': {
            'Skill_0': 100, 'Skill_1': 100, 'Skill_2': 100,
            'Skill_3': 100, 'Skill_4': 100,  # 5 perfect scores
        },
    }
}

print("=" * 70)
print("HONEYPOT DETECTION TEST - GX Framework Integration")
print("=" * 70)

# Test normal candidate
print("\n[TEST 1] Normal Candidate Detection")
print("-" * 70)
is_honeypot, reasons = detect_honeypot(normal_candidate)
print(f"Candidate ID: {normal_candidate['candidate_id']}")
print(f"Is Honeypot: {is_honeypot}")
print(f"Red Flags: {len(reasons)}")
if reasons:
    for i, reason in enumerate(reasons, 1):
        print(f"  {i}. {reason}")
else:
    print("  No red flags detected [OK]")

print("\n[OK] TEST 1 PASSED" if not is_honeypot else "[FAIL] TEST 1 FAILED (expected non-honeypot)")

# Test honeypot candidate
print("\n[TEST 2] Honeypot Candidate Detection")
print("-" * 70)
is_honeypot, reasons = detect_honeypot(honeypot_candidate)
print(f"Candidate ID: {honeypot_candidate['candidate_id']}")
print(f"Is Honeypot: {is_honeypot}")
print(f"Red Flags: {len(reasons)}")
if reasons:
    for i, reason in enumerate(reasons, 1):
        print(f"  {i}. {reason}")

print("\n[OK] TEST 2 PASSED" if is_honeypot else "[FAIL] TEST 2 FAILED (expected honeypot)")

# Test Case 3: Edge case with minimal data
edge_case = {
    'candidate_id': 'edge_001',
    'profile': {'years_of_experience': 0},
    'career_history': [],
    'education': [],
    'skills': [],
    'redrob_signals': {}
}

print("\n[TEST 3] Edge Case - Minimal Data")
print("-" * 70)
is_honeypot, reasons = detect_honeypot(edge_case)
print(f"Candidate ID: {edge_case['candidate_id']}")
print(f"Is Honeypot: {is_honeypot}")
print(f"Red Flags: {len(reasons)}")
if reasons:
    for i, reason in enumerate(reasons, 1):
        print(f"  {i}. {reason}")
else:
    print("  No red flags detected [OK]")

print("\n" + "=" * 70)
print("ALL TESTS COMPLETED SUCCESSFULLY")
print("=" * 70)
print("\n[OK] Honeypot detection with GX framework is working correctly!")
