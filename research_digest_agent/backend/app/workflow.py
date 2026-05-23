from __future__ import annotations

import re
from typing import Literal

from langgraph.graph import END, START, StateGraph

from .models import PaperSummary, ResearchState
import mcp_client


def _topic_keywords(topic: str) -> set[str]:
    words = re.findall(r"[a-zA-Z]{3,}", topic.lower())
    return set(words)


def _relevance_score(topic: str, text: str) -> float:
    keywords = _topic_keywords(topic)
    if not keywords:
        return 0.0

    haystack = set(re.findall(r"[a-zA-Z]{3,}", text.lower()))
    overlap = keywords.intersection(haystack)
    return round(len(overlap) / max(len(keywords), 1), 3)


def _merge_unique(existing: list[dict], incoming: list[dict]) -> list[dict]:
    by_id = {p["arxiv_id"]: p for p in existing}
    for paper in incoming:
        by_id[paper["arxiv_id"]] = paper
    return list(by_id.values())


async def generate_query(state: ResearchState) -> dict:
    seen_titles = [p["title"] for p in state["collected_papers"]][:12]
    query = await mcp_client.generate_query_from_titles(
        topic=state["topic"],
        iteration=state["iteration"],
        collected_titles=seen_titles,
    )
    if not query:
        query = state["topic"]

    return {"query": query}


async def search_papers(state: ResearchState) -> dict:
    papers = await mcp_client.search_papers(state["query"], max_results=8)
    return {"candidate_papers": [paper.to_dict() for paper in papers]}


async def filter_papers(state: ResearchState) -> dict:
    scored: list[tuple[dict, float]] = []

    for paper in state["candidate_papers"]:
        text = f"{paper['title']} {paper['abstract']}"
        score = _relevance_score(state["topic"], text)
        scored.append((paper, score))

    scored.sort(key=lambda item: item[1], reverse=True)
    relevant = [paper for paper, score in scored if score >= 0.15][:5]

    if not relevant and scored:
        # Keep at least a couple of candidates to avoid dead ends on sparse topics.
        relevant = [paper for paper, _ in scored[:2]]

    collected = _merge_unique(state["collected_papers"], relevant)
    return {
        "relevant_papers": relevant,
        "collected_papers": collected,
    }


async def summarize_papers(state: ResearchState) -> dict:
    existing_ids = {item["arxiv_id"] for item in state["paper_summaries"]}
    new_summaries: list[dict] = []

    for paper in state["relevant_papers"]:
        if paper["arxiv_id"] in existing_ids:
            continue

        content = await mcp_client.summarize_paper(
            topic=state["topic"],
            title=paper["title"],
            abstract=paper["abstract"],
        )
        score = _relevance_score(state["topic"], f"{paper['title']} {paper['abstract']}")

        summary = PaperSummary(
            arxiv_id=paper["arxiv_id"],
            title=paper["title"],
            summary=content.strip() or "Summary unavailable due to MCP tool failure.",
            relevance_score=score,
        )
        new_summaries.append(summary.model_dump())

    return {"paper_summaries": state["paper_summaries"] + new_summaries}


async def evaluate_sufficiency(state: ResearchState) -> dict:
    result = await mcp_client.evaluate_sufficiency_from_summaries(
        topic=state["topic"],
        paper_summaries=state["paper_summaries"],
    )
    return {
        "sufficient": bool(result.get("sufficient", False)),
        "sufficiency_reason": str(result.get("reason", "")),
        "missing_information": str(result.get("missing_information", "")),
    }


async def prepare_next_iteration(state: ResearchState) -> dict:
    return {"iteration": state["iteration"] + 1}


def _next_after_evaluate(state: ResearchState) -> Literal["done", "loop"]:
    if state["sufficient"]:
        return "done"
    if state["iteration"] >= state["max_iterations"]:
        return "done"
    return "loop"


def build_workflow():
    graph = StateGraph(ResearchState)

    graph.add_node("generate_query", generate_query)
    graph.add_node("search_papers", search_papers)
    graph.add_node("filter_papers", filter_papers)
    graph.add_node("summarize_papers", summarize_papers)
    graph.add_node("evaluate_sufficiency", evaluate_sufficiency)
    graph.add_node("prepare_next_iteration", prepare_next_iteration)

    graph.add_edge(START, "generate_query")
    graph.add_edge("generate_query", "search_papers")
    graph.add_edge("search_papers", "filter_papers")
    graph.add_edge("filter_papers", "summarize_papers")
    graph.add_edge("summarize_papers", "evaluate_sufficiency")

    graph.add_conditional_edges(
        "evaluate_sufficiency",
        _next_after_evaluate,
        {
            "done": END,
            "loop": "prepare_next_iteration",
        },
    )
    graph.add_edge("prepare_next_iteration", "generate_query")

    return graph.compile()
