"""
ReAct-style Research Digest Agent.

Loop:
  Think → Search arXiv → Observe papers → Evaluate sufficiency
  → if sufficient: Synthesize digest (streamed)
  → if not:        Refine query and repeat (max MAX_ITERATIONS)
"""
from __future__ import annotations

import json
import logging
import os
from typing import AsyncGenerator, List

from openai import AsyncOpenAI

from arxiv_client import Paper, rate_limit_hint, search_arxiv

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


# ---------------------------------------------------------------------------
# Helper: single non-streaming LLM call that returns JSON
# ---------------------------------------------------------------------------
async def _call_json(system: str, user: str) -> dict:
    client = _llm_client()
    resp = await client.chat.completions.create(
        model=_model(),
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    raw = resp.choices[0].message.content or "{}"
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("LLM returned non-JSON: %s", raw[:200])
        return {}


# ---------------------------------------------------------------------------
# Step 1 — Generate arXiv search query for the given iteration
# ---------------------------------------------------------------------------
async def _generate_query(
    topic: str,
    collected_papers: List[Paper],
    iteration: int,
    zero_results: bool = False,
) -> str:
    seen_titles = [p.title for p in collected_papers]
    extra = ""
    if zero_results:
        extra = (
            "IMPORTANT: The previous query returned ZERO results. "
            "Use much simpler, broader, or more general synonyms. "
            "Try core concepts or related terms instead of the exact phrase."
        )
    system = (
        "You are a research librarian. Generate a concise plain-text search query "
        "(2-5 words, no field prefixes, no quotes, no boolean operators) "
        "suitable for Semantic Scholar and arXiv. "
        "The query must be plain keywords only. "
        "Return JSON with a single key 'query'. "
        "On iteration > 0, use different keywords/synonyms to find more papers."
    )
    user = (
        f"Research topic: {topic}\n"
        f"Iteration: {iteration}\n"
        f"Papers already found ({len(seen_titles)}): {json.dumps(seen_titles[:10])}\n"
        f"{extra}\n"
        "Generate the best plain-text keyword search query for this iteration."
    )
    result = await _call_json(system, user)
    query = result.get("query") or topic
    return str(query)[:200]


# ---------------------------------------------------------------------------
# Step 2 — Evaluate whether collected papers are sufficient
# ---------------------------------------------------------------------------
async def _evaluate_sufficiency(topic: str, papers: List[Paper]) -> dict:
    """Returns {sufficient: bool, reason: str, missing: str}"""
    abstracts_snippet = "\n".join(
        f"- [{p.published[:4]}] {p.title}: {p.abstract[:200]}"
        for p in papers
    )
    system = (
        "You are a research evaluator. "
        "Decide if the paper list is sufficient to write a comprehensive research digest. "
        "Criteria: at least 3 relevant papers, covering core concepts and recent work. "
        "Return JSON: {\"sufficient\": bool, \"reason\": \"...\", \"missing\": \"...\"}"
    )
    user = (
        f"Topic: {topic}\n"
        f"Papers collected ({len(papers)}):\n{abstracts_snippet}\n\n"
        "Is the evidence sufficient?"
    )
    return await _call_json(system, user)


# ---------------------------------------------------------------------------
# Step 3 — Stream the synthesized digest
# ---------------------------------------------------------------------------
async def _stream_digest(topic: str, papers: List[Paper]) -> AsyncGenerator[str, None]:
    """Yields text chunks of the final markdown digest."""
    paper_details = "\n\n".join(
        f"### {i+1}. {p.title}\n"
        f"**Authors:** {', '.join(p.authors[:3])}{'et al.' if len(p.authors)>3 else ''}\n"
        f"**Published:** {p.published} | **Category:** {p.primary_category}\n"
        f"**URL:** {p.url}\n"
        f"**Abstract:** {p.abstract[:500]}"
        for i, p in enumerate(papers)
    )
    system = (
        "You are a senior AI research analyst. "
        "Write a comprehensive, structured research digest in Markdown. "
        "Use these exact sections:\n"
        "1. ## Overview (3–4 sentences synthesising the field)\n"
        "2. ## Key Papers (brief annotation of each paper)\n"
        "3. ## Key Findings (5–8 bullet points of the most important insights)\n"
        "4. ## Research Trends (2–3 emerging directions)\n"
        "5. ## Recommended Reading Order (numbered list, easiest → most advanced)\n"
        "6. ## Open Questions (2–3 unresolved problems)\n\n"
        "Be specific. Cite paper titles inline. Use Markdown formatting."
    )
    user = (
        f"# Research Topic: {topic}\n\n"
        f"## Papers\n{paper_details}\n\n"
        "Write the research digest now."
    )

    client = _llm_client()
    stream = await client.chat.completions.create(
        model=_model(),
        temperature=0.3,
        stream=True,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


# ---------------------------------------------------------------------------
# Public: main agent generator — yields SSE-ready dicts
# ---------------------------------------------------------------------------
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
        query = await _generate_query(topic, all_papers, iteration, zero_results=zero_prev)
        yield {"event": "searching", "data": {"iteration": iteration + 1, "query": query}}

        # ── SEARCH ─────────────────────────────────────────────────────────
        new_papers = await search_arxiv(query, max_results=5)

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

        evaluation = await _evaluate_sufficiency(topic, all_papers)
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
    async for chunk in _stream_digest(topic, all_papers):
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
