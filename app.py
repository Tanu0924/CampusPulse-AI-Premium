from __future__ import annotations
import os
from pathlib import Path
import pandas as pd
import streamlit as st
import altair as alt
from core import canonicalize, inspect_schema, data_quality_report, plan_question, validate_sql, execute_readonly

APP_NAME = "CampusPulse AI"
SAMPLE_PATH = Path(__file__).parent / "sample_data" / "students.csv"
st.set_page_config(page_title=APP_NAME, page_icon="🎓", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
:root { --cp-blue:#1769e0; --cp-ink:#172033; --cp-muted:#687386; --cp-line:#e4e9f1; }
html, body, [class*="css"] { font-family:'DM Sans',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; }
.block-container { max-width:1500px; padding-top:1.5rem; padding-bottom:3rem; }
[data-testid="stSidebar"] { border-right:1px solid var(--cp-line); }
[data-testid="stMetric"] { border:1px solid var(--cp-line); border-radius:17px; padding:16px 18px; background:linear-gradient(145deg,#fff,#fbfcff); }
[data-testid="stMetricLabel"] { color:#687386; font-weight:600; }
.hero { padding:2.2rem 2.3rem; border:1px solid #e3eaf5; border-radius:26px; background:radial-gradient(circle at 85% 0%,#e7f1ff 0,transparent 33%),linear-gradient(135deg,#fff 0%,#f8fbff 100%); margin-bottom:1.35rem; }
.eyebrow { text-transform:uppercase; letter-spacing:.16em; font-size:.72rem; font-weight:800; color:#1769e0; }
.hero h1 { font-family:'Manrope',sans-serif; font-weight:800; font-size:clamp(2rem,4vw,3.3rem); line-height:1.08; letter-spacing:-.055em; color:#121a2a; margin:.7rem 0 .65rem; }
.hero p { color:#5f6b7c; max-width:780px; font-size:1rem; line-height:1.7; margin:0; }
.section-card { padding:1rem 1.15rem; border:1px solid var(--cp-line); border-radius:18px; background:white; }
.pill { display:inline-block; padding:.32rem .65rem; border-radius:999px; background:#eaf2ff; color:#1554a5; font-size:.74rem; font-weight:700; }
.small-muted { color:#687386; font-size:.86rem; }
div.stButton>button, div.stDownloadButton>button { border-radius:11px; font-weight:700; min-height:2.65rem; }
div[data-testid="stTabs"] button { font-weight:650; }
[data-testid="stDataFrame"] { border:1px solid #e4e9f1; border-radius:12px; overflow:hidden; }
hr { border-color:#e9edf4; }
@media (max-width:700px) { .hero { padding:1.35rem; } .block-container { padding-left:1rem; padding-right:1rem; } }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## 🎓 CampusPulse AI")
    st.caption("Faculty intelligence workspace")
    uploaded = st.file_uploader("Upload student dataset", type=["csv"], help="CSV stays in this Streamlit session. Avoid uploading identifiable real student data to a public demo.")
    use_sample = st.toggle("Use synthetic demo data", value=uploaded is None)
    st.divider()
    st.markdown("### Workspace")
    st.caption("A transparent, data-backed assistant for faculty review.")
    st.markdown("### Privacy note")
    st.caption("This portfolio prototype is not an official university system. It has no user authentication or production access controls.")
    st.markdown("### AI status")
    st.info("Deterministic intent mode", icon="🧭")
    st.caption("Only implemented query patterns are answered. Unsupported questions are explained rather than guessed.")

st.markdown("""
<div class="hero">
 <div class="eyebrow">UNIVERSITY INTELLIGENCE · FACULTY FIRST</div>
 <h1>From student data<br>to confident decisions.</h1>
 <p>Meet CampusPulse AI — a transparent faculty copilot for exploring attendance, assessment outcomes and academic progress. Ask in plain language, inspect the SQL, verify the records and export what you need.</p>
</div>
""", unsafe_allow_html=True)

@st.cache_data
def read_sample():
    return pd.read_csv(SAMPLE_PATH)

try:
    if uploaded is not None:
        raw = pd.read_csv(uploaded, encoding_errors="replace")
        dataset_label = uploaded.name
        is_synthetic = False
    elif use_sample:
        raw = read_sample()
        dataset_label = "Synthetic demonstration dataset"
        is_synthetic = True
    else:
        raw = pd.DataFrame()
        dataset_label = "No dataset loaded"
        is_synthetic = False
except Exception as exc:
    st.error(f"Could not read the CSV. Check the file format and try again. Details: {exc}")
    st.stop()

if raw.empty:
    st.info("Upload a CSV or enable the synthetic demo dataset to begin.")
    st.stop()

df = canonicalize(raw)
if "student_id" not in df.columns:
    st.warning("No student ID column was detected. A row identifier will be shown for this session only.")
    df.insert(0, "student_id", [f"ROW-{i+1:03d}" for i in range(len(df))])
if "name" not in df.columns:
    df["name"] = "Student " + df["student_id"].astype(str)

st.markdown(f'<span class="pill">{"SYNTHETIC DEMO DATA" if is_synthetic else "UPLOADED DATASET"}</span> &nbsp; <span class="small-muted">{dataset_label} · {len(df):,} rows · {len(df.columns)} columns</span>', unsafe_allow_html=True)

# Dataset-wide filters are intentionally explicit and apply to the data used by analytics.
filtered = df.copy()
with st.expander("Filter the workspace", expanded=False):
    f1, f2, f3 = st.columns(3)
    if "department" in df.columns:
        options = sorted(df["department"].dropna().astype(str).unique().tolist())
        chosen = f1.multiselect("Department", options, default=options)
        filtered = filtered[filtered["department"].astype(str).isin(chosen)]
    if "semester" in df.columns:
        sems = sorted(df["semester"].dropna().unique().tolist())
        chosen_sem = f2.multiselect("Semester", sems, default=sems)
        filtered = filtered[filtered["semester"].isin(chosen_sem)]
    if "course" in df.columns:
        courses = sorted(df["course"].dropna().astype(str).unique().tolist())
        chosen_course = f3.multiselect("Course", courses, default=courses)
        filtered = filtered[filtered["course"].astype(str).isin(chosen_course)]

c1,c2,c3,c4 = st.columns(4)
c1.metric("Student records", f"{len(filtered):,}", help="Rows after workspace filters")
if "attendance_pct" in filtered.columns:
    c2.metric("Average attendance", f"{filtered['attendance_pct'].mean():.1f}%" if filtered["attendance_pct"].notna().any() else "—")
else: c2.metric("Attendance", "Not available")
if "overall_marks" in filtered.columns:
    c3.metric("Average marks", f"{filtered['overall_marks'].mean():.1f}" if filtered["overall_marks"].notna().any() else "—")
else: c3.metric("Overall marks", "Not available")
if "exam_status" in filtered.columns:
    statuses = filtered["exam_status"].astype(str).str.strip().str.lower()
    c4.metric("Recorded exam absences", f"{statuses.isin(['absent','not appeared','not_attempted','no','false','0']).sum():,}")
else: c4.metric("Exam status", "Not available")

tab_ask, tab_insights, tab_quality, tab_schema = st.tabs(["✦ Ask CampusPulse", "Analytics", "Data quality", "Dataset schema"])

def set_question(example: str):
    st.session_state["question_input"] = example

with tab_ask:
    left, right = st.columns([1.6,1], gap="large")
    with left:
        st.subheader("Ask your dataset")
        st.caption("Try a supported question. Results are computed from the active data, not generated as sample answers.")
        question = st.text_area("Natural-language question", placeholder="e.g. Which students have attendance below 60%?", height=100, label_visibility="collapsed", key="question_input")
        run = st.button("Run analysis  →", type="primary", use_container_width=True)
        st.markdown("**Quick starts**")
        examples = [
            "Show the top 5 students by overall marks",
            "Which students have attendance below 60%?",
            "Which students have attendance above 90%?",
            "Which students have not submitted the quiz?",
            "Who got full marks in the quiz?",
            "Which students were absent from the end-semester exam?",
            "Find students with low attendance and low marks",
            "Show average attendance by department",
            "Find students with missing grades",
            "Find students with multiple failed courses",
        ]
        cols = st.columns(2)
        for i, example in enumerate(examples):
            cols[i % 2].button(example, key=f"example_{i}", use_container_width=True,
                               on_click=set_question, args=(example,))
    with right:
        st.markdown("#### How it works")
        st.markdown("""
        <div class="section-card">
          <p><b>01 · Understand</b><br><span class="small-muted">Detect the intent and required columns.</span></p>
          <p><b>02 · Validate</b><br><span class="small-muted">Approve only a single read-only query.</span></p>
          <p><b>03 · Execute</b><br><span class="small-muted">Run against the current dataset in SQLite.</span></p>
          <p><b>04 · Explain</b><br><span class="small-muted">Show assumptions, matching rows and export options.</span></p>
        </div>
        """, unsafe_allow_html=True)
        st.caption("Keyboard-friendly · SQL visible · Human-reviewed support flags")

    if run:
        q = question.strip()
        if not q:
            st.warning("Enter a question or choose a quick start.")
        else:
            plan = plan_question(q, list(filtered.columns))
            if plan is None:
                st.warning("I can’t safely answer that question yet. Try one of the supported examples, or check whether the dataset contains the required columns.")
                st.session_state["last_result"] = None
            elif plan.mode == "unsupported":
                st.warning(plan.explanation)
                st.session_state["last_result"] = None
            elif plan.mode == "quality":
                st.info(plan.explanation)
                st.session_state["last_result"] = None
            else:
                try:
                    safe_sql = validate_sql(plan.sql, list(filtered.columns))
                    result_df = execute_readonly(filtered, safe_sql)
                    st.session_state["last_result"] = {
                        "question": q, "title": plan.title, "sql": safe_sql,
                        "explanation": plan.explanation, "result": result_df,
                        "dataset": dataset_label, "count": len(result_df)
                    }
                    history = st.session_state.get("query_history", [])
                    history.insert(0, {"Question": q, "Intent": plan.title, "Rows": len(result_df), "Dataset": dataset_label})
                    st.session_state["query_history"] = history[:12]
                except Exception as exc:
                    st.error(f"Analysis could not be completed. Check the dataset columns and try again. Details: {exc}")

    last = st.session_state.get("last_result")
    if last:
        st.divider()
        st.markdown(f"### {last['title']}")
        st.caption(f"Executed successfully · {last['count']:,} result rows · Dataset: {last['dataset']}")
        st.info(last["explanation"], icon="ℹ️")
        if last["result"].empty:
            st.warning("No matching records were found. This is a valid result, not an error.")
        else:
            st.dataframe(last["result"], use_container_width=True, hide_index=True)
            st.download_button("Download results as CSV", last["result"].to_csv(index=False).encode("utf-8-sig"),
                               file_name="campuspulse_results.csv", mime="text/csv")
        with st.expander("Inspect SQL"):
            st.code(last["sql"], language="sql")
            st.caption("Status: validated and executed against the active in-memory SQLite dataset.")
    with st.expander("Recent query history", expanded=False):
        history = st.session_state.get("query_history", [])
        if history: st.dataframe(pd.DataFrame(history), use_container_width=True, hide_index=True)
        else: st.caption("Queries you run in this session will appear here. History is not persisted.")

with tab_insights:
    st.subheader("Analytics overview")
    st.caption("Charts are generated from the active filtered dataset. Missing values are excluded from numeric summaries.")
    chart_cols = st.columns(2)
    if "attendance_pct" in filtered.columns and filtered["attendance_pct"].notna().any():
        attendance_bins = pd.cut(filtered["attendance_pct"], bins=[-0.001, 60, 75, 90, 100.001],
                                 labels=["Below 60%", "60–75%", "75–90%", "Above 90%"]).value_counts(sort=False).rename_axis("Attendance band").reset_index(name="Students")
        chart_cols[0].altair_chart(alt.Chart(attendance_bins).mark_bar(cornerRadiusTopLeft=5, cornerRadiusTopRight=5).encode(
            x=alt.X("Attendance band:N", sort=None, title=None), y=alt.Y("Students:Q", title="Student records"),
            tooltip=["Attendance band", "Students"]).properties(height=280, title="Attendance distribution"), use_container_width=True)
    else: chart_cols[0].info("Attendance chart unavailable: no attendance column with numeric values.")
    if "overall_marks" in filtered.columns and filtered["overall_marks"].notna().any():
        marks = filtered[["overall_marks"]].dropna().copy()
        chart_cols[1].altair_chart(alt.Chart(marks).mark_bar(color="#1769e0", cornerRadiusTopLeft=5, cornerRadiusTopRight=5).encode(
            x=alt.X("overall_marks:Q", bin=alt.Bin(maxbins=10), title="Overall marks"),
            y=alt.Y("count():Q", title="Student records"), tooltip=[alt.Tooltip("count():Q", title="Students")]).properties(height=280, title="Marks distribution"), use_container_width=True)
    else: chart_cols[1].info("Marks chart unavailable: no numeric overall marks column.")
    if "department" in filtered.columns and "attendance_pct" in filtered.columns:
        summary = filtered.groupby("department", dropna=False)["attendance_pct"].mean().dropna().reset_index(name="Average attendance")
        if not summary.empty:
            st.altair_chart(alt.Chart(summary).mark_bar(cornerRadiusTopRight=5).encode(
                x=alt.X("Average attendance:Q", title="Average attendance (%)"),
                y=alt.Y("department:N", sort="-x", title="Department"),
                tooltip=["department", alt.Tooltip("Average attendance:Q", format=".1f")]).properties(height=max(180, 36*len(summary)), title="Average attendance by department"), use_container_width=True)
    st.markdown("#### Filtered dataset preview")
    st.dataframe(filtered.head(100), use_container_width=True, hide_index=True)
    st.download_button("Export filtered dataset", filtered.to_csv(index=False).encode("utf-8-sig"), "campuspulse_filtered_dataset.csv", "text/csv")

with tab_quality:
    st.subheader("Data quality audit")
    st.caption("Flags identify possible data problems for review. The app does not silently repair records.")
    quality = data_quality_report(filtered)
    q1,q2,q3 = st.columns(3)
    q1.metric("Issues detected", f"{len(quality):,}")
    q2.metric("Rows in current view", f"{len(filtered):,}")
    q3.metric("Duplicate-ID flags", f"{int(quality['issue'].eq('Duplicate student ID').sum()) if not quality.empty else 0:,}")
    if quality.empty:
        st.success("No issues were detected by the current checks. This does not guarantee the dataset is error-free.")
    else:
        st.dataframe(quality, use_container_width=True, hide_index=True)
        st.download_button("Download quality report", quality.to_csv(index=False).encode("utf-8-sig"), "campuspulse_data_quality_report.csv", "text/csv")

with tab_schema:
    st.subheader("Dataset schema")
    st.caption("Canonical columns are mapped from common header variations. Original row values are not fabricated.")
    st.dataframe(pd.DataFrame(inspect_schema(filtered)), use_container_width=True, hide_index=True)
    st.markdown("#### Active columns")
    st.code(", ".join(map(str, filtered.columns)))
    st.markdown("#### Recognized canonical columns")
    st.write("Student ID, name, department, course, semester, attendance percentage, overall marks, exam status, quiz submission, quiz marks, quiz maximum, GPA, failed-course count — only when present in your dataset.")

st.divider()
st.caption("CampusPulse AI · Portfolio prototype · Synthetic sample data included · Not an official student information system")
