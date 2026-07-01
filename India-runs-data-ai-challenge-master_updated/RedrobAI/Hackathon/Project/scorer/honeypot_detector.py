"""
Stage 1 Honeypot Detector.

Identifies fictional candidates with impossible or fabricated experience.
A candidate is disqualified and receives a 0.0 score only when two or more
Stage 1 red flags are triggered.
"""

from datetime import date
from typing import Tuple, List, Dict, Any
import logging

from scorer.config import TODAY

logger = logging.getLogger(__name__)


class HoneypotDetectorGE:
    """
    Rule-based Stage 1 honeypot detector for candidate profiles.
    """
    
    def __init__(self):
        """Initialize the detector with validation rules."""
        self.red_flags = []
        
    def detect_honeypot(self, candidate: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Detect honeypot candidates using the Stage 1 rule specification.
        
        Args:
            candidate: Candidate dictionary with profile, career_history, etc.
            
        Returns:
            (is_honeypot: bool, reasons: list[str])
            A candidate is flagged as a honeypot if they trigger 2+ red flags.
        """
        self.red_flags = []
        
        # Run the eight Stage 1 red-flag checks.
        self._validate_skills(candidate)
        self._validate_career_timeline(candidate)
        self._validate_education(candidate)
        self._validate_experience_consistency(candidate)
        self._validate_temporal_impossibilities(candidate)
        self._validate_assessment_scores(candidate)
        
        is_honeypot = len(self.red_flags) >= 2
        return is_honeypot, self.red_flags

    def _validate_skills(self, candidate: Dict[str, Any]) -> None:
        """
        Rule 1: 8+ expert skills where 5+ have 0 months duration.
        Rule 2: 8+ expert skills where 6+ have 0 endorsements.
        """
        skills = candidate.get('skills', [])
        
        expert_skills = [s for s in skills if s.get('proficiency') == 'expert']
        expert_count = len(expert_skills)
        
        if expert_count >= 8:
            zero_duration = [s for s in expert_skills if s.get('duration_months', 0) == 0]
            if len(zero_duration) >= 5:
                self.red_flags.append(
                    f"Rule 1 Expert Skills Duration Gap: {expert_count} expert skills; "
                    f"{len(zero_duration)} have 0 months duration"
                )
            
            zero_endorsements = [s for s in expert_skills if s.get('endorsements', 0) == 0]
            if len(zero_endorsements) >= 6:
                self.red_flags.append(
                    f"Rule 2 Expert Endorsement Gap: {expert_count} expert skills; "
                    f"{len(zero_endorsements)} have 0 endorsements"
                )
    
    def _validate_career_timeline(self, candidate: Dict[str, Any]) -> None:
        """
        Rule 3: Sum of job durations is more than 2x stated YoE.
        Rule 4: A role duration exceeds actual elapsed time since start date.
        """
        career = candidate.get('career_history', [])
        profile = candidate.get('profile', {})
        yoe = profile.get('years_of_experience', 0)
        
        if not career:
            return
        
        total_career_months = sum(r.get('duration_months', 0) for r in career)
        yoe_months = yoe * 12
        
        if yoe_months > 0 and total_career_months > yoe_months * 2:
            self.red_flags.append(
                f"Rule 3 Career Duration Discrepancy: total career months "
                f"({total_career_months}) is >2x stated "
                f"years_of_experience ({yoe} years = {yoe_months:.0f} months)"
            )
        
        for role in career:
            start_str = role.get('start_date')
            end_str = role.get('end_date')
            duration = role.get('duration_months', 0)
            company = role.get('company', '?')
            
            if start_str and duration:
                try:
                    start = date.fromisoformat(start_str)
                    end = date.fromisoformat(end_str) if end_str else TODAY
                    elapsed_months = (end.year - start.year) * 12 + (end.month - start.month)
                    rounded_elapsed_months = elapsed_months + 1
                    
                    if elapsed_months >= 0 and duration > rounded_elapsed_months:
                        self.red_flags.append(
                            f"Rule 4 Impossible Job Tenure: {company} claims "
                            f"{duration} months but only about {rounded_elapsed_months} "
                            f"months elapsed"
                        )
                except (ValueError, TypeError):
                    pass
    
    def _validate_education(self, candidate: Dict[str, Any]) -> None:
        """
        Rule 5: Graduation end year before start year, or bachelor's degree
        duration less than 2 years or greater than 8 years.
        """
        education = candidate.get('education', [])
        
        for edu in education:
            start_y = edu.get('start_year', 0)
            end_y = edu.get('end_year', 0)
            degree = edu.get('degree', '').lower()
            
            if start_y and end_y:
                if end_y < start_y:
                    self.red_flags.append(
                        f"Rule 5 Education Timeline Mismatch: end_year ({end_y}) "
                        f"is before start_year ({start_y})"
                    )
                
                duration_yrs = end_y - start_y
                
                if self._is_bachelors_degree(degree):
                    if duration_yrs < 2 or duration_yrs > 8:
                        self.red_flags.append(
                            f"Rule 5 Education Timeline Mismatch: bachelor's degree "
                            f"duration is {duration_yrs} years ({start_y}-{end_y}); "
                            f"expected 2-8 years"
                        )
    
    def _validate_experience_consistency(self, candidate: Dict[str, Any]) -> None:
        """
        Rule 6: Career start year is more than 3 years before earliest
        graduation year.
        """
        education = candidate.get('education', [])
        career = candidate.get('career_history', [])
        profile = candidate.get('profile', {})
        yoe = profile.get('years_of_experience', 0)
        
        if not education:
            return

        earliest_grad = min(
            (e.get('end_year', 9999) for e in education if e.get('end_year')),
            default=9999
        )
        if earliest_grad >= 9999:
            return
        
        career_start_year = None
        career_roles_with_dates = [r for r in career if r.get('start_date')]
        if career_roles_with_dates:
            earliest_career_start = min(
                (r.get('start_date', '') for r in career_roles_with_dates), default=None
            )
            try:
                career_start_year = int(earliest_career_start[:4])
            except (ValueError, TypeError):
                career_start_year = None
        elif yoe > 0:
            career_start_year = int(TODAY.year - yoe)

        if career_start_year is not None and career_start_year < earliest_grad - 3:
            self.red_flags.append(
                f"Rule 6 Career Pre-Graduation: career start year "
                f"({career_start_year}) is more than 3 years before earliest "
                f"graduation year ({earliest_grad})"
            )
    
    def _validate_temporal_impossibilities(self, candidate: Dict[str, Any]) -> None:
        """
        Rule 8: Two or more overlapping employment periods where overlap is
        more than 30 days.
        """
        career = candidate.get('career_history', [])
        
        dated_roles = []
        for role in career:
            start_str = role.get('start_date')
            end_str = role.get('end_date')
            
            if start_str:
                try:
                    s = date.fromisoformat(start_str)
                    e = date.fromisoformat(end_str) if end_str else TODAY
                    dated_roles.append((s, e, role.get('company', '?')))
                except (ValueError, TypeError):
                    pass
        
        dated_roles.sort(key=lambda x: x[0])
        overlap_count = 0
        
        for i in range(len(dated_roles) - 1):
            _, end_i, comp_i = dated_roles[i]
            start_next, _, comp_next = dated_roles[i + 1]
            
            # Allow 30 days overlap (notice period)
            if end_i > start_next and (end_i - start_next).days > 30:
                overlap_count += 1
        
        if overlap_count >= 2:
            self.red_flags.append(
                f"Rule 8 Overlapping Jobs: {overlap_count} employment periods "
                f"overlap by more than 30 days"
            )
    
    def _validate_assessment_scores(self, candidate: Dict[str, Any]) -> None:
        """
        Rule 7: 10 or more expert skills but 0 platform skill assessments.
        """
        skills = candidate.get('skills', [])
        expert_skills = [s for s in skills if s.get('proficiency') == 'expert']
        signals = candidate.get('redrob_signals', {})
        assessments = signals.get('skill_assessment_scores', {})

        if len(expert_skills) >= 10 and len(assessments) == 0:
            self.red_flags.append(
                f"Rule 7 Expert Credibility Gap: {len(expert_skills)} expert "
                f"skills but 0 platform skill assessments completed"
            )

    @staticmethod
    def _is_bachelors_degree(degree: str) -> bool:
        """Return True when the degree text indicates a bachelor's degree."""
        tokens = (
            'bachelor', 'bachelors', 'b.tech', 'btech', 'b.e.', 'be',
            'b.sc', 'bsc', 'b.a.', 'ba', 'b.s.', 'bs'
        )
        return any(token in degree for token in tokens)


def detect_honeypot(candidate: dict) -> tuple[bool, list[str]]:
    """
    Detect honeypot candidates using the Stage 1 rule specification.
    
    Returns (is_honeypot: bool, reasons: list[str]).
    A candidate is flagged as a honeypot if they trigger 2+ red flags.
    """
    return HoneypotDetectorGE().detect_honeypot(candidate)
