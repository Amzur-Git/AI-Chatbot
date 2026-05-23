"""
ReAct-style Research Digest Agent.

IMPORTANT: This agent is Project 10 (original implementation) adapted to Project 12.
The agent logic, system prompt, and behavior remain IDENTICAL.
Only the underlying tool calls have been switched from hand-written functions to MCP calls.

Loop:
  Think → Search arXiv (via MCP) → Observe papers → Evaluate sufficiency (via MCP)
  → if sufficient: Synthesize digest (streamed via MCP)
  → if not:        Refine query and repeat (max MAX_ITERATIONS)
"""
from __future__ import annotations

import json
import logging
import os
from typing import AsyncGenerator, List

from openai import AsyncOpenAI

from arxiv_client import Paper, rate_limit_hint
import mcp_client

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 4          # safety cap on search rounds
MIN_PAPERS_TARGET = 3       # agent aims for at least this many relevant papers


def _llm_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=os.environ["LITELLM_API_KEY"],
        base_url=os.environ["LITELLM_PROXY_URL"],
    )


def _model() -> str:
    return os.environ.get("LLM_MODEL", "gpt-4o")


# ──────────────────────────────────────────────────────────────────────────────
# AGENT LOGIC (unchanged from Project 10)
# Tool implementations have moved to MCP server; calls now use mcp_client module
# ──────────────────────────────────────────────────────────────────────────────
async def run_research_agent(topic: str) -> AsyncGenerator[dict, None]:
    """
    Yields structured event dicts:
      {"event": "<type>", "data": {...}}
    Caller wraps these into SSE text.
    """

    yield {"event": "agent_start", "data": {"topic": topic, "max_iterations": MAX_ITERATIONS}}

    all_papers: List[Paper] = []
    seen_ids: set[str] = set()
    iteration = 0

    while iteration < MAX_ITERATIONS:
        # ── THINK ──────────────────────────────────────────────────────────
        yield {
            "event": "thinking",
            "data": {
                "iteration": iteration + 1,
                "message": (
                    f"Iteration {iteration + 1}: Planning search query…"
                    if iteration == 0
                    else f"Iteration {iteration + 1}: Papers so far insufficient — refining search…"
                ),
                "papers_so_far": len(all_papers),
            },
        }

        # ── GENERATE QUERY ─────────────────────────────────────────────────
        zero_prev = (iteration > 0 and len(all_papers) == 0)
        query = await mcp_client.generate_query(topic, all_papers, iteration, zero_results=zero_prev)
        yield {"event": "searching", "data": {"iteration": iteration + 1, "query": query}}

        # ── SEARCH ─────────────────────────────────────────────────────────
        new_papers = await mcp_client.search_papers(query, max_results=5)

        # deduplicate
        unique_new: List[Paper] = []
        for p in new_papers:
            if p.arxiv_id not in seen_ids:
                seen_ids.add(p.arxiv_id)
                all_papers.append(p)
                unique_new.append(p)

        yield {
            "event": "papers_found",
            "data": {
                "iteration": iteration + 1,
                "query": query,
                "new_count": len(unique_new),
                "total_count": len(all_papers),
                "papers": [p.to_dict() for p in unique_new],
            },
        }

        # If still no papers at all, skip evaluation and retry
        if not all_papers:
            if iteration + 1 >= MAX_ITERATIONS:
                yield {
                    "event": "error",
                    "data": {"message": rate_limit_hint()},
                }
                return
            yield {
                "event": "thinking",
                "data": {
                    "iteration": iteration + 2,
                    "message": f"No papers found — trying broader keywords…",
                    "papers_so_far": 0,
                },
            }
            iteration += 1
            continue

        # ── EVALUATE SUFFICIENCY ───────────────────────────────────────────
        yield {
            "event": "evaluating",
            "data": {"message": "Evaluating whether collected papers are sufficient…", "total": len(all_papers)},
        }

        evaluation = await mcp_client.evaluate_sufficiency(topic, all_papers)
        sufficient = bool(evaluation.get("sufficient", False))
        reason = evaluation.get("reason", "")
        missing = evaluation.get("missing", "")

        yield {
            "event": "evaluation_result",
            "data": {
                "sufficient": sufficient,
                "reason": reason,
                "missing": missing,
                "total_papers": len(all_papers),
            },
        }

        if sufficient or len(all_papers) >= MIN_PAPERS_TARGET * 2:
            break

        iteration += 1

    # ── SYNTHESIZE DIGEST ──────────────────────────────────────────────────
    yield {
        "event": "synthesizing",
        "data": {
            "message": f"Synthesizing digest from {len(all_papers)} papers…",
            "paper_titles": [p.title for p in all_papers],
        },
    }

    digest_text = ""
    async for chunk in mcp_client.stream_digest(topic, all_papers):
        digest_text += chunk
        yield {"event": "digest_chunk", "data": {"chunk": chunk}}

    yield {
        "event": "done",
        "data": {
            "topic": topic,
            "papers_used": len(all_papers),
            "digest_length": len(digest_text),
        },
    }
