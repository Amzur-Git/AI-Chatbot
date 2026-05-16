from __future__ import annotations

import json
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage

from .llm import get_chat_llm
from .models import ResearchState
from .workflow import build_workflow


def _apply_update(state: dict, update: dict) -> dict:
    for key, value in update.items():
        state[key] = value
    return state


async def _stream_final_digest(topic: str, paper_summaries: list[dict]) -> AsyncGenerator[str, None]:
    llm = get_chat_llm(temperature=0.2)

    summaries_text = "\n\n".join(
        f"Title: {item['title']}\nSummary: {item['summary']}"
        for item in paper_summaries[:12]
    )

    prompt = (
        f"Research topic: {topic}\n\n"
        f"Paper summaries:\n{summaries_text}\n\n"
        "Write a structured markdown research digest with these exact sections:\n"
        "## Overview\n"
        "## Key findings\n"
        "## Important papers\n"
        "## Trends\n"
        "## Limitations\n"
        "## Future research directions\n"
        "## References\n"
        "For references, include paper titles as a numbered list."
    )

    async for chunk in llm.astream(
        [
            SystemMessage(content="You are a senior research analyst writing concise, accurate digests."),
            HumanMessage(content=prompt),
        ]
    ):
        text = chunk.content if isinstance(chunk.content, str) else ""
        if text:
            yield text


async def run_research_agent(topic: str, max_iterations: int = 4) -> AsyncGenerator[dict, None]:
    graph = build_workflow()

    state: ResearchState = {
        "topic": topic,
        "iteration": 1,
        "max_iterations": max_iterations,
        "query": "",
        "candidate_papers": [],
        "relevant_papers": [],
        "collected_papers": [],
        "paper_summaries": [],
        "sufficient": False,
        "sufficiency_reason": "",
        "missing_information": "",
    }

    yield {
        "event": "agent_start",
        "data": {"topic": topic, "max_iterations": max_iterations},
    }

    async for update in graph.astream(state, stream_mode="updates"):
        for node_name, node_update in update.items():
            state = _apply_update(state, node_update)

            if node_name == "generate_query":
                yield {
                    "event": "reasoning",
                    "data": {
                        "iteration": state["iteration"],
                        "message": f"Planning search strategy for iteration {state['iteration']}",
                    },
                }
                yield {
                    "event": "searching",
                    "data": {
                        "iteration": state["iteration"],
                        "query": state["query"],
                    },
                }

            elif node_name == "search_papers":
                yield {
                    "event": "papers_found",
                    "data": {
                        "iteration": state["iteration"],
                        "query": state["query"],
                        "new_count": len(state["candidate_papers"]),
                        "papers": state["candidate_papers"],
                    },
                }

            elif node_name == "filter_papers":
                yield {
                    "event": "reasoning",
                    "data": {
                        "iteration": state["iteration"],
                        "message": (
                            f"Filtered {len(state['relevant_papers'])} relevant papers "
                            f"from {len(state['candidate_papers'])} candidates"
                        ),
                    },
                }

            elif node_name == "summarize_papers":
                yield {
                    "event": "summarizing",
                    "data": {
                        "iteration": state["iteration"],
                        "summaries_count": len(state["paper_summaries"]),
                    },
                }

            elif node_name == "evaluate_sufficiency":
                yield {
                    "event": "evaluation_result",
                    "data": {
                        "iteration": state["iteration"],
                        "sufficient": state["sufficient"],
                        "reason": state["sufficiency_reason"],
                        "missing_information": state["missing_information"],
                    },
                }

    yield {
        "event": "synthesizing",
        "data": {
            "message": "Generating final structured research digest",
            "papers_used": len(state["paper_summaries"]),
        },
    }

    digest = ""
    async for chunk in _stream_final_digest(topic, state["paper_summaries"]):
        digest += chunk
        yield {"event": "digest_chunk", "data": {"chunk": chunk}}

    yield {
        "event": "done",
        "data": {
            "topic": topic,
            "iterations": state["iteration"],
            "papers_collected": len(state["collected_papers"]),
            "summaries_collected": len(state["paper_summaries"]),
            "sufficient": state["sufficient"],
            "digest_length": len(digest),
        },
    }
