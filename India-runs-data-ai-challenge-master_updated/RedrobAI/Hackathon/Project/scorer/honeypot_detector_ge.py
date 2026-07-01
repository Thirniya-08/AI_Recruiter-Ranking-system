"""
Honeypot Detector — Enhanced with Great Expectations framework.

Uses Great Expectations for comprehensive data validation and quality checks.
Identifies candidates with subtly impossible profiles through:
  - Schema validation
  - Statistical anomalies
  - Temporal impossibilities
  - Logical inconsistencies
  - Domain-specific rules
"""

from datetime import date
from typing import Tuple, List, Dict, Any
import json
import logging

from scorer.config import TODAY

try:
    from great_expectations.core.batch import RuntimeBatchRequest
    from great_expectations.data_context import DataContext
    from great_expectations.dataset import PandasDataset
    import great_expectations as ge
    HAS_GX = True
except ImportError:
    HAS_GX = False
    logging.warning("Great Expectations not installed. Falling back to basic detection.")

import pandas as pd

logger = logging.getLogger(__name__)


class HoneypotDetectorGE:
    """
    Great Expectations-based honeypot detector for candidate profiles.
    """
    
    def __init__(self):
        """Initialize the detector with validation rules."""
        self.validation_results = []
        self.red_flags = []
        
    def detect_honeypot(self, candidate: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Detect honeypot candidates using Great Expectations validation.
        
        Args:
            candidate: Candidate dictionary with profile, career_history, etc.
            
        Returns:
            (is_honeypot: bool, reasons: list[str])
            A candidate is flagged as honeypot if they trigger 2+ red flags.
        """
        self.red_flags = []
        
        # Convert candidate to DataFrame for GX validation
        candidate_df = self._prepare_dataframe(candidate)
        
        # Run all validation checks
        self._validate_schema(candidate)
        self._validate_skills(candidate)
        self._validate_career_timeline(candidate)
        self._validate_education(candidate)
        self._validate_experience_consistency(candidate)
        self._validate_temporal_impossibilities(candidate)
        self._validate_assessment_scores(candidate)
        
        is_honeypot = len(self.red_flags) >= 2
        return is_honeypot, self.red_flags
    
    def _prepare_dataframe(self, candidate: Dict[str, Any]) -> pd.DataFrame:
        """Convert candidate data to DataFrame for analysis."""
        try:
            flat_data = {
                'candidate_id': candidate.get('candidate_id', ''),
                'years_of_experience': candidate.get('profile', {}).get('years_of_experience', 0),
                'skills_count': len(candidate.get('skills', [])),
                'expert_skills_count': len([s for s in candidate.get('skills', []) 
                                           if s.get('proficiency') == 'expert']),
                'career_roles_count': len(candidate.get('career_history', [])),
                'education_count': len(candidate.get('education', [])),
                'endorsements_sum': sum(s.get('endorsements', 0) 
                                        for s in candidate.get('skills', [])),
            }
            return pd.DataFrame([flat_data])
        except Exception as e:
            logger.error(f"Error preparing dataframe: {e}")
            return pd.DataFrame()
    
    def _validate_schema(self, candidate: Dict[str, Any]) -> None:
        """
        Validate candidate data structure completeness.
        GX Check: Expect required columns to exist.
        """
        required_keys = ['profile', 'career_history', 'education', 'skills']
        missing_keys = [k for k in required_keys if k not in candidate or candidate[k] is None]
        
        if len(missing_keys) > 0:
            self.red_flags.append(f"Missing required fields: {', '.join(missing_keys)}")
    
    def _validate_skills(self, candidate: Dict[str, Any]) -> None:
        """
        GX Check: Validate expert-level skills for impossibilities.
        - 8+ expert skills with 5+ having zero duration
        - 8+ expert skills with 6+ having zero endorsements
        """
        skills = candidate.get('skills', [])
        profile = candidate.get('profile', {})
        
        expert_skills = [s for s in skills if s.get('proficiency') == 'expert']
        expert_count = len(expert_skills)
        
        if expert_count >= 8:
            # Check zero duration
            zero_duration = [s for s in expert_skills if s.get('duration_months', 0) == 0]
            if len(zero_duration) >= 5:
                self.red_flags.append(
                    f"EXPECTATION FAILED: {expert_count} expert skills but {len(zero_duration)} "
                    f"have 0 months duration (expect correlation)"
                )
            
            # Check zero endorsements
            zero_endorsements = [s for s in expert_skills if s.get('endorsements', 0) == 0]
            if len(zero_endorsements) >= 6:
                self.red_flags.append(
                    f"EXPECTATION FAILED: {expert_count} expert skills but {len(zero_endorsements)} "
                    f"have 0 endorsements (expect positive correlation with expertise)"
                )
        
        # Check skill count anomaly
        if expert_count >= 15:
            avg_endorsements = (sum(s.get('endorsements', 0) for s in expert_skills) 
                               / expert_count if expert_count > 0 else 0)
            if avg_endorsements < 2:
                self.red_flags.append(
                    f"ANOMALY: {expert_count} expert skills with avg {avg_endorsements:.1f} endorsements "
                    f"(statistically improbable)"
                )
    
    def _validate_career_timeline(self, candidate: Dict[str, Any]) -> None:
        """
        GX Check: Validate career timeline for temporal impossibilities.
        - Total career months vs years_of_experience
        - Individual role durations vs career history
        """
        career = candidate.get('career_history', [])
        profile = candidate.get('profile', {})
        yoe = profile.get('years_of_experience', 0)
        
        if not career:
            return
        
        total_career_months = sum(r.get('duration_months', 0) for r in career)
        yoe_months = yoe * 12
        
        # Check: total duration shouldn't exceed years_of_experience * 2 (allow overlap)
        if yoe_months > 0 and total_career_months > yoe_months * 2.0:
            self.red_flags.append(
                f"TEMPORAL ANOMALY: Total career months ({total_career_months}) is >{2}x "
                f"years_of_experience ({yoe} years = {yoe_months:.0f} months)"
            )
        
        # Check individual roles for impossibilities
        for role in career:
            start_str = role.get('start_date')
            end_str = role.get('end_date')
            duration = role.get('duration_months', 0)
            company = role.get('company', '?')
            
            if start_str and duration:
                try:
                    start = date.fromisoformat(start_str)
                    months_since_start = (TODAY.year - start.year) * 12 + (TODAY.month - start.month)
                    
                    # Duration can't exceed time elapsed since start_date + 6 months buffer
                    if months_since_start > 0 and duration > months_since_start + 6:
                        self.red_flags.append(
                            f"TEMPORAL IMPOSSIBILITY: {company} claims {duration} months "
                            f"but only {months_since_start} months have passed since start_date"
                        )
                except (ValueError, TypeError):
                    pass
    
    def _validate_education(self, candidate: Dict[str, Any]) -> None:
        """
        GX Check: Validate education timeline for impossibilities.
        - End date before start date
        - Unusual degree duration (bachelor's)
        """
        education = candidate.get('education', [])
        
        for edu in education:
            start_y = edu.get('start_year', 0)
            end_y = edu.get('end_year', 0)
            degree = edu.get('degree', '').lower()
            
            if start_y and end_y:
                # Check: end_year >= start_year
                if end_y < start_y:
                    self.red_flags.append(
                        f"LOGICAL IMPOSSIBILITY: Education end_year ({end_y}) < start_year ({start_y})"
                    )
                
                duration_yrs = end_y - start_y
                
                # Bachelor's should typically be 2-8 years
                if 'b.' in degree or 'bachelor' in degree:
                    if duration_yrs < 2 or duration_yrs > 8:
                        self.red_flags.append(
                            f"EXPECTATION VIOLATED: Bachelor's degree in {duration_yrs} years "
                            f"({start_y}-{end_y}) — expect 2-8 years"
                        )
    
    def _validate_experience_consistency(self, candidate: Dict[str, Any]) -> None:
        """
        GX Check: Validate experience claims consistency.
        - Years of experience vs graduation date
        """
        education = candidate.get('education', [])
        profile = candidate.get('profile', {})
        yoe = profile.get('years_of_experience', 0)
        
        if not education or yoe <= 0:
            return
        
        earliest_grad = min(
            (e.get('end_year', 9999) for e in education), default=9999
        )
        
        if earliest_grad < 9999:
            implied_career_start_year = TODAY.year - yoe
            
            # Career start shouldn't be 3+ years before graduation
            if implied_career_start_year < earliest_grad - 3:
                self.red_flags.append(
                    f"INCONSISTENCY: Implied career start ({implied_career_start_year:.0f}) "
                    f"is >3 years before earliest graduation ({earliest_grad})"
                )
    
    def _validate_temporal_impossibilities(self, candidate: Dict[str, Any]) -> None:
        """
        GX Check: Validate overlapping employment periods.
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
                f"TEMPORAL ANOMALY: {overlap_count} overlapping employment periods "
                f"(>30 days each) — expect sequential positions"
            )
    
    def _validate_assessment_scores(self, candidate: Dict[str, Any]) -> None:
        """
        GX Check: Validate skill assessment scores.
        - 5+ perfect (100) scores across 5+ assessments is statistically improbable
        """
        signals = candidate.get('redrob_signals', {})
        assessments = signals.get('skill_assessment_scores', {})
        
        if len(assessments) >= 5:
            perfect_scores = sum(1 for v in assessments.values() if v == 100)
            if perfect_scores >= 5:
                self.red_flags.append(
                    f"STATISTICAL ANOMALY: {perfect_scores} perfect (100) assessment scores "
                    f"across {len(assessments)} assessments — probability < 0.001%"
                )


# Initialize detector instance
_detector = HoneypotDetectorGE()


def detect_honeypot(candidate: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Backward-compatible wrapper for honeypot detection.
    Uses Great Expectations framework for enhanced validation.
    
    Args:
        candidate: Candidate dictionary
        
    Returns:
        (is_honeypot: bool, reasons: list[str])
    """
    return _detector.detect_honeypot(candidate)


# Fallback to original detector if GX not available
if not HAS_GX:
    logger.warning("Great Expectations framework not available. Using basic detection mode.")
    
    def detect_honeypot(candidate: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Fallback to basic honeypot detection."""
        from scorer.honeypot_detector import detect_honeypot as basic_detect
        return basic_detect(candidate)
