from __future__ import annotations

from sqlalchemy.orm import Session

from langgraph.graph import END, START, StateGraph

from app.db.models import Candidate
from app.graphs.candidate_nodes import (
    analyze_github,
    analyze_linkedin,
    analyze_other_sources,
    analyze_portfolio,
    analyze_resume,
    create_master_candidate_json,
    deduplicate,
    extract_document,
    generate_candidate_embedding,
    load_candidate,
    load_resume,
    merge_sources,
    normalize_candidate,
    route_after_extract,
    route_after_resume,
    route_after_validate,
    save_profile,
    validate_candidate,
)
from app.graphs.candidate_state import CandidateGraphState

ALL_PIPELINE_NODES = [
    "load_candidate",
    "load_resume",
    "extract_document",
    "analyze_resume",
    "analyze_github",
    "analyze_linkedin",
    "analyze_portfolio",
    "analyze_other_sources",
    "merge_sources",
    "normalize_candidate",
    "deduplicate",
    "validate_candidate",
    "create_master_candidate_json",
    "generate_candidate_embedding",
    "save_profile",
]


def build_candidate_graph():
    graph = StateGraph(CandidateGraphState)
    graph.add_node("load_candidate", load_candidate)
    graph.add_node("load_resume", load_resume)
    graph.add_node("extract_document", extract_document)
    graph.add_node("analyze_resume", analyze_resume)
    graph.add_node("analyze_github", analyze_github)
    graph.add_node("analyze_linkedin", analyze_linkedin)
    graph.add_node("analyze_portfolio", analyze_portfolio)
    graph.add_node("analyze_other_sources", analyze_other_sources)
    graph.add_node("merge_sources", merge_sources)
    graph.add_node("normalize_candidate", normalize_candidate)
    graph.add_node("deduplicate", deduplicate)
    graph.add_node("validate_candidate", validate_candidate)
    graph.add_node("create_master_candidate_json", create_master_candidate_json)
    graph.add_node("generate_candidate_embedding", generate_candidate_embedding)
    graph.add_node("save_profile", save_profile)

    graph.add_edge(START, "load_candidate")
    graph.add_edge("load_candidate", "load_resume")
    graph.add_conditional_edges(
        "load_resume",
        route_after_resume,
        {"extract_document": "extract_document", "analyze_github": "analyze_github"},
    )
    graph.add_conditional_edges(
        "extract_document",
        route_after_extract,
        {"analyze_resume": "analyze_resume", "analyze_github": "analyze_github"},
    )
    graph.add_edge("analyze_resume", "analyze_github")
    graph.add_edge("analyze_github", "analyze_linkedin")
    graph.add_edge("analyze_linkedin", "analyze_portfolio")
    graph.add_edge("analyze_portfolio", "analyze_other_sources")
    graph.add_edge("analyze_other_sources", "merge_sources")
    graph.add_edge("merge_sources", "normalize_candidate")
    graph.add_edge("normalize_candidate", "deduplicate")
    graph.add_edge("deduplicate", "validate_candidate")
    graph.add_conditional_edges(
        "validate_candidate",
        route_after_validate,
        {"create_master_candidate_json": "create_master_candidate_json", "save_profile": "save_profile"},
    )
    graph.add_edge("create_master_candidate_json", "generate_candidate_embedding")
    graph.add_edge("generate_candidate_embedding", "save_profile")
    graph.add_edge("save_profile", END)
    return graph.compile()


_CANDIDATE_GRAPH = None


def candidate_graph():
    global _CANDIDATE_GRAPH
    if _CANDIDATE_GRAPH is None:
        _CANDIDATE_GRAPH = build_candidate_graph()
    return _CANDIDATE_GRAPH


def run_candidate_graph(session: Session, candidate: Candidate) -> CandidateGraphState:
    initial: CandidateGraphState = {
        "candidate_id": str(candidate.id),
        "current_node": "",
        "status": "running",
        "errors": [],
        "skipped": [],
        "steps": [],
        "resume_present": False,
        "extraction_ok": False,
        "validation_ok": False,
        "embedding_ok": False,
        "resume_text": "",
        "resume_content_type": "",
        "resume_bytes": None,
        "parse_result": {},
        "github": {},
        "linkedin": {},
        "portfolio": {},
        "other_sources": [],
        "merged": {},
        "normalized": {},
        "master": {},
        "embedding": [],
    }
    result = candidate_graph().invoke(
        initial,
        config={"configurable": {"session": session, "candidate": candidate}},
    )
    return result
