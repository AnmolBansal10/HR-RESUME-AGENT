"""
schemas.py
Pydantic v2 schemas for LLM output validation and data transfer objects.
"""
from typing import Optional
from pydantic import BaseModel, Field, field_validator


# ─── LLM Evaluation Output ────────────────────────────────────────────────────

class DimensionScore(BaseModel):
    score: float = Field(..., ge=0.0, le=10.0)
    justification: str = Field(..., min_length=5, max_length=500)


class LLMEvaluationOutput(BaseModel):
    skills_match: DimensionScore
    experience_relevance: DimensionScore
    education_certifications: DimensionScore
    project_portfolio: DimensionScore
    communication_quality: DimensionScore
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    recommendation: str

    @field_validator("recommendation")
    @classmethod
    def validate_recommendation(cls, v: str) -> str:
        allowed = {"Strong Hire", "Consider", "Do Not Hire"}
        if v not in allowed:
            raise ValueError(f"recommendation must be one of {allowed}, got '{v}'")
        return v

    def compute_weighted_total(self) -> float:
        """Weighted score scaled to 100."""
        return round(
            (
                self.skills_match.score * 0.30
                + self.experience_relevance.score * 0.25
                + self.education_certifications.score * 0.15
                + self.project_portfolio.score * 0.20
                + self.communication_quality.score * 0.10
            )
            * 10,
            2,
        )


# ─── JD + Resume Parsing Schemas ──────────────────────────────────────────────

class ParsedJobDescription(BaseModel):
    title: str
    required_skills: list[str] = []
    preferred_skills: list[str] = []
    experience_years: Optional[int] = None
    education_requirements: list[str] = []
    certifications: list[str] = []
    key_responsibilities: list[str] = []
    industry_domain: Optional[str] = None


class ParsedResume(BaseModel):
    candidate_name: str = "Unknown"
    skills: list[str] = []
    total_experience_years: Optional[float] = None
    education: list[str] = []
    certifications: list[str] = []
    projects: list[str] = []
    work_history: list[str] = []
    summary: Optional[str] = None


# ─── Override DTO ─────────────────────────────────────────────────────────────

class OverrideDTO(BaseModel):
    evaluation_id: int
    override_score: float = Field(..., ge=0.0, le=100.0)
    override_recommendation: str
    reason: str = Field(..., min_length=10)

    @field_validator("override_recommendation")
    @classmethod
    def validate_rec(cls, v: str) -> str:
        allowed = {"Strong Hire", "Consider", "Do Not Hire"}
        if v not in allowed:
            raise ValueError(f"Must be one of {allowed}")
        return v


# ─── Result DTO ───────────────────────────────────────────────────────────────

class EvaluationResult(BaseModel):
    evaluation_id: int
    candidate_id: int
    candidate_name: str
    original_filename: str

    skills_match_score: float
    experience_relevance_score: float
    education_certifications_score: float
    project_portfolio_score: float
    communication_quality_score: float

    skills_match_justification: str
    experience_relevance_justification: str
    education_certifications_justification: str
    project_portfolio_justification: str
    communication_quality_justification: str

    weighted_total: float
    confidence_score: float
    recommendation: str

    is_overridden: bool
    override_score: Optional[float]
    override_recommendation: Optional[str]
    is_fallback: bool

    # Effective values (post-override)
    @property
    def effective_score(self) -> float:
        return self.override_score if self.is_overridden and self.override_score is not None else self.weighted_total

    @property
    def effective_recommendation(self) -> str:
        return self.override_recommendation if self.is_overridden and self.override_recommendation else self.recommendation

    class Config:
        from_attributes = True
