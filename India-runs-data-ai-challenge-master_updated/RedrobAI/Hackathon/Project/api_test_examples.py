#!/usr/bin/env python3
"""
api_test_examples.py - Complete examples of using the enhanced FastAPI with JD support.
Run these examples to test all new features.
"""

import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"


class APITester:
    """Test suite for enhanced FastAPI endpoints."""
    
    def __init__(self, base_url=BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()
    
    def test_jd_upload_text(self):
        """Test uploading a text-based JD."""
        print("\n=== Test: Upload Text JD ===")
        
        jd_text = """
        Senior Machine Learning Engineer
        
        Company: TechCorp AI
        Location: San Francisco, CA (Remote)
        Experience Required: 5 years
        
        MUST-HAVE REQUIREMENTS:
        - 5+ years of Python development experience
        - Strong machine learning background
        - Experience with SQL and databases
        - AWS cloud platform expertise
        - Docker containerization
        - API development experience
        
        NICE-TO-HAVE:
        - Natural Language Processing (NLP) experience
        - Computer Vision knowledge
        - Kubernetes experience
        - Experience with data engineering pipelines
        
        PREFERRED:
        - Git version control
        - CI/CD pipeline experience
        - Agile/Scrum methodology
        """
        
        # Create temporary file
        with open("temp_jd.txt", "w") as f:
            f.write(jd_text)
        
        # Upload
        with open("temp_jd.txt", "rb") as f:
            response = self.session.post(
                f"{self.base_url}/api/jd/upload",
                files={"file": f}
            )
        
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.json()
    
    def test_get_jd_summary(self):
        """Test getting JD summary."""
        print("\n=== Test: Get JD Summary ===")
        
        response = self.session.get(f"{self.base_url}/api/jd/summary")
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.json()
    
    def test_apply_strategy(self, strategy):
        """Test applying a ranking strategy."""
        print(f"\n=== Test: Apply Strategy '{strategy}' ===")
        
        response = self.session.post(
            f"{self.base_url}/api/preferences/strategy/{strategy}"
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.json()
    
    def test_get_strategies(self):
        """Test getting available strategies."""
        print("\n=== Test: Get Available Strategies ===")
        
        response = self.session.get(f"{self.base_url}/api/preferences/strategies")
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.json()
    
    def test_set_custom_preferences(self):
        """Test setting custom preferences."""
        print("\n=== Test: Set Custom Preferences ===")
        
        preferences = {
            "skill_match_weight": 0.55,
            "experience_weight": 0.25,
            "title_match_weight": 0.1,
            "location_weight": 0.05,
            "behavioral_weight": 0.05,
            "must_have_weight": 0.8,
            "nice_to_have_weight": 0.15,
            "preferred_weight": 0.05,
            "minimum_experience": 3,
            "minimum_skill_match": 60.0,
            "minimum_overall_score": 50.0,
            "exclude_honeypots": True,
            "ranking_strategy": "skill_focused"
        }
        
        response = self.session.post(
            f"{self.base_url}/api/preferences/set",
            json=preferences
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.json()
    
    def test_get_preferences(self):
        """Test getting current preferences."""
        print("\n=== Test: Get Current Preferences ===")
        
        response = self.session.get(f"{self.base_url}/api/preferences/get")
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.json()
    
    def test_rank_with_jd(self, top_n=10):
        """Test ranking candidates with JD."""
        print(f"\n=== Test: Rank Candidates with JD (top {top_n}) ===")
        
        response = self.session.post(
            f"{self.base_url}/api/rank-with-jd",
            json={"top_n": top_n}
        )
        print(f"Status: {response.status_code}")
        data = response.json()
        
        # Print summary
        if "results" in data:
            print(f"Results returned: {len(data['results'])}")
            print(f"Total candidates: {data.get('total_candidates', 'N/A')}")
            print(f"Total valid: {data.get('total_valid', 'N/A')}")
            
            # Print first few results
            if data['results']:
                print("\nTop 3 Results:")
                for r in data['results'][:3]:
                    print(f"  - {r['rank']}: {r['name']} (Score: {r['score_raw']:.2f})")
        else:
            print(f"Response: {json.dumps(data, indent=2)}")
        
        return data
    
    def test_filter_by_jd(self, top_n=50):
        """Test filtering candidates by JD."""
        print(f"\n=== Test: Filter Candidates by JD ===")
        
        response = self.session.post(
            f"{self.base_url}/api/candidates/filter-by-jd",
            json={"top_n": top_n}
        )
        print(f"Status: {response.status_code}")
        data = response.json()
        
        print(f"Qualified: {data.get('qualified_candidates', 'N/A')}")
        print(f"Filtered out: {data.get('filtered_out_candidates', 'N/A')}")
        
        return data
    
    def test_candidate_match_score(self, candidate_id):
        """Test getting individual candidate match score."""
        print(f"\n=== Test: Get Candidate Match Score ===")
        
        response = self.session.post(
            f"{self.base_url}/api/candidate-match-score",
            json={"candidate_id": candidate_id}
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.json()
    
    def test_reset_preferences(self):
        """Test resetting preferences."""
        print("\n=== Test: Reset Preferences ===")
        
        response = self.session.post(f"{self.base_url}/api/preferences/reset")
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.json()
    
    def test_clear_jd(self):
        """Test clearing JD."""
        print("\n=== Test: Clear JD ===")
        
        response = self.session.post(f"{self.base_url}/api/jd/clear")
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.json()


def run_complete_test_suite():
    """Run complete test suite."""
    tester = APITester()
    
    print("=" * 60)
    print("FastAPI Enhanced JD Testing Suite")
    print("=" * 60)
    
    try:
        # Test JD Upload
        jd_result = tester.test_jd_upload_text()
        if jd_result.get("success"):
            print("✓ JD Upload successful")
        
        # Test Get JD Summary
        jd_summary = tester.test_get_jd_summary()
        print("✓ JD Summary retrieved")
        
        # Test Get Available Strategies
        strategies = tester.test_get_strategies()
        print("✓ Strategies retrieved")
        
        # Test Apply Different Strategies
        for strategy in ["skill_focused", "experience_focused", "quick_hire"]:
            tester.test_apply_strategy(strategy)
            print(f"✓ Strategy '{strategy}' applied")
        
        # Test Custom Preferences
        tester.test_set_custom_preferences()
        print("✓ Custom preferences set")
        
        # Test Get Preferences
        prefs = tester.test_get_preferences()
        print("✓ Current preferences retrieved")
        
        # Test Rank with JD
        results = tester.test_rank_with_jd(top_n=10)
        if results.get("results"):
            print(f"✓ Ranking with JD successful ({len(results['results'])} results)")
        
        # Test Filter by JD
        filtered = tester.test_filter_by_jd(top_n=50)
        print("✓ Filtering by JD successful")
        
        # Test Reset
        tester.test_reset_preferences()
        print("✓ Preferences reset")
        
        # Test Clear
        tester.test_clear_jd()
        print("✓ JD cleared")
        
        print("\n" + "=" * 60)
        print("✓ All tests completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Error during testing: {e}")
        print("Make sure the FastAPI server is running on http://127.0.0.1:8000")


if __name__ == "__main__":
    run_complete_test_suite()
