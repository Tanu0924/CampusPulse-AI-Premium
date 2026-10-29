import pandas as pd
import pytest
from core import canonicalize, data_quality_report, plan_question, validate_sql, execute_readonly

@pytest.fixture
def sample():
    return canonicalize(pd.DataFrame([
        {"Roll No":"S1","Student Name":"A","Attendance":"55%","Marks":45,"Quiz Status":"No","Quiz Marks":None,"Quiz Total Marks":20,"Exam Status":"Absent","Department":"CS","GPA":5.2,"Failed Courses":2},
        {"Roll No":"S2","Student Name":"B","Attendance":"95","Marks":92,"Quiz Status":"Yes","Quiz Marks":20,"Quiz Total Marks":20,"Exam Status":"Present","Department":"IT","GPA":9.2,"Failed Courses":0},
        {"Roll No":"S3","Student Name":"C","Attendance":"78","Marks":70,"Quiz Status":"Yes","Quiz Marks":17,"Quiz Total Marks":20,"Exam Status":"Present","Department":"CS","GPA":7.1,"Failed Courses":0},
    ]))

def test_aliases_and_numeric_conversion(sample):
    assert "student_id" in sample.columns
    assert sample.loc[0, "attendance_pct"] == 55
    assert sample.loc[1, "overall_marks"] == 92

def test_dynamic_attendance_threshold(sample):
    plan = plan_question("Which students have attendance below 60%?", list(sample.columns))
    result = execute_readonly(sample, plan.sql)
    assert result["student_id"].tolist() == ["S1"]

def test_above_attendance_threshold(sample):
    plan = plan_question("Show students with attendance above 90%", list(sample.columns))
    result = execute_readonly(sample, plan.sql)
    assert result["student_id"].tolist() == ["S2"]

def test_top_n(sample):
    plan = plan_question("Show top 2 students by overall marks", list(sample.columns))
    result = execute_readonly(sample, plan.sql)
    assert result["student_id"].tolist() == ["S2", "S3"]

def test_exam_absence_is_explicit(sample):
    plan = plan_question("Which students were absent from the end-semester exam?", list(sample.columns))
    result = execute_readonly(sample, plan.sql)
    assert result["student_id"].tolist() == ["S1"]

def test_missing_column_is_explained():
    plan = plan_question("Which students were absent from the exam?", ["student_id", "name"])
    assert plan.mode == "unsupported"
    assert "exam_status" in plan.explanation

def test_unsupported_question_does_not_fallback(sample):
    assert plan_question("What is the best university in the world?", list(sample.columns)) is None

@pytest.mark.parametrize("sql", [
    "DELETE FROM students",
    "DROP TABLE students",
    "SELECT * FROM students; DELETE FROM students",
    "SELECT * FROM sqlite_master",
    "SELECT * FROM students; -- comment",
    "SELECT * FROM other_table",
])
def test_unsafe_sql_rejected(sql, sample):
    with pytest.raises(ValueError):
        validate_sql(sql, list(sample.columns))

def test_data_quality_detects_duplicate_and_out_of_range():
    frame = canonicalize(pd.DataFrame([
        {"student_id":"D1","name":"A","attendance_pct":120,"overall_marks":20},
        {"student_id":"D1","name":"B","attendance_pct":80,"overall_marks":-1},
    ]))
    issues = data_quality_report(frame)
    assert "Duplicate student ID" in issues["issue"].tolist()
    assert "Attendance outside 0–100%" in issues["issue"].tolist()
    assert "Negative overall marks" in issues["issue"].tolist()


def test_department_average_and_support_intents_are_not_captured_by_generic_attendance(sample):
    dept = plan_question("Show average attendance by department", list(sample.columns))
    assert dept.title == "Department attendance summary"
    support = plan_question("Find students with low attendance and low marks", list(sample.columns))
    assert support.title == "Academic support review"
