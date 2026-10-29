# CampusPulse AI — Premium Faculty Intelligence

A polished, explainable faculty analytics prototype built with Streamlit, Pandas, SQLite and Altair. It helps faculty explore attendance, marks, quiz submissions, exam attendance, academic support indicators and dataset quality using plain-language questions.

> **Important:** This is a portfolio/demo project, not an official university system. The included student records are synthetic. Do not upload identifiable real student data to a public deployment.

## What is implemented

- Premium responsive Streamlit UI with a clean blue-and-white visual system.
- CSV upload and synthetic sample dataset.
- Header alias mapping for common variants such as `Roll No`, `Student Name`, `Attendance`, `Marks`, `Quiz Status`, `Exam Status`, and GPA.
- Numeric type conversion for common academic fields.
- KPI cards, attendance distribution, marks distribution and department attendance chart, based on the active dataset.
- Deterministic natural-language query planner for supported intents.
- Read-only SQL validation and in-memory SQLite execution, plus SQLite authorizer safeguards.
- SQL preview with a clear validated/executed status.
- Result table and CSV export.
- Dataset filters for department, semester and course when those columns exist.
- Data quality checks for duplicate IDs, missing IDs/names/departments, invalid attendance, negative marks, quiz scores above maximum, assumed GPA range and submitted quizzes without scores.
- Session-only query history.
- Explainable academic support flags: the rule is shown and explicitly intended for human review.
- Automated tests for query behaviour, schema gaps, unsafe SQL and quality checks.

## Supported question examples

- `Show the top 5 students by overall marks`
- `Show top 2 students by GPA`
- `Which students have attendance below 60%?`
- `Show students with attendance above 90%`
- `Which students have not submitted the quiz?`
- `Who got full marks in the quiz?`
- `Which students were absent from the end-semester exam?`
- `Find students with low attendance and low marks`
- `Show average attendance by department`
- `Find students with missing grades`
- `Find students with multiple failed courses`
- `List all students`

The deterministic mode intentionally answers only supported patterns. Unsupported questions do not silently fall back to an unrelated query. This version does not include an LLM API integration; this keeps the default demo reproducible and makes the query behaviour easy to verify.

## Run locally

Requires Python 3.10+.

### Windows PowerShell
```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

### macOS / Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The app opens at `http://localhost:8501`.

## Run tests
```bash
pytest -q
```

Tests cover supported query planning and execution, common header aliases, missing schema, explicit exam absence, unsupported questions, SQL write-operation rejection and data-quality checks.

## Deploy on Streamlit Community Cloud

1. Upload the project contents to a GitHub repository.
2. Visit https://share.streamlit.io/ and sign in with GitHub.
3. Create an app, choose your repository and branch, and set main file path to `app.py`.
4. Deploy. Streamlit will provide the public URL after a successful build.

A public demo is for synthetic data only. Do not treat the deployment as an authenticated student records system.

## Architecture

```text
CSV / synthetic dataset
        ↓
Header mapping + numeric normalization
        ↓
Workspace filters + schema inspection
        ↓
Deterministic intent planner
        ↓
Read-only SQL validation
        ↓
In-memory SQLite + authorizer
        ↓
Explainable results / charts / CSV exports
        ↓
Human review
```

## Safety and limitations

- No authentication, role-based access control, persistent audit log or production database connector.
- CSV data is loaded in the Streamlit app session; deployment environments may have different operational properties. Use synthetic data for public demos.
- SQL validation is defence-in-depth for a prototype, not a substitute for a carefully permissioned production database and security review.
- Missing exam statuses are not counted as confirmed absences.
- Academic support indicators are review prompts, not labels or decisions about students.
- GPA quality checks assume a 0–10 scale. Change the check if your institution uses another scale.
- Trend analysis across time is not implemented unless the dataset and a future version explicitly support dated historical records.
- The included intent planner is not general-purpose natural-language understanding. It supports the examples above and reports unsupported requests clearly.

## Project structure

```text
CampusPulse_AI_Premium/
├── app.py
├── core.py
├── requirements.txt
├── README.md
├── LICENSE
├── .gitignore
├── .streamlit/config.toml
├── sample_data/students.csv
└── tests/test_core.py
```

## Resume-ready description

**CampusPulse AI — Faculty Intelligence Assistant**  
Built a faculty analytics prototype with schema-flexible CSV ingestion, natural-language query routing, read-only SQL validation, SQLite execution, interactive academic charts, explainable student-support indicators, data-quality auditing and downloadable results. Added automated tests for query correctness, missing schemas and SQL safety.

**Skills:** Python, Streamlit, Pandas, SQLite, Altair, Text-to-SQL concepts, data validation, SQL safety, automated testing, UI/UX.

## 2–3 minute presentation script

Good morning everyone. My project is CampusPulse AI, a faculty intelligence assistant designed to make student data easier to explore.

Faculty members often need to answer questions such as who has low attendance, who has not submitted a quiz, which students scored full marks, or how attendance differs across departments. Doing this manually in spreadsheets can take time. CampusPulse AI provides a single workspace where a teacher can load a CSV and ask supported questions in natural language.

The app first maps common column names to a consistent schema, checks what data is available, and identifies the intent behind a supported question. It then validates a read-only SQL query and runs it against an in-memory SQLite database. The results are shown in a table, along with the SQL and an explanation, and can be exported as a CSV.

The project also includes visual analytics for attendance and marks, department summaries, and a data-quality audit that flags duplicate IDs, missing values, invalid attendance percentages and inconsistent quiz records. These checks help staff review data quality instead of blindly trusting a spreadsheet.

A key design decision is transparency. The system does not invent results when a question is unsupported, and it does not treat missing examination data as confirmed absence. Academic support flags are prompts for human review, not automated judgements.

The current version is a portfolio prototype using synthetic demo data. It does not yet include university authentication or a live student information system. Those would be important before real institutional use.

Overall, CampusPulse AI demonstrates how data engineering, SQL safety, analytics and a carefully designed interface can help faculty explore academic records more efficiently. Thank you.
