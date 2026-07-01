#!/usr/bin/env python3
"""
recruiter_preferences.py — Recruiter-defined ranking preferences and weighting system.
Allows custom ranking criteria based on recruiter needs.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel


class RecruiterPreferences(BaseModel):
    """Recruiter ranking preferences."""
    
    # Weight factors (0.0 to 1.0)
    skill_match_weight: float = 0.4  # How much skill match matters
    experience_weight: float = 0.25   # How much experience matters
    title_match_weight: float = 0.15  # How much job title match matters
    location_weight: float = 0.1      # How much location matters
    behavioral_weight: float = 0.1    # How much behavioral fit matters
    
    # Skill weighting
    must_have_weight: float = 0.8     # Weight for must-have skills
    nice_to_have_weight: float = 0.15 # Weight for nice-to-have skills
    preferred_weight: float = 0.05    # Weight for preferred skills
    
    # Minimum thresholds
    minimum_experience: int = 0       # Minimum years of experience required
    minimum_skill_match: float = 0.0  # Minimum skill match percentage (0-100)
    minimum_overall_score: float = 0.0  # Minimum overall score (0-100)
    
    # Filters
    exclude_honeypots: bool = True
    prefer_specific_titles: List[str] = []  # Titles to prioritize
    prefer_locations: List[str] = []        # Locations to prioritize
    
    # Ranking strategy
    ranking_strategy: str = "balanced"  # balanced, skill_focused, experience_focused, title_focused
    
    # Additional preferences
    allow_remote: bool = True
    allow_relocation: bool = True
    prioritize_current_role: bool = False
    
    class Config:
        schema_extra = {
            "example": {
                "skill_match_weight": 0.4,
                "experience_weight": 0.25,
                "title_match_weight": 0.15,
                "location_weight": 0.1,
                "behavioral_weight": 0.1,
                "must_have_weight": 0.8,
                "nice_to_have_weight": 0.15,
                "preferred_weight": 0.05,
                "minimum_experience": 3,
                "minimum_skill_match": 60.0,
                "minimum_overall_score": 50.0,
                "exclude_honeypots": True,
                "ranking_strategy": "skill_focused",
            }
        }


class PreferencesManager:
    """Manages recruiter preferences for ranking."""
    
    def __init__(self):
        self.current_preferences = RecruiterPreferences()
        self.preference_history = []
    
    def set_preferences(self, preferences: Dict) -> RecruiterPreferences:
        """Set recruiter preferences."""
        self.current_preferences = RecruiterPreferences(**preferences)
        self.preference_history.append(self.current_preferences.copy(deep=True))
        return self.current_preferences
    
    def get_preferences(self) -> RecruiterPreferences:
        """Get current preferences."""
        return self.current_preferences
    
    def apply_ranking_strategy(self, strategy: str) -> Dict:
        """Apply a preset ranking strategy."""
        strategies = {
            "balanced": {
                "skill_match_weight": 0.4,
                "experience_weight": 0.25,
                "title_match_weight": 0.15,
                "location_weight": 0.1,
                "behavioral_weight": 0.1,
            },
            "skill_focused": {
                "skill_match_weight": 0.6,
                "experience_weight": 0.15,
                "title_match_weight": 0.1,
                "location_weight": 0.1,
                "behavioral_weight": 0.05,
            },
            "experience_focused": {
                "skill_match_weight": 0.2,
                "experience_weight": 0.45,
                "title_match_weight": 0.15,
                "location_weight": 0.1,
                "behavioral_weight": 0.1,
            },
            "title_focused": {
                "skill_match_weight": 0.25,
                "experience_weight": 0.2,
                "title_match_weight": 0.35,
                "location_weight": 0.1,
                "behavioral_weight": 0.1,
            },
            "quick_hire": {
                "skill_match_weight": 0.35,
                "experience_weight": 0.3,
                "title_match_weight": 0.2,
                "location_weight": 0.1,
                "behavioral_weight": 0.05,
                "minimum_experience": 1,
                "minimum_skill_match": 50.0,
            },
            "elite": {
                "skill_match_weight": 0.45,
                "experience_weight": 0.35,
                "title_match_weight": 0.1,
                "location_weight": 0.05,
                "behavioral_weight": 0.05,
                "minimum_experience": 5,
                "minimum_skill_match": 80.0,
                "minimum_overall_score": 75.0,
            },
        }
        
        if strategy not in strategies:
            return {"error": f"Unknown strategy: {strategy}"}
        
        weights = strategies[strategy]
        self.current_preferences = RecruiterPreferences(**weights)
        return {"strategy": strategy, "weights": weights}
    
    def calculate_weighted_score(
        self,
        skill_score: float,
        experience_score: float,
        title_score: float,
        location_score: float,
        behavioral_score: float
    ) -> float:
        """
        Calculate weighted overall score based on recruiter preferences.
        All input scores should be 0-100.
        Returns overall score 0-100.
        """
        prefs = self.current_preferences
        
        weighted_score = (
            (skill_score * prefs.skill_match_weight) +
            (experience_score * prefs.experience_weight) +
            (title_score * prefs.title_match_weight) +
            (location_score * prefs.location_weight) +
            (behavioral_score * prefs.behavioral_weight)
        )
        
        # Normalize if weights don't add up to 1.0
        total_weight = (
            prefs.skill_match_weight +
            prefs.experience_weight +
            prefs.title_match_weight +
            prefs.location_weight +
            prefs.behavioral_weight
        )
        
        if total_weight > 0:
            weighted_score = weighted_score / total_weight * 100
        
        return min(100, max(0, weighted_score))  # Clamp 0-100
    
    def apply_filters(self, candidate: Dict, jd_skills: Dict) -> tuple[bool, List[str]]:
        """
        Apply recruiter filters to candidate.
        Returns (passes_filters, filter_messages)
        """
        messages = []
        prefs = self.current_preferences
        
        # Check honeypot
        if prefs.exclude_honeypots and candidate.get("is_honeypot", False):
            return False, ["Candidate is marked as honeypot"]
        
        # Check minimum experience
        candidate_yoe = candidate.get("profile", {}).get("years_of_experience", 0)
        if candidate_yoe < prefs.minimum_experience:
            messages.append(
                f"Experience ({candidate_yoe} yrs) below minimum ({prefs.minimum_experience} yrs)"
            )
            return False, messages
        
        # Check location preferences
        if prefs.prefer_locations:
            candidate_location = candidate.get("profile", {}).get("location", "")
            if not any(loc.lower() in candidate_location.lower() for loc in prefs.prefer_locations):
                messages.append(f"Location '{candidate_location}' not in preferred list")
        
        # Check title preferences
        if prefs.prefer_specific_titles:
            candidate_title = candidate.get("profile", {}).get("current_title", "")
            if not any(title.lower() in candidate_title.lower() for title in prefs.prefer_specific_titles):
                messages.append(f"Title '{candidate_title}' not in preferred titles")
        
        return True, messages
    
    def get_strategy_recommendations(self, jd_metadata: Dict) -> List[Dict]:
        """Recommend ranking strategies based on JD metadata."""
        recommendations = []
        
        exp_required = jd_metadata.get("experience_required", 0)
        
        recommendations.append({
            "strategy": "skill_focused",
            "reason": "Best for specialized technical roles",
            "use_case": "When technical skills are critical"
        })
        
        recommendations.append({
            "strategy": "experience_focused",
            "reason": "Best for senior/leadership roles",
            "use_case": "When experience matters most"
        })
        
        if exp_required and exp_required >= 7:
            recommendations.append({
                "strategy": "elite",
                "reason": f"Job requires {exp_required}+ years experience",
                "use_case": "Suitable for this high-seniority role"
            })
        
        recommendations.append({
            "strategy": "quick_hire",
            "reason": "Good for quick turnaround hiring",
            "use_case": "When you need to hire fast"
        })
        
        return recommendations
    
    def reset_to_defaults(self):
        """Reset preferences to defaults."""
        self.current_preferences = RecruiterPreferences()
        return self.current_preferences


# Global preferences manager instance
preferences_manager = PreferencesManager()
