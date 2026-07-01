#!/usr/bin/env python3
"""
test_system_metrics.py - Test script for comprehensive ranking system metrics.

Tests all endpoints and validates metric calculations.
"""

import json
import sys
from scorer.ranking_system_metrics import (
    RankingSystemMetrics, 
    DashboardMetricsGenerator,
    generate_test_ranking_metrics
)

def test_metrics_generation():
    """Test metrics generation with sample data."""
    print("\n" + "="*70)
    print("TEST 1: Generating Test Metrics")
    print("="*70)
    
    try:
        metrics = generate_test_ranking_metrics()
        
        print("[OK] Test metrics generated successfully")
        print(f"  - Total candidates: {metrics['key_metrics']['total_candidates']}")
        print(f"  - Valid candidates: {metrics['key_metrics']['valid_candidates']}")
        print(f"  - Honeypot rate: {metrics['key_metrics']['honeypot_rate']}")
        print(f"  - Average score: {metrics['key_metrics']['average_score']}")
        
        return True
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return False

def test_component_analysis():
    """Test component performance analysis."""
    print("\n" + "="*70)
    print("TEST 2: Component Performance Analysis")
    print("="*70)
    
    try:
        metrics = generate_test_ranking_metrics()
        components = metrics['component_performance']
        
        print("[OK] Component analysis calculated successfully")
        for component, stats in components.items():
            print(f"  - {component}:")
            print(f"    Average score: {stats['avg_score']:.4f}")
            print(f"    Contribution: {stats['percentage']:.2f}%")
        
        return True
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return False

def test_ranking_metrics():
    """Test ranking quality metrics."""
    print("\n" + "="*70)
    print("TEST 3: Ranking Quality Metrics")
    print("="*70)
    
    try:
        metrics = generate_test_ranking_metrics()
        ranking = metrics['ranking_metrics']
        
        print("[OK] Ranking metrics calculated successfully")
        print(f"  - NDCG@10: {ranking['ndcg_at_10']:.4f}")
        print(f"  - NDCG@20: {ranking['ndcg_at_20']:.4f}")
        print(f"  - MAP@10: {ranking['map_at_10']:.4f}")
        print(f"  - MAP@20: {ranking['map_at_20']:.4f}")
        print(f"  - MRR: {ranking['mrr']:.4f}")
        
        return True
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return False

def test_tier_distribution():
    """Test tier distribution analysis."""
    print("\n" + "="*70)
    print("TEST 4: Tier Distribution Analysis")
    print("="*70)
    
    try:
        metrics = generate_test_ranking_metrics()
        tiers = metrics['tier_distribution']
        
        print("[OK] Tier distribution calculated successfully")
        total_percentage = 0
        for tier, stats in tiers.items():
            print(f"  - {tier}:")
            print(f"    Range: {stats['range']}")
            print(f"    Count: {stats['count']}")
            print(f"    Percentage: {stats['percentage']:.2f}%")
            total_percentage += stats['percentage']
        
        if abs(total_percentage - 100.0) < 0.1:
            print(f"\n[OK] Total percentage check: {total_percentage:.2f}% (valid)")
            return True
        else:
            print(f"\n[ERROR] Total percentage check: {total_percentage:.2f}% (should be 100%)")
            return False
            
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return False

def test_score_distribution():
    """Test score distribution statistics."""
    print("\n" + "="*70)
    print("TEST 5: Score Distribution Statistics")
    print("="*70)
    
    try:
        metrics = generate_test_ranking_metrics()
        scores = metrics['score_stats']
        
        print("[OK] Score distribution calculated successfully")
        print(f"  - Mean: {scores['mean']:.6f}")
        print(f"  - Median: {scores['median']:.6f}")
        print(f"  - Std Dev: {scores['std_dev']:.6f}")
        print(f"  - Min: {scores['min']:.6f}")
        print(f"  - Max: {scores['max']:.6f}")
        
        if scores['min'] <= scores['max']:
            print("\n[OK] Score range validation: PASSED")
            return True
        else:
            print("\n[ERROR] Score range validation: FAILED")
            return False
            
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return False

def test_honeypot_analysis():
    """Test honeypot analysis metrics."""
    print("\n" + "="*70)
    print("TEST 6: Honeypot Detection Analysis")
    print("="*70)
    
    try:
        metrics = generate_test_ranking_metrics()
        hp_stats = metrics['key_metrics']
        
        print("[OK] Honeypot analysis calculated successfully")
        print(f"  - Total candidates: {hp_stats['total_candidates']}")
        print(f"  - Honeypots detected: {hp_stats['honeypot_detected']}")
        print(f"  - Valid candidates: {hp_stats['valid_candidates']}")
        print(f"  - Honeypot rate: {hp_stats['honeypot_rate']}")
        
        total = hp_stats['total_candidates']
        valid = hp_stats['valid_candidates']
        hp = hp_stats['honeypot_detected']
        
        if valid + hp == total:
            print("\n[OK] Candidate count validation: PASSED")
            return True
        else:
            print("\n[ERROR] Candidate count validation: FAILED")
            return False
            
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return False

def test_insights():
    """Test insights and recommendations."""
    print("\n" + "="*70)
    print("TEST 7: System Insights")
    print("="*70)
    
    try:
        metrics = generate_test_ranking_metrics()
        
        print("[OK] Insights generated successfully")
        print(f"  - System health: {metrics['system_health']}")
        print(f"  - Number of insights: {len(metrics['insights'])}")
        
        for i, insight in enumerate(metrics['insights'], 1):
            print(f"  - Insight {i}: {insight}")
        
        return True
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return False

def run_all_tests():
    """Run all tests."""
    print("\n" + "="*70)
    print("RANKING SYSTEM METRICS - COMPREHENSIVE TEST SUITE")
    print("="*70)
    
    tests = [
        ("Test 1: Metrics Generation", test_metrics_generation),
        ("Test 2: Component Analysis", test_component_analysis),
        ("Test 3: Ranking Metrics", test_ranking_metrics),
        ("Test 4: Tier Distribution", test_tier_distribution),
        ("Test 5: Score Distribution", test_score_distribution),
        ("Test 6: Honeypot Analysis", test_honeypot_analysis),
        ("Test 7: Insights", test_insights),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n[ERROR] {test_name} failed with exception: {str(e)}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status} - {test_name}")
    
    print(f"\n{passed}/{total} tests passed")
    
    if passed == total:
        print("\nALL TESTS PASSED - System metrics are fully functional!")
        return 0
    else:
        print(f"\n{total - passed} tests failed - Please review errors above")
        return 1

if __name__ == "__main__":
    sys.exit(run_all_tests())
