from __future__ import annotations

from sqlalchemy.orm import Session

from langgraph.graph import END, START, StateGraph

from app.db.models import Job
from app.graphs.job_nodes import (
    create_job_json,
    description_quality_check,
    duplicate_check,
    education_check,
    experience_check,
    gemini_review,
    load_job,
    normalize_job,
    required_field_check,
    salary_check,
    skill_check,
    technology_check,
    validate_job,
)
from app.graphs.job_state import JobGraphState

ALL_PIPELINE_NODES = [
    "load_job",
    "required_field_check",
    "description_quality_check",
    "skill_check",
    "experience_check",
    "education_check",
    "technology_check",
    "salary_check",
    "duplicate_check",
    "Gemini_review",
    "normalize_job",
    "validate_job",
    "create_job_json",
]


def build_job_graph():
    graph = StateGraph(JobGraphState)
    graph.add_node("load_job", load_job)
    graph.add_node("required_field_check", required_field_check)
    graph.add_node("description_quality_check", description_quality_check)
    graph.add_node("skill_check", skill_check)
    graph.add_node("experience_check", experience_check)
    graph.add_node("education_check", education_check)
    graph.add_node("technology_check", technology_check)
    graph.add_node("salary_check", salary_check)
    graph.add_node("duplicate_check", duplicate_check)
    graph.add_node("Gemini_review", gemini_review)
    graph.add_node("normalize_job", normalize_job)
    graph.add_node("validate_job", validate_job)
    graph.add_node("create_job_json", create_job_json)

    graph.add_edge(START, "load_job")
    graph.add_edge("load_job", "required_field_check")
    graph.add_edge("required_field_check", "description_quality_check")
    graph.add_edge("description_quality_check", "skill_check")
    graph.add_edge("skill_check", "experience_check")
    graph.add_edge("experience_check", "education_check")
    graph.add_edge("education_check", "technology_check")
    graph.add_edge("technology_check", "salary_check")
    graph.add_edge("salary_check", "duplicate_check")
    graph.add_edge("duplicate_check", "Gemini_review")
    graph.add_edge("Gemini_review", "normalize_job")
    graph.add_edge("normalize_job", "validate_job")
    graph.add_edge("validate_job", "create_job_json")
    graph.add_edge("create_job_json", END)
    return graph.compile()


_JOB_GRAPH = None


def job_graph():
    global _JOB_GRAPH
    if _JOB_GRAPH is None:
        _JOB_GRAPH = build_job_graph()
    return _JOB_GRAPH


def run_job_graph(session: Session, job: Job) -> JobGraphState:
    initial: JobGraphState = {
        "job_id": str(job.id),
        "current_node": "",
        "status": "running",
        "errors": [],
        "skipped": [],
        "steps": [],
        "checks": [],
        "fields": {},
        "normalized": {},
        "job_json": {},
        "review": "",
        "validation_ok": False,
    }
    result = job_graph().invoke(
        initial,
        config={"configurable": {"session": session, "job": job}},
    )
    return result
