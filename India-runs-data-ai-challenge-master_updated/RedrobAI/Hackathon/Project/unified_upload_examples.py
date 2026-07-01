#!/usr/bin/env python3
"""
unified_upload_examples.py - Complete examples for unified file uploads.
"""

import json
import zipfile
import tempfile
import os
import requests
from pathlib import Path


class UnifiedUploadExamples:
    """Examples for using the unified upload feature."""
    
    BASE_URL = "http://127.0.0.1:8000"
    
    @staticmethod
    def create_sample_json():
        """Create a sample JSON file with JD and candidates."""
        print("\n=== Example 1: Create JSON File ===\n")
        
        data = {
            "job_description": """
            Senior AI Engineer
            
            Company: TechCorp AI
            Location: San Francisco, CA
            Experience Required: 5 years
            
            MUST-HAVE REQUIREMENTS:
            - 5+ years Python development
            - Strong machine learning background
            - SQL and database expertise
            - AWS cloud experience
            - Docker containerization
            - API development
            
            NICE-TO-HAVE:
            - Natural Language Processing (NLP)
            - Computer Vision knowledge
            - Kubernetes experience
            - Data engineering pipelines
            
            PREFERRED:
            - Git version control
            - CI/CD experience
            - Agile methodology
            """,
            "candidates": [
                {
                    "id": "CAND_001",
                    "name": "Alice Johnson",
                    "title": "ML Engineer",
                    "experience": 8,
                    "skills": ["Python", "ML", "SQL", "AWS", "Docker", "API"],
                    "location": "San Francisco",
                    "country": "USA"
                },
                {
                    "id": "CAND_002",
                    "name": "Bob Smith",
                    "title": "Data Scientist",
                    "experience": 6,
                    "skills": ["Python", "Machine Learning", "SQL", "GCP"],
                    "location": "New York",
                    "country": "USA"
                },
                {
                    "id": "CAND_003",
                    "name": "Carol Davis",
                    "title": "AI Researcher",
                    "experience": 7,
                    "skills": ["Python", "NLP", "TensorFlow", "AWS", "Docker"],
                    "location": "San Francisco",
                    "country": "USA"
                },
                {
                    "id": "CAND_004",
                    "name": "David Lee",
                    "title": "Backend Engineer",
                    "experience": 5,
                    "skills": ["Python", "Go", "SQL", "Kubernetes", "Docker"],
                    "location": "Remote",
                    "country": "USA"
                },
                {
                    "id": "CAND_005",
                    "name": "Eve Martinez",
                    "title": "Data Engineer",
                    "experience": 4,
                    "skills": ["Python", "Spark", "SQL", "AWS"],
                    "location": "Austin",
                    "country": "USA"
                }
            ]
        }
        
        # Save to file
        filename = "combined_data.json"
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"✓ Created: {filename}")
        print(f"  - 1 Job Description")
        print(f"  - 5 Candidates")
        print(f"  - Ready to upload!\n")
        
        return filename
    
    @staticmethod
    def create_sample_zip():
        """Create a sample ZIP file with JD and candidates."""
        print("\n=== Example 2: Create ZIP File ===\n")
        
        # Create JD file
        jd_content = """Senior AI Engineer

Company: TechCorp AI
Location: San Francisco, CA
Experience Required: 5 years

MUST-HAVE REQUIREMENTS:
- 5+ years Python development
- Strong machine learning background
- SQL and database expertise
- AWS cloud experience
- Docker containerization
- API development

NICE-TO-HAVE:
- Natural Language Processing (NLP)
- Computer Vision knowledge
- Kubernetes experience

PREFERRED:
- Git version control
- CI/CD experience
"""
        
        # Create candidates JSONL file
        candidates_jsonl = """{"id": "CAND_001", "name": "Alice Johnson", "title": "ML Engineer", "experience": 8, "skills": ["Python", "ML", "SQL", "AWS", "Docker"], "location": "San Francisco"}
{"id": "CAND_002", "name": "Bob Smith", "title": "Data Scientist", "experience": 6, "skills": ["Python", "ML", "SQL", "GCP"], "location": "New York"}
{"id": "CAND_003", "name": "Carol Davis", "title": "AI Researcher", "experience": 7, "skills": ["Python", "NLP", "TensorFlow", "AWS"], "location": "San Francisco"}
{"id": "CAND_004", "name": "David Lee", "title": "Backend Engineer", "experience": 5, "skills": ["Python", "Go", "SQL", "Kubernetes"], "location": "Remote"}
{"id": "CAND_005", "name": "Eve Martinez", "title": "Data Engineer", "experience": 4, "skills": ["Python", "Spark", "SQL", "AWS"], "location": "Austin"}
"""
        
        # Create ZIP
        zip_filename = "combined_data.zip"
        with zipfile.ZipFile(zip_filename, 'w') as zf:
            zf.writestr('job_description.txt', jd_content)
            zf.writestr('candidates.jsonl', candidates_jsonl)
        
        print(f"✓ Created: {zip_filename}")
        print(f"  - job_description.txt")
        print(f"  - candidates.jsonl")
        print(f"  - Ready to upload!\n")
        
        return zip_filename
    
    @staticmethod
    def upload_unified_file(file_path, auto_rank=True):
        """Upload unified file and get results."""
        print(f"\n=== Uploading: {file_path} ===\n")
        
        try:
            with open(file_path, 'rb') as f:
                files = {'file': f}
                params = {'auto_rank': auto_rank}
                
                response = requests.post(
                    f"{UnifiedUploadExamples.BASE_URL}/api/unified-upload",
                    files=files,
                    params=params
                )
            
            if response.status_code == 200:
                result = response.json()
                print("✓ Upload Successful!\n")
                print(f"  Job Title: {result['job_title']}")
                print(f"  Experience Required: {result['experience_required']} years")
                print(f"  Must-Have Skills: {result['must_have_skills']}")
                print(f"  Nice-to-Have Skills: {result['nice_to_have_skills']}")
                print(f"  Preferred Skills: {result['preferred_skills']}")
                print(f"\n  Total Candidates: {result['total_candidates']}")
                print(f"  Valid Candidates: {result['valid_candidates']}")
                print(f"  Honeypots Detected: {result['honeypots']}")
                print(f"\n  File Type: {result['file_type']}")
                print(f"  Auto-Ranked: {result['candidates_ranked']}")
                print(f"\n  Message: {result['message']}\n")
                
                return result
            else:
                print(f"✗ Error: {response.status_code}")
                print(f"  {response.json()}\n")
                return None
        
        except Exception as e:
            print(f"✗ Error: {str(e)}\n")
            return None
    
    @staticmethod
    def get_supported_formats():
        """Get supported format information."""
        print("\n=== Supported Formats ===\n")
        
        try:
            response = requests.get(
                f"{UnifiedUploadExamples.BASE_URL}/api/unified-upload/formats"
            )
            
            if response.status_code == 200:
                data = response.json()
                
                for fmt in data['supported_formats']:
                    print(f"Format: {fmt['format']}")
                    print(f"  Extension: {fmt['extension']}")
                    print(f"  Description: {fmt['description']}")
                    print()
                
                print("Notes:")
                for note in data['notes']:
                    print(f"  • {note}")
                print()
            
        except Exception as e:
            print(f"✗ Error: {str(e)}\n")
    
    @staticmethod
    def get_rankings():
        """Get rankings for uploaded candidates."""
        print("\n=== Getting Rankings ===\n")
        
        try:
            response = requests.post(
                f"{UnifiedUploadExamples.BASE_URL}/api/rank-with-jd",
                json={"top_n": 10}
            )
            
            if response.status_code == 200:
                data = response.json()
                
                print(f"Total Candidates: {data['total_candidates']}")
                print(f"Qualified: {data['total_valid']}")
                print(f"\nTop 10 Ranked:\n")
                
                for result in data['results'][:10]:
                    print(f"{result['rank']}. {result['name']}")
                    print(f"   Title: {result['current_title']}")
                    print(f"   YoE: {result['yoe']} years")
                    print(f"   Score: {result['score_raw']:.2f}")
                    print()
                
                return data
            else:
                print(f"✗ Error: {response.status_code}")
                print(f"  {response.json()}\n")
                return None
        
        except Exception as e:
            print(f"✗ Error: {str(e)}\n")
            return None


def main():
    """Run example demonstrations."""
    print("=" * 70)
    print("UNIFIED UPLOAD EXAMPLES - Candidates + JD in Single File")
    print("=" * 70)
    
    examples = UnifiedUploadExamples()
    
    # Show supported formats
    examples.get_supported_formats()
    
    # Example 1: JSON format
    print("\n" + "="*70)
    print("EXAMPLE 1: JSON Format")
    print("="*70)
    json_file = examples.create_sample_json()
    
    result = examples.upload_unified_file(json_file, auto_rank=True)
    
    if result:
        # Wait a moment for background ranking
        print("Waiting for ranking to complete...")
        import time
        time.sleep(5)
        
        rankings = examples.get_rankings()
    
    # Clean up
    if os.path.exists(json_file):
        os.remove(json_file)
    
    # Example 2: ZIP format
    print("\n" + "="*70)
    print("EXAMPLE 2: ZIP Format")
    print("="*70)
    zip_file = examples.create_sample_zip()
    
    result = examples.upload_unified_file(zip_file, auto_rank=True)
    
    if result:
        # Wait for ranking
        print("Waiting for ranking to complete...")
        import time
        time.sleep(5)
        
        rankings = examples.get_rankings()
    
    # Clean up
    if os.path.exists(zip_file):
        os.remove(zip_file)
    
    print("\n" + "="*70)
    print("✓ Examples Complete!")
    print("="*70)
    print("\nNext steps:")
    print("1. Read UNIFIED_UPLOAD_GUIDE.md for complete documentation")
    print("2. Create your own combined file")
    print("3. Upload using the /api/unified-upload endpoint")
    print("4. Get instant rankings!\n")


if __name__ == "__main__":
    main()
