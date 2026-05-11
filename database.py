"""
database.py
SQLAlchemy ORM models using synchronous SQLite engine.
Streamlit runs in a single thread — sync engine is simpler and more compatible.
"""
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, JSON, String, Text, create_engine
)
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker

from config import get_settings

settings = get_settings()

# Use synchronous SQLite (no aiosqlite needed for Streamlit)
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    echo=settings.debug,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


# ─── ORM Models ───────────────────────────────────────────────────────────────

class JobDescription(Base):
    __tablename__ = "job_descriptions"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    raw_text = Column(Text, nullable=False)
    structured_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    candidates = relationship("Candidate", back_populates="job_description", cascade="all, delete-orphan")


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    job_description_id = Column(Integer, ForeignKey("job_descriptions.id"), nullable=False)
    original_filename = Column(String(255), nullable=False)
    candidate_name = Column(String(255), nullable=True)
    parsed_resume = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    job_description = relationship("JobDescription", back_populates="candidates")
    evaluation = relationship("Evaluation", back_populates="candidate", uselist=False, cascade="all, delete-orphan")


class Evaluation(Base):
    __tablename__ = "evaluations"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    raw_llm_response = Column(Text, nullable=True)

    # Dimension scores (0–10)
    skills_match_score = Column(Float, nullable=False, default=0.0)
    experience_relevance_score = Column(Float, nullable=False, default=0.0)
    education_certifications_score = Column(Float, nullable=False, default=0.0)
    project_portfolio_score = Column(Float, nullable=False, default=0.0)
    communication_quality_score = Column(Float, nullable=False, default=0.0)

    # One-line justifications
    skills_match_justification = Column(Text, nullable=True)
    experience_relevance_justification = Column(Text, nullable=True)
    education_certifications_justification = Column(Text, nullable=True)
    project_portfolio_justification = Column(Text, nullable=True)
    communication_quality_justification = Column(Text, nullable=True)

    # Aggregated
    weighted_total = Column(Float, nullable=False, default=0.0)
    confidence_score = Column(Float, nullable=False, default=0.0)
    recommendation = Column(String(50), nullable=False, default="Do Not Hire")

    # Override fields
    is_overridden = Column(Boolean, default=False)
    override_score = Column(Float, nullable=True)
    override_recommendation = Column(String(50), nullable=True)

    # Fallback flag (True when LLM output was invalid and defaults were used)
    is_fallback = Column(Boolean, default=False)

    candidate = relationship("Candidate", back_populates="evaluation")
    overrides = relationship("Override", back_populates="evaluation", cascade="all, delete-orphan")


class Override(Base):
    __tablename__ = "overrides"

    id = Column(Integer, primary_key=True, index=True)
    evaluation_id = Column(Integer, ForeignKey("evaluations.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    override_score = Column(Float, nullable=False)
    override_recommendation = Column(String(50), nullable=False)
    reason = Column(Text, nullable=False)
    hr_session_id = Column(String(100), nullable=True)

    evaluation = relationship("Evaluation", back_populates="overrides")


# ─── DB Lifecycle ─────────────────────────────────────────────────────────────

def init_db():
    """Create all tables if they don't exist."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Context-manager style DB session for use outside Streamlit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
