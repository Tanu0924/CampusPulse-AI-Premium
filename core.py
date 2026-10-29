"""Core data, query-planning, SQL-safety, and data-quality utilities for CampusPulse AI."""
from __future__ import annotations
import re
import sqlite3
from dataclasses import dataclass
from typing import Optional
import pandas as pd

ALIASES = {
    "student_id": ["studentid", "id", "rollno", "rollnumber", "enrollmentno", "enrolmentno", "registrationnumber", "studentcode"],
    "name": ["name", "studentname", "fullname", "student"],
    "department": ["department", "dept", "programme", "program", "branch", "faculty"],
    "course": ["course", "subject", "coursename", "subjectname"],
    "semester": ["semester", "term", "sem"],
    "attendance_pct": ["attendancepct", "attendance", "attendancepercentage", "attendancepercent", "attendancerate", "attendancepercentage"],
    "overall_marks": ["overallmarks", "totalmarks", "finalmarks", "performance", "marks", "totalscore", "score"],
    "exam_status": ["examstatus", "endsemstatus", "semesterexamstatus", "examattendance", "examappeared", "appeared"],
    "quiz_submitted": ["quizsubmitted", "quizstatus", "quizattempted", "submitted", "quizsubmissionstatus"],
    "quiz_marks": ["quizmarks", "quizscore", "quizmark"],
    "quiz_total_marks": ["quiztotalmarks", "quizmaxmarks", "quizmaximum", "maxquizmarks"],
    "gpa": ["gpa", "cgpa", "sgpa"],
    "failed_courses": ["failedcourses", "coursesfailed", "backlogs", "arrears"],
}

def normalize_col(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())

def canonicalize(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize common header aliases without inventing data values."""
    frame = frame.copy()
    normalized = {normalize_col(c): c for c in frame.columns}
    renames = {}
    used = set()
    for canonical, aliases in ALIASES.items():
        for alias in [canonical] + aliases:
            found = normalized.get(normalize_col(alias))
            if found is not None and found not in used:
                renames[found] = canonical
                used.add(found)
                break
    frame = frame.rename(columns=renames)
    for col in ["attendance_pct", "overall_marks", "quiz_marks", "quiz_total_marks", "gpa", "failed_courses", "semester"]:
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col].astype(str).str.replace("%", "", regex=False).str.strip(), errors="coerce")
    for col in ["student_id", "name", "department", "course", "exam_status", "quiz_submitted"]:
        if col in frame.columns:
            frame[col] = frame[col].where(frame[col].notna(), None)
    return frame

def inspect_schema(frame: pd.DataFrame) -> list[dict]:
    return [{"column": str(c), "type": str(frame[c].dtype), "non_null": int(frame[c].notna().sum()),
             "missing": int(frame[c].isna().sum()), "unique": int(frame[c].nunique(dropna=True))}
            for c in frame.columns]

def data_quality_report(frame: pd.DataFrame) -> pd.DataFrame:
    """Return row-level data quality issues; flags are advisory, not silent corrections."""
    issues = []
    if frame.empty:
        return pd.DataFrame(columns=["row_number", "student_id", "issue", "value"])
    id_col = "student_id" if "student_id" in frame.columns else None
    for idx, row in frame.iterrows():
        row_num = int(idx) + 2
        sid = row.get(id_col, "") if id_col else ""
        if id_col and pd.isna(sid):
            issues.append((row_num, "", "Missing student ID", ""))
        if id_col and pd.notna(sid) and str(sid).strip():
            # Duplicate details added below, avoiding one issue per pair.
            pass
        for col in ("name", "department"):
            if col in frame.columns and (pd.isna(row[col]) or not str(row[col]).strip()):
                issues.append((row_num, sid, f"Missing {col.replace('_',' ')}", ""))
        if "attendance_pct" in frame.columns and pd.notna(row.get("attendance_pct")):
            value = row["attendance_pct"]
            if value < 0 or value > 100:
                issues.append((row_num, sid, "Attendance outside 0–100%", value))
        for col in ("overall_marks", "quiz_marks", "quiz_total_marks"):
            if col in frame.columns and pd.notna(row.get(col)) and row[col] < 0:
                issues.append((row_num, sid, f"Negative {col.replace('_',' ')}", row[col]))
        if all(c in frame.columns for c in ("quiz_marks", "quiz_total_marks")):
            earned, total = row.get("quiz_marks"), row.get("quiz_total_marks")
            if pd.notna(earned) and pd.notna(total) and earned > total:
                issues.append((row_num, sid, "Quiz marks exceed maximum", f"{earned} > {total}"))
        if "gpa" in frame.columns and pd.notna(row.get("gpa")) and (row["gpa"] < 0 or row["gpa"] > 10):
            issues.append((row_num, sid, "GPA outside assumed 0–10 range", row["gpa"]))
        if "quiz_submitted" in frame.columns:
            status = str(row.get("quiz_submitted", "")).strip().lower()
            if status in {"yes", "true", "1", "submitted", "complete"} and "quiz_marks" in frame.columns and pd.isna(row.get("quiz_marks")):
                issues.append((row_num, sid, "Submitted quiz has no score", status))
    if id_col:
        ids = frame[id_col].astype("string").str.strip()
        dup_mask = ids.notna() & ids.ne("") & ids.duplicated(keep=False)
        for idx in frame.index[dup_mask]:
            issues.append((int(idx)+2, frame.loc[idx, id_col], "Duplicate student ID", frame.loc[idx, id_col]))
    return pd.DataFrame(issues, columns=["row_number", "student_id", "issue", "value"])

@dataclass
class QueryPlan:
    title: str
    sql: str
    explanation: str
    mode: str = "records"

def _has(columns, *names):
    return all(n in columns for n in names)

def plan_question(question: str, columns: list[str]) -> Optional[QueryPlan]:
    """A deterministic, auditable query planner for common faculty intents."""
    q = question.lower().replace("’", "'")
    has = lambda *terms: any(t in q for t in terms)
    def require(cols, title):
        missing = [c for c in cols if c not in columns]
        if missing:
            return QueryPlan(title, "", "This question needs columns not found in the dataset: " + ", ".join(missing) + ".", "unsupported")
        return None
    select_base = [c for c in ("student_id", "name") if c in columns]
    select = ", ".join(select_base) if select_base else "*"
    threshold_match = re.search(r"(?:below|under|less than|<)\s*(\d+(?:\.\d+)?)\s*%?", q)
    above_match = re.search(r"(?:above|over|more than|greater than|>)\s*(\d+(?:\.\d+)?)\s*%?", q)
    if has("data quality", "duplicate id", "duplicates", "missing values", "invalid records"):
        return QueryPlan("Data quality review", "", "Run the Data Quality tab to inspect row-level issues.", "quality")
    if has("top", "best", "highest") and has("student", "performer", "marks", "gpa", "score"):
        metric = "gpa" if has("gpa", "cgpa") and "gpa" in columns else ("overall_marks" if "overall_marks" in columns else ("gpa" if "gpa" in columns else None))
        if not metric:
            return QueryPlan("Top performers", "", "A marks or GPA column is required to rank students.", "unsupported")
        nmatch = re.search(r"\btop\s+(\d+)\b", q)
        n = min(max(int(nmatch.group(1)), 1), 100) if nmatch else 5
        return QueryPlan("Top performers", f"SELECT {select}, {metric} FROM students WHERE {metric} IS NOT NULL ORDER BY {metric} DESC LIMIT {n}", f"Ranked by {metric.replace('_',' ')} descending; limited to {n} records.")
    if has("exam", "end-sem", "end sem", "endsem", "final examination") and has("absent", "not appear", "didn't appear", "did not appear", "not appeared", "not attend", "missed", "absence"):
        missing = require(["exam_status"], "Examination absence audit")
        if missing: return missing
        return QueryPlan("Examination absence audit", f"SELECT {select}, exam_status FROM students WHERE lower(trim(CAST(exam_status AS TEXT))) IN ('absent','not appeared','not_attempted','no','false','0','did not appear') ORDER BY name", "Lists only statuses explicitly recorded as absent/non-appeared. Missing statuses are not treated as confirmed absences.")
    if has("quiz") and has("not submitted", "not attempted", "didn't submit", "have not submitted", "haven't submitted", "pending", "not given", "non submitter"):
        missing = require(["quiz_submitted"], "Quiz non-submissions")
        if missing: return missing
        return QueryPlan("Quiz non-submissions", f"SELECT {select}, quiz_submitted FROM students WHERE lower(trim(CAST(quiz_submitted AS TEXT))) IN ('no','false','0','not submitted','not attempted','pending','absent')", "Uses explicit non-submission status values; blank statuses are not automatically considered confirmed non-submissions.")
    if has("full marks", "full mark", "perfect score", "full score") and has("quiz", "score", "marks"):
        missing = require(["quiz_marks", "quiz_total_marks"], "Full quiz marks")
        if missing: return missing
        return QueryPlan("Full quiz marks", f"SELECT {select}, quiz_marks, quiz_total_marks FROM students WHERE quiz_marks = quiz_total_marks AND quiz_total_marks IS NOT NULL", "Matches earned marks equal to a recorded maximum score.")
    if has("attendance") and not has("low attendance and low marks", "both low", "need support", "academic support", "at risk", "at-risk", "average attendance", "avg attendance"):
        missing = require(["attendance_pct"], "Attendance analysis")
        if missing: return missing
        if threshold_match:
            threshold = float(threshold_match.group(1))
            op = "<"
            if threshold < 0 or threshold > 100:
                return QueryPlan("Attendance analysis", "", "Attendance thresholds must be between 0 and 100.", "unsupported")
            return QueryPlan(f"Attendance below {threshold:g}%", f"SELECT {select}, attendance_pct FROM students WHERE attendance_pct < {threshold:g} ORDER BY attendance_pct ASC", f"Filters attendance strictly below {threshold:g}%.")
        if above_match:
            threshold = float(above_match.group(1))
            if threshold < 0 or threshold > 100:
                return QueryPlan("Attendance analysis", "", "Attendance thresholds must be between 0 and 100.", "unsupported")
            return QueryPlan(f"Attendance above {threshold:g}%", f"SELECT {select}, attendance_pct FROM students WHERE attendance_pct > {threshold:g} ORDER BY attendance_pct DESC", f"Filters attendance strictly above {threshold:g}%.")
        return QueryPlan("Attendance overview", f"SELECT {select}, attendance_pct FROM students WHERE attendance_pct IS NOT NULL ORDER BY attendance_pct ASC LIMIT 200", "Shows records with a recorded attendance percentage.")
    if has("average", "avg", "mean") and has("department") and has("attendance"):
        missing = require(["department", "attendance_pct"], "Department attendance summary")
        if missing: return missing
        return QueryPlan("Department attendance summary", "SELECT department, ROUND(AVG(attendance_pct), 2) AS average_attendance_pct, COUNT(*) AS student_count FROM students WHERE attendance_pct IS NOT NULL GROUP BY department ORDER BY average_attendance_pct DESC", "Averages recorded attendance by department; rows with missing attendance are excluded from the average.")
    if has("low attendance and low marks", "both low", "need support", "academic support", "at risk", "at-risk"):
        missing = require(["attendance_pct", "overall_marks"], "Academic support review")
        if missing: return missing
        return QueryPlan("Academic support review", f"SELECT {select}, attendance_pct, overall_marks FROM students WHERE attendance_pct < 75 AND overall_marks < 50 ORDER BY attendance_pct ASC", "Review flag: attendance below 75% AND overall marks below 50. This is a support prompt for human review, not a judgement.")
    if has("missing grade", "missing grades", "no recorded grades", "grades missing"):
        missing = require(["overall_marks"], "Missing grades")
        if missing: return missing
        return QueryPlan("Missing grades", f"SELECT {select} FROM students WHERE overall_marks IS NULL", "Lists rows with no recorded overall marks.")
    if has("failed multiple", "multiple failures", "multiple courses", "backlogs", "arrears"):
        missing = require(["failed_courses"], "Multiple failed courses")
        if missing: return missing
        return QueryPlan("Multiple failed courses", f"SELECT {select}, failed_courses FROM students WHERE failed_courses >= 2 ORDER BY failed_courses DESC", "Lists students with two or more recorded failed courses.")
    if has("all students", "list all", "show all", "student list"):
        return QueryPlan("Student list", "SELECT * FROM students LIMIT 200", "Shows up to 200 rows from the loaded dataset.")
    return None

BLOCKED_SQL = re.compile(r"\b(insert|update|delete|drop|alter|create|replace|attach|detach|pragma|vacuum|load_extension|sqlite_master|sqlite_schema|writable_schema|readfile|writefile)\b", re.I)

def validate_sql(sql: str, columns: list[str]) -> str:
    if not sql or not sql.strip():
        raise ValueError("No SQL was generated.")
    cleaned = sql.strip().rstrip(";").strip()
    if ";" in cleaned:
        raise ValueError("Only one SQL statement is allowed.")
    if not re.match(r"(?is)^(select|with)\b", cleaned):
        raise ValueError("Only read-only SELECT queries are allowed.")
    if BLOCKED_SQL.search(cleaned):
        raise ValueError("The query contains a blocked operation.")
    if not re.search(r"(?i)\bstudents\b", cleaned):
        raise ValueError("Queries must reference the students table.")
    # Avoid SQL comments and unknown table references.
    if "--" in cleaned or "/*" in cleaned or "*/" in cleaned:
        raise ValueError("SQL comments are not allowed.")
    tables = re.findall(r"(?i)\b(?:FROM|JOIN)\s+([A-Za-z_][A-Za-z0-9_]*)", cleaned)
    if not tables or any(t.lower() != "students" for t in tables):
        raise ValueError("Only the students table is available.")
    return cleaned + ";"

def execute_readonly(frame: pd.DataFrame, sql: str) -> pd.DataFrame:
    safe_sql = validate_sql(sql, list(frame.columns))
    conn = sqlite3.connect(":memory:")
    try:
        frame.to_sql("students", conn, index=False, if_exists="replace")
        conn.execute("PRAGMA query_only = ON")
        # SQLite authorizer blocks write operations even if validation misses a construct.
        def authorizer(action, arg1, arg2, dbname, source):
            denied = {sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE,
                      sqlite3.SQLITE_CREATE_INDEX, sqlite3.SQLITE_CREATE_TABLE,
                      sqlite3.SQLITE_DROP_INDEX, sqlite3.SQLITE_DROP_TABLE,
                      sqlite3.SQLITE_ALTER_TABLE, sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH}
            return sqlite3.SQLITE_DENY if action in denied else sqlite3.SQLITE_OK
        conn.set_authorizer(authorizer)
        return pd.read_sql_query(safe_sql, conn)
    finally:
        conn.close()
