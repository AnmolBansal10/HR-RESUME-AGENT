"""
evaluation_service.py
Orchestrates the full pipeline:
  file validation → text extraction → LLM parse → LLM evaluate → DB write → result DTO
Also handles override logging and result retrieval.
"""
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from database import Candidate, Evaluation, JobDescription, Override
from file_parser import extract_text, is_valid_extension, is_valid_size, mask_pii
from llm_service import evaluate_candidate, parse_job_description, parse_resume
from schemas import EvaluationResult, OverrideDTO

logger = logging.getLogger(__name__)


# ─── JD Ingestion ─────────────────────────────────────────────────────────────

def ingest_job_description(db: Session, title: str, jd_text: str) -> JobDescription:
    parsed = parse_job_description(jd_text)
    jd = JobDescription(
        title=title.strip(),
        raw_text=jd_text.strip(),
        structured_data=parsed.model_dump() if parsed else {},
    )
    db.add(jd)
    db.commit()
    db.refresh(jd)
    logger.info("Stored JD id=%d title=%s", jd.id, jd.title)
    return jd


# ─── Resume Pipeline ──────────────────────────────────────────────────────────

def process_resume(
    db: Session,
    jd: JobDescription,
    filename: str,
    file_bytes: bytes,
    max_file_size_mb: int,
) -> EvaluationResult:
    """Full pipeline for a single resume file."""

    # 1. Validate
    if not is_valid_extension(filename):
        raise ValueError(f"Unsupported file type: {filename}. Only PDF and DOCX allowed.")
    if not is_valid_size(file_bytes, max_file_size_mb):
        raise ValueError(f"{filename} exceeds {max_file_size_mb} MB limit.")

    # 2. Extract text
    resume_text = extract_text(filename, file_bytes)
    if not resume_text.strip():
        raise ValueError(f"Could not extract any text from {filename}.")

    # 3. Parse resume via LLM
    parsed_resume = parse_resume(resume_text)
    resume_dict = parsed_resume.model_dump() if parsed_resume else {}
    candidate_name = parsed_resume.candidate_name if parsed_resume else "Unknown"

    # 4. Store candidate (PII masked in stored text)
    candidate = Candidate(
        job_description_id=jd.id,
        original_filename=filename,
        candidate_name=candidate_name,
        parsed_resume=resume_dict,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    # 5. Evaluate against JD
    masked_text = mask_pii(resume_text)
    eval_output, raw_response, is_fallback = evaluate_candidate(
        jd_structured=jd.structured_data or {},
        resume_structured=resume_dict,
        resume_raw_text=masked_text,
    )
    weighted_total = eval_output.compute_weighted_total()

    # 6. Store evaluation
    evaluation = Evaluation(
        candidate_id=candidate.id,
        timestamp=datetime.utcnow(),
        raw_llm_response=raw_response[:10_000],
        skills_match_score=eval_output.skills_match.score,
        experience_relevance_score=eval_output.experience_relevance.score,
        education_certifications_score=eval_output.education_certifications.score,
        project_portfolio_score=eval_output.project_portfolio.score,
        communication_quality_score=eval_output.communication_quality.score,
        skills_match_justification=eval_output.skills_match.justification,
        experience_relevance_justification=eval_output.experience_relevance.justification,
        education_certifications_justification=eval_output.education_certifications.justification,
        project_portfolio_justification=eval_output.project_portfolio.justification,
        communication_quality_justification=eval_output.communication_quality.justification,
        weighted_total=weighted_total,
        confidence_score=eval_output.confidence_score,
        recommendation=eval_output.recommendation,
        is_fallback=is_fallback,
    )
    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)

    return _to_dto(candidate, evaluation)


# ─── Retrieval ────────────────────────────────────────────────────────────────

def get_all_jds(db: Session) -> list[JobDescription]:
    return db.query(JobDescription).order_by(JobDescription.created_at.desc()).all()


def get_results_for_jd(db: Session, jd_id: int) -> list[EvaluationResult]:
    candidates = (
        db.query(Candidate)
        .filter(Candidate.job_description_id == jd_id)
        .all()
    )
    results = []
    for c in candidates:
        if c.evaluation:
            results.append(_to_dto(c, c.evaluation))

    results.sort(
        key=lambda r: r.effective_score,
        reverse=True,
    )
    return results


# ─── Override ─────────────────────────────────────────────────────────────────

def apply_override(db: Session, dto: OverrideDTO, hr_session: str = "anonymous") -> Override:
    evaluation = db.query(Evaluation).filter(Evaluation.id == dto.evaluation_id).first()
    if not evaluation:
        raise ValueError(f"Evaluation {dto.evaluation_id} not found.")

    evaluation.is_overridden = True
    evaluation.override_score = dto.override_score
    evaluation.override_recommendation = dto.override_recommendation

    override = Override(
        evaluation_id=evaluation.id,
        override_score=dto.override_score,
        override_recommendation=dto.override_recommendation,
        reason=dto.reason,
        hr_session_id=hr_session,
    )
    db.add(override)
    db.commit()
    db.refresh(override)
    logger.info("Override id=%d applied to eval_id=%d", override.id, evaluation.id)
    return override


def get_overrides_for_eval(db: Session, eval_id: int) -> list[Override]:
    return (
        db.query(Override)
        .filter(Override.evaluation_id == eval_id)
        .order_by(Override.timestamp.desc())
        .all()
    )


# ─── Internal Helper ──────────────────────────────────────────────────────────

def _to_dto(candidate: Candidate, evaluation: Evaluation) -> EvaluationResult:
    return EvaluationResult(
        evaluation_id=evaluation.id,
        candidate_id=candidate.id,
        candidate_name=candidate.candidate_name or "Unknown",
        original_filename=candidate.original_filename,
        skills_match_score=evaluation.skills_match_score,
        experience_relevance_score=evaluation.experience_relevance_score,
        education_certifications_score=evaluation.education_certifications_score,
        project_portfolio_score=evaluation.project_portfolio_score,
        communication_quality_score=evaluation.communication_quality_score,
        skills_match_justification=evaluation.skills_match_justification or "",
        experience_relevance_justification=evaluation.experience_relevance_justification or "",
        education_certifications_justification=evaluation.education_certifications_justification or "",
        project_portfolio_justification=evaluation.project_portfolio_justification or "",
        communication_quality_justification=evaluation.communication_quality_justification or "",
        weighted_total=evaluation.weighted_total,
        confidence_score=evaluation.confidence_score,
        recommendation=evaluation.recommendation,
        is_overridden=evaluation.is_overridden,
        override_score=evaluation.override_score,
        override_recommendation=evaluation.override_recommendation,
        is_fallback=evaluation.is_fallback,
    )
