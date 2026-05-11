"""
streamlit_app.py
HR Resume Shortlisting Agent — Streamlit Dashboard
Run: streamlit run streamlit_app.py
"""
import os
import sys
import time
import uuid
import logging

import streamlit as st
from sqlalchemy.orm import Session

# ─── Path fix for Colab / flat structure ──────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

from database import SessionLocal, init_db
from evaluation_service import (
    apply_override,
    get_all_jds,
    get_overrides_for_eval,
    get_results_for_jd,
    ingest_job_description,
    process_resume,
)
from schemas import EvaluationResult, OverrideDTO
from config import get_settings

logging.basicConfig(level=logging.INFO)
settings = get_settings()

# ─── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="HR Shortlisting Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Global CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* General */
[data-testid="stAppViewContainer"] { background: #f8fafc; }
[data-testid="stSidebar"] { background: #1e293b; }
[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
[data-testid="stSidebar"] .stMarkdown h1,
[data-testid="stSidebar"] .stMarkdown h2,
[data-testid="stSidebar"] .stMarkdown h3 { color: #f1f5f9 !important; }
[data-testid="stSidebar"] hr { border-color: #334155; }

/* Cards */
.hr-card {
    background: white;
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    border: 1px solid #e2e8f0;
    box-shadow: 0 1px 3px rgba(0,0,0,.06);
    margin-bottom: 1rem;
}

/* Metric chips */
.metric-row { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 1rem; }
.metric-chip {
    background: white;
    border-radius: 10px;
    border: 1px solid #e2e8f0;
    padding: .6rem 1rem;
    text-align: center;
    flex: 1;
    min-width: 120px;
    box-shadow: 0 1px 2px rgba(0,0,0,.04);
}
.metric-chip .val { font-size: 1.75rem; font-weight: 700; color: #1e293b; }
.metric-chip .lbl { font-size: .72rem; color: #64748b; text-transform: uppercase; letter-spacing: .04em; }

/* Badge */
.badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: .78rem;
    font-weight: 600;
    white-space: nowrap;
}
.badge-strong  { background: #dcfce7; color: #166534; border: 1px solid #bbf7d0; }
.badge-consider{ background: #fef9c3; color: #854d0e; border: 1px solid #fde68a; }
.badge-no      { background: #fee2e2; color: #991b1b; border: 1px solid #fecaca; }
.badge-override{ background: #ede9fe; color: #5b21b6; border: 1px solid #ddd6fe; }
.badge-fallback{ background: #ffedd5; color: #9a3412; border: 1px solid #fed7aa; }

/* Score bar */
.score-bar-wrap { background: #f1f5f9; border-radius: 6px; height: 8px; overflow: hidden; margin: 4px 0 2px; }
.score-bar { height: 100%; border-radius: 6px; transition: width .4s; }
.bar-green  { background: linear-gradient(90deg,#22c55e,#16a34a); }
.bar-yellow { background: linear-gradient(90deg,#eab308,#ca8a04); }
.bar-red    { background: linear-gradient(90deg,#ef4444,#dc2626); }

/* Rank bubble */
.rank-bubble {
    display: inline-flex;
    width: 28px; height: 28px;
    border-radius: 50%;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: .82rem;
}
.rank-1 { background:#fef9c3; color:#854d0e; }
.rank-2 { background:#f1f5f9; color:#475569; }
.rank-3 { background:#fff7ed; color:#9a3412; }
.rank-n { background:#f8fafc; color:#94a3b8; }

/* Candidate card */
.cand-card {
    background: white;
    border-radius: 12px;
    border: 1px solid #e2e8f0;
    padding: 1rem 1.25rem;
    margin-bottom: .75rem;
    box-shadow: 0 1px 2px rgba(0,0,0,.04);
}
.cand-name { font-size: 1rem; font-weight: 600; color: #1e293b; }
.cand-file { font-size: .78rem; color: #94a3b8; margin-top: 1px; }

/* Divider */
.dim-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px,1fr)); gap: 10px; margin-top: .75rem; }
.dim-box {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: .75rem;
}
.dim-label { font-size: .7rem; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: .04em; }
.dim-score { font-size: 1.4rem; font-weight: 700; margin: 2px 0; }
.dim-just  { font-size: .75rem; color: #64748b; line-height: 1.4; }
.score-green  { color: #16a34a; }
.score-yellow { color: #ca8a04; }
.score-red    { color: #dc2626; }

/* Section header */
.section-hdr {
    font-size: .75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .06em;
    color: #94a3b8;
    margin: 1.25rem 0 .5rem;
}

/* Override log row */
.ov-row {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: .6rem .9rem;
    font-size: .8rem;
    color: #475569;
    margin-bottom: .4rem;
}
</style>
""", unsafe_allow_html=True)


# ─── DB Session ───────────────────────────────────────────────────────────────

@st.cache_resource
def initialise_db():
    init_db()
    return True

initialise_db()


def get_session() -> Session:
    return SessionLocal()


# ─── Session State ────────────────────────────────────────────────────────────

if "current_jd_id" not in st.session_state:
    st.session_state.current_jd_id = None
if "hr_session" not in st.session_state:
    st.session_state.hr_session = str(uuid.uuid4())[:8]
if "eval_results" not in st.session_state:
    st.session_state.eval_results = []
if "active_tab" not in st.session_state:
    st.session_state.active_tab = "upload"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def rec_badge(rec: str) -> str:
    if rec == "Strong Hire":
        return f'<span class="badge badge-strong">✓ {rec}</span>'
    if rec == "Consider":
        return f'<span class="badge badge-consider">~ {rec}</span>'
    return f'<span class="badge badge-no">✗ {rec}</span>'


def score_color_class(score: float, out_of_10: bool = True) -> str:
    threshold = (7, 4) if out_of_10 else (70, 40)
    if score >= threshold[0]:
        return "score-green"
    if score >= threshold[1]:
        return "score-yellow"
    return "score-red"


def bar_class(score: float, out_of_10: bool = True) -> str:
    threshold = (7, 4) if out_of_10 else (70, 40)
    if score >= threshold[0]:
        return "bar-green"
    if score >= threshold[1]:
        return "bar-yellow"
    return "bar-red"


def render_score_bar(score: float, max_val: float = 10.0):
    pct = (score / max_val) * 100
    cls = bar_class(score, out_of_10=(max_val == 10))
    st.markdown(
        f'<div class="score-bar-wrap"><div class="score-bar {cls}" style="width:{pct}%"></div></div>',
        unsafe_allow_html=True,
    )


def rank_bubble(i: int) -> str:
    css = {1: "rank-1", 2: "rank-2", 3: "rank-3"}.get(i, "rank-n")
    return f'<span class="rank-bubble {css}">{i}</span>'


# ─── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🤖 HR Agent")
    st.markdown("AI-powered resume shortlisting")
    st.markdown("---")

    st.markdown("### Navigation")
    if st.button("📤  Upload & Evaluate", use_container_width=True):
        st.session_state.active_tab = "upload"
        st.rerun()
    if st.button("📊  View Results", use_container_width=True,
                 disabled=not st.session_state.eval_results):
        st.session_state.active_tab = "results"
        st.rerun()

    st.markdown("---")
    st.markdown("### Past Evaluations")

    db = get_session()
    jd_list = get_all_jds(db)
    db.close()

    if jd_list:
        for jd in jd_list[:10]:
            label = f"📄 {jd.title[:28]}{'…' if len(jd.title)>28 else ''}"
            if st.button(label, key=f"jd_{jd.id}", use_container_width=True):
                db2 = get_session()
                st.session_state.eval_results = get_results_for_jd(db2, jd.id)
                st.session_state.current_jd_id = jd.id
                db2.close()
                st.session_state.active_tab = "results"
                st.rerun()
    else:
        st.caption("No evaluations yet.")

    st.markdown("---")
    st.markdown("### Scoring Rubric")
    rubric = [
        ("Skills Match", "30%"),
        ("Experience", "25%"),
        ("Projects", "20%"),
        ("Education", "15%"),
        ("Communication", "10%"),
    ]
    for name, weight in rubric:
        st.markdown(
            f"<div style='display:flex;justify-content:space-between;font-size:.8rem;"
            f"padding:2px 0'><span>{name}</span><strong>{weight}</strong></div>",
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown(
        "<div style='font-size:.72rem;color:#64748b'>"
        "🔒 PII masked before storage<br>"
        "🛡 Prompt injection mitigated<br>"
        "🔁 LLM retry + fallback active"
        "</div>",
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════════
#  TAB: UPLOAD
# ═══════════════════════════════════════════════════════════════════

if st.session_state.active_tab == "upload":

    st.markdown("# 📤 Upload & Evaluate")
    st.markdown("Paste a job description, upload candidate resumes, and let the AI rank them.")

    col_form, col_guide = st.columns([2, 1])

    with col_form:
        with st.form("eval_form", clear_on_submit=False):
            st.markdown('<div class="hr-card">', unsafe_allow_html=True)
            st.markdown("#### 📋 Job Description")

            jd_title = st.text_input(
                "Job Title *",
                placeholder="e.g. Senior Machine Learning Engineer",
            )
            jd_text = st.text_area(
                "Full Job Description *",
                height=260,
                placeholder=(
                    "Paste the complete job description here.\n\n"
                    "Include: required skills, preferred skills, years of experience, "
                    "education requirements, responsibilities, etc."
                ),
            )
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('<div class="hr-card">', unsafe_allow_html=True)
            st.markdown("#### 📁 Resume Files")
            uploaded_files = st.file_uploader(
                "Upload resumes (PDF or DOCX) *",
                type=["pdf", "docx"],
                accept_multiple_files=True,
                help=f"Each file must be under {settings.max_file_size_mb} MB.",
            )
            if uploaded_files:
                st.markdown(f"**{len(uploaded_files)} file(s) selected:**")
                for f in uploaded_files:
                    size_kb = len(f.getvalue()) / 1024
                    icon = "📄" if f.name.endswith(".pdf") else "📝"
                    st.markdown(
                        f"<div style='font-size:.82rem;padding:2px 0;color:#475569'>"
                        f"{icon} {f.name} <span style='color:#94a3b8'>({size_kb:.0f} KB)</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
            st.markdown('</div>', unsafe_allow_html=True)

            submitted = st.form_submit_button(
                "🚀 Evaluate Candidates",
                use_container_width=True,
                type="primary",
            )

        # ── Form processing ──
        if submitted:
            errors_form = []
            if not jd_title.strip():
                errors_form.append("Job title is required.")
            if not jd_text.strip():
                errors_form.append("Job description text is required.")
            if not uploaded_files:
                errors_form.append("Please upload at least one resume.")

            if errors_form:
                for e in errors_form:
                    st.error(e)
            else:
                db = get_session()
                try:
                    # Store JD
                    with st.spinner("📋 Parsing job description..."):
                        jd = ingest_job_description(db, jd_title, jd_text)

                    st.session_state.current_jd_id = jd.id
                    results = []
                    file_errors = []

                    progress_bar = st.progress(0, text="Starting evaluation...")
                    total = len(uploaded_files)

                    for idx, upload in enumerate(uploaded_files):
                        progress_bar.progress(
                            (idx) / total,
                            text=f"Evaluating {upload.name} ({idx+1}/{total})...",
                        )
                        try:
                            file_bytes = upload.getvalue()
                            result = process_resume(
                                db=db,
                                jd=jd,
                                filename=upload.name,
                                file_bytes=file_bytes,
                                max_file_size_mb=settings.max_file_size_mb,
                            )
                            results.append(result)
                        except Exception as ex:
                            file_errors.append({"filename": upload.name, "error": str(ex)})

                    progress_bar.progress(1.0, text="Done!")
                    time.sleep(0.5)
                    progress_bar.empty()

                    st.session_state.eval_results = results

                    if file_errors:
                        for fe in file_errors:
                            st.warning(f"⚠️ **{fe['filename']}**: {fe['error']}")

                    if results:
                        st.success(f"✅ {len(results)} candidate(s) evaluated successfully!")
                        time.sleep(0.8)
                        st.session_state.active_tab = "results"
                        st.rerun()
                    else:
                        st.error("No candidates could be evaluated. Check file formats and try again.")

                finally:
                    db.close()

    with col_guide:
        st.markdown(
            '<div class="hr-card">'
            '<div class="section-hdr">How it works</div>'
            '<ol style="font-size:.85rem;color:#475569;padding-left:1.1rem;line-height:1.8">'
            '<li>Paste full JD text</li>'
            '<li>Upload PDF / DOCX resumes</li>'
            '<li>AI parses & scores each candidate</li>'
            '<li>View ranked shortlist</li>'
            '<li>Override scores if needed</li>'
            '</ol>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="hr-card">'
            '<div class="section-hdr">Recommendations</div>'
            '<div style="font-size:.83rem;line-height:2">'
            '<span class="badge badge-strong">✓ Strong Hire</span> — Score ≥ 75<br>'
            '<span class="badge badge-consider">~ Consider</span> — Score 50–74<br>'
            '<span class="badge badge-no">✗ Do Not Hire</span> — Score &lt; 50'
            '</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="hr-card">'
            '<div class="section-hdr">Security</div>'
            '<ul style="font-size:.78rem;color:#64748b;padding-left:1rem;line-height:1.9">'
            '<li>Prompt injection mitigated</li>'
            '<li>Email &amp; phone masked before DB</li>'
            '<li>File type &amp; size validated</li>'
            '<li>API key loaded from .env only</li>'
            '<li>LLM output Pydantic-validated</li>'
            '<li>Fallback if LLM output invalid</li>'
            '</ul>'
            '</div>',
            unsafe_allow_html=True,
        )


# ═══════════════════════════════════════════════════════════════════
#  TAB: RESULTS
# ═══════════════════════════════════════════════════════════════════

elif st.session_state.active_tab == "results":

    results: list[EvaluationResult] = st.session_state.eval_results

    if not results:
        st.info("No results to display. Upload resumes first.")
        if st.button("← Go to Upload"):
            st.session_state.active_tab = "upload"
            st.rerun()
        st.stop()

    # ── Header ──
    st.markdown("# 📊 Evaluation Results")

    top_col, btn_col = st.columns([4, 1])
    with top_col:
        st.markdown(f"**{len(results)} candidate(s) evaluated** — ranked by effective score")
    with btn_col:
        if st.button("← New Evaluation", use_container_width=True):
            st.session_state.active_tab = "upload"
            st.rerun()

    # ── Summary Metrics ──
    strong  = sum(1 for r in results if r.effective_recommendation == "Strong Hire")
    consider = sum(1 for r in results if r.effective_recommendation == "Consider")
    no_hire = sum(1 for r in results if r.effective_recommendation == "Do Not Hire")
    avg_score = sum(r.effective_score for r in results) / len(results)

    st.markdown(
        f'<div class="metric-row">'
        f'<div class="metric-chip"><div class="val">{len(results)}</div><div class="lbl">Total</div></div>'
        f'<div class="metric-chip"><div class="val" style="color:#16a34a">{strong}</div><div class="lbl">Strong Hire</div></div>'
        f'<div class="metric-chip"><div class="val" style="color:#ca8a04">{consider}</div><div class="lbl">Consider</div></div>'
        f'<div class="metric-chip"><div class="val" style="color:#dc2626">{no_hire}</div><div class="lbl">Do Not Hire</div></div>'
        f'<div class="metric-chip"><div class="val">{avg_score:.1f}</div><div class="lbl">Avg Score</div></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Ranked Table ──
    st.markdown('<div class="section-hdr">Ranked Candidates</div>', unsafe_allow_html=True)

    # Table header
    h_cols = st.columns([0.5, 2.5, 1.5, 1.2, 1, 1.3])
    headers = ["#", "Candidate", "Recommendation", "Score /100", "Confidence", "Actions"]
    for col, hdr in zip(h_cols, headers):
        col.markdown(f"<div style='font-size:.72rem;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em'>{hdr}</div>", unsafe_allow_html=True)

    st.markdown("<hr style='margin:.3rem 0 .6rem;border-color:#e2e8f0'>", unsafe_allow_html=True)

    for i, r in enumerate(results, 1):
        eff_score = r.effective_score
        eff_rec   = r.effective_recommendation

        row_cols = st.columns([0.5, 2.5, 1.5, 1.2, 1, 1.3])

        # Rank
        row_cols[0].markdown(rank_bubble(i), unsafe_allow_html=True)

        # Candidate name + filename
        tags = ""
        if r.is_overridden:
            tags += ' <span class="badge badge-override" style="font-size:.65rem">Overridden</span>'
        if r.is_fallback:
            tags += ' <span class="badge badge-fallback" style="font-size:.65rem">Fallback</span>'
        row_cols[1].markdown(
            f'<div class="cand-name">{r.candidate_name}{tags}</div>'
            f'<div class="cand-file">{r.original_filename}</div>',
            unsafe_allow_html=True,
        )

        # Recommendation
        row_cols[2].markdown(rec_badge(eff_rec), unsafe_allow_html=True)

        # Score + bar
        score_col = row_cols[3]
        score_col.markdown(
            f'<div style="font-size:1.3rem;font-weight:700;{f"color:#16a34a" if eff_score>=75 else ("color:#ca8a04" if eff_score>=50 else "color:#dc2626")}">'
            f'{eff_score:.1f}</div>',
            unsafe_allow_html=True,
        )
        with score_col:
            render_score_bar(eff_score, max_val=100.0)

        # Confidence
        row_cols[4].markdown(
            f'<div style="font-size:.9rem;color:#64748b;padding-top:.3rem">{r.confidence_score*100:.0f}%</div>',
            unsafe_allow_html=True,
        )

        # Action buttons
        with row_cols[5]:
            detail_key = f"detail_{r.evaluation_id}"
            if detail_key not in st.session_state:
                st.session_state[detail_key] = False

            btn_label = "▲ Hide" if st.session_state[detail_key] else "▼ Details"
            if st.button(btn_label, key=f"btn_detail_{r.evaluation_id}", use_container_width=True):
                st.session_state[detail_key] = not st.session_state[detail_key]
                st.rerun()

        # ── Expandable Dimension Details ──
        if st.session_state.get(f"detail_{r.evaluation_id}", False):
            with st.container():
                st.markdown("<div style='background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:1rem 1.25rem;margin:.25rem 0 .75rem'>", unsafe_allow_html=True)

                dims = [
                    ("Skills Match",        r.skills_match_score,               r.skills_match_justification,               "30%"),
                    ("Experience Relevance", r.experience_relevance_score,       r.experience_relevance_justification,       "25%"),
                    ("Project / Portfolio",  r.project_portfolio_score,          r.project_portfolio_justification,          "20%"),
                    ("Education & Certs",    r.education_certifications_score,   r.education_certifications_justification,   "15%"),
                    ("Communication",        r.communication_quality_score,      r.communication_quality_justification,      "10%"),
                ]

                d_cols = st.columns(5)
                for col, (label, score, just, weight) in zip(d_cols, dims):
                    color_cls = score_color_class(score)
                    bar_pct = score * 10
                    b_cls = bar_class(score)
                    col.markdown(
                        f'<div class="dim-box">'
                        f'<div class="dim-label">{label} <span style="color:#cbd5e1">({weight})</span></div>'
                        f'<div class="dim-score {color_cls}">{score:.1f}<span style="font-size:.7rem;color:#94a3b8">/10</span></div>'
                        f'<div class="score-bar-wrap"><div class="score-bar {b_cls}" style="width:{bar_pct}%"></div></div>'
                        f'<div class="dim-just">{just}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                # Override section
                st.markdown("<div class='section-hdr' style='margin-top:.9rem'>Human Override</div>", unsafe_allow_html=True)
                ov_cols = st.columns([1, 1, 2, 1])

                new_score = ov_cols[0].number_input(
                    "New Score (0–100)",
                    min_value=0.0, max_value=100.0,
                    value=float(f"{r.effective_score:.1f}"),
                    step=0.5,
                    key=f"ov_score_{r.evaluation_id}",
                )
                new_rec = ov_cols[1].selectbox(
                    "New Recommendation",
                    ["Strong Hire", "Consider", "Do Not Hire"],
                    index=["Strong Hire", "Consider", "Do Not Hire"].index(r.effective_recommendation),
                    key=f"ov_rec_{r.evaluation_id}",
                )
                new_reason = ov_cols[2].text_input(
                    "Reason * (min 10 chars)",
                    placeholder="Explain why you are overriding this score...",
                    key=f"ov_reason_{r.evaluation_id}",
                )

                with ov_cols[3]:
                    st.markdown("<div style='height:1.6rem'></div>", unsafe_allow_html=True)
                    if st.button("💾 Save Override", key=f"ov_save_{r.evaluation_id}", use_container_width=True):
                        if len(new_reason.strip()) < 10:
                            st.error("Reason must be at least 10 characters.")
                        else:
                            db = get_session()
                            try:
                                dto = OverrideDTO(
                                    evaluation_id=r.evaluation_id,
                                    override_score=new_score,
                                    override_recommendation=new_rec,
                                    reason=new_reason.strip(),
                                )
                                apply_override(db, dto, st.session_state.hr_session)
                                # Refresh results
                                if st.session_state.current_jd_id:
                                    st.session_state.eval_results = get_results_for_jd(
                                        db, st.session_state.current_jd_id
                                    )
                                st.success("✅ Override saved and logged.")
                                time.sleep(0.8)
                                st.rerun()
                            except Exception as ex:
                                st.error(f"Override failed: {ex}")
                            finally:
                                db.close()

                # Override log
                db_log = get_session()
                overrides = get_overrides_for_eval(db_log, r.evaluation_id)
                db_log.close()

                if overrides:
                    st.markdown("<div class='section-hdr'>Override History</div>", unsafe_allow_html=True)
                    for ov in overrides:
                        ts = ov.timestamp.strftime("%Y-%m-%d %H:%M UTC")
                        st.markdown(
                            f'<div class="ov-row">'
                            f'🕐 <strong>{ts}</strong> · '
                            f'Score → <strong>{ov.override_score:.1f}</strong> · '
                            f'Rec → <strong>{ov.override_recommendation}</strong> · '
                            f'Reason: {ov.reason}'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

                st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<hr style='margin:.3rem 0;border-color:#f1f5f9'>", unsafe_allow_html=True)

    # ── Score Distribution Chart ──
    st.markdown('<div class="section-hdr" style="margin-top:1.5rem">Score Distribution</div>', unsafe_allow_html=True)

    try:
        import pandas as pd
        import altair as alt

        chart_data = pd.DataFrame([
            {
                "Candidate": r.candidate_name[:20],
                "Score": r.effective_score,
                "Recommendation": r.effective_recommendation,
            }
            for r in results
        ]).sort_values("Score", ascending=False)

        color_map = {
            "Strong Hire": "#22c55e",
            "Consider":    "#eab308",
            "Do Not Hire": "#ef4444",
        }

        chart = (
            alt.Chart(chart_data)
            .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
            .encode(
                x=alt.X("Candidate:N", sort="-y", axis=alt.Axis(labelAngle=-30, labelFontSize=11)),
                y=alt.Y("Score:Q", scale=alt.Scale(domain=[0, 100]), title="Weighted Score / 100"),
                color=alt.Color(
                    "Recommendation:N",
                    scale=alt.Scale(
                        domain=list(color_map.keys()),
                        range=list(color_map.values()),
                    ),
                    legend=alt.Legend(title="Recommendation"),
                ),
                tooltip=["Candidate", "Score", "Recommendation"],
            )
            .properties(height=260)
        )

        # Threshold lines
        lines = (
            alt.Chart(pd.DataFrame([{"y": 75, "label": "Strong Hire ≥75"}, {"y": 50, "label": "Consider ≥50"}]))
            .mark_rule(strokeDash=[4, 4], opacity=0.5)
            .encode(y="y:Q", color=alt.value("#94a3b8"))
        )

        st.altair_chart(chart + lines, use_container_width=True)

    except ImportError:
        st.info("Install `altair` and `pandas` to see the score chart.")

    # ── Radar-style dimension comparison ──
    st.markdown('<div class="section-hdr">Dimension Breakdown (Top 5)</div>', unsafe_allow_html=True)

    try:
        import pandas as pd

        dim_names = ["Skills", "Experience", "Education", "Projects", "Communication"]
        dim_data = []
        for r in results[:5]:
            dim_data.append({
                "Candidate": r.candidate_name[:18],
                "Skills":        r.skills_match_score * 10,
                "Experience":    r.experience_relevance_score * 10,
                "Education":     r.education_certifications_score * 10,
                "Projects":      r.project_portfolio_score * 10,
                "Communication": r.communication_quality_score * 10,
            })

        df = pd.DataFrame(dim_data).set_index("Candidate")
        st.dataframe(
            df.style.background_gradient(cmap="RdYlGn", vmin=0, vmax=100)
              .format("{:.1f}"),
            use_container_width=True,
        )
    except ImportError:
        st.info("Install `pandas` to see the dimension breakdown table.")
