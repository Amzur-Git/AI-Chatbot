"""
MCP Server for Research Digest Agent Tools.

This server exposes tool functions that were previously hand-written in the agent:
- generate_query: Generate arXiv search queries
- evaluate_sufficiency: Evaluate if collected papers are sufficient
- search_papers: Search arXiv for papers
- stream_digest: Stream synthesized research digest

The agent calls these via MCP instead of directly, demonstrating MCP integration
while keeping the agent logic, frontend, and system prompt unchanged.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from typing import Any, AsyncGenerator, List

# Add project and backend directories to import path, regardless of cwd.
PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_DIR)

from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Import the research tools (arxiv_client and agent helper functions)
from backend.arxiv_client import Paper, search_arxiv

logger = logging.getLogger(__name__)

# Create MCP Server instance
server = Server("research-digest-agent-tools")


# ──────────────────────────────────────────────────────────────────────────────
# Standalone Tool Implementations
# ──────────────────────────────────────────────────────────────────────────────


def _llm_client() -> Any:
    """Create LLM client for tool execution."""
    from openai import AsyncOpenAI
    return AsyncOpenAI(
        api_key=os.environ.get("LITELLM_API_KEY", ""),
        base_url=os.environ.get("LITELLM_PROXY_URL", ""),
    )


def _model() -> str:
    """Get LLM model name."""
    return os.environ.get("LLM_MODEL", "gpt-4o")


async def _call_json(system: str, user: str) -> dict:
    """Make a JSON-formatted LLM call."""
    client = _llm_client()
    try:
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
    except Exception as e:
        logger.error("Error in _call_json: %s", e)
        return {}


async def _stream_digest(topic: str, papers: List[Paper]) -> AsyncGenerator[str, None]:
    """Stream the synthesized research digest."""
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
    try:
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
    except Exception as e:
        logger.error("Error in _stream_digest: %s", e)
        yield f"Error generating digest: {str(e)}"


async def _stream_digest_from_summaries(
    topic: str,
    paper_summaries: list[dict[str, Any]],
) -> AsyncGenerator[str, None]:
    """Stream digest synthesis directly from paper summaries."""
    summaries_text = "\n\n".join(
        f"Title: {item.get('title', '')}\nSummary: {item.get('summary', '')}"
        for item in paper_summaries[:12]
    )

    system = "You are a senior research analyst writing concise, accurate digests."
    user = (
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

    client = _llm_client()
    try:
        stream = await client.chat.completions.create(
            model=_model(),
            temperature=0.2,
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
    except Exception as e:
        logger.error("Error in _stream_digest_from_summaries: %s", e)
        yield f"Error generating digest: {str(e)}"


async def _summarize_paper_impl(topic: str, title: str, abstract: str) -> str:
    """Summarize a paper for iterative evidence gathering."""
    client = _llm_client()
    try:
        resp = await client.chat.completions.create(
            model=_model(),
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Summarize the paper for a research digest. "
                        "Return 2-3 concise sentences focused on methods and findings."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Topic: {topic}\n"
                        f"Title: {title}\n"
                        f"Abstract: {abstract}"
                    ),
                },
            ],
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        logger.error("Error in _summarize_paper_impl: %s", e)
        return ""


# ──────────────────────────────────────────────────────────────────────────────
# Tool Definitions
# ──────────────────────────────────────────────────────────────────────────────


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """List all available tools."""
    return [
        Tool(
            name="generate_query",
            description="Generate an arXiv search query using LLM. Takes a research topic and iteration context.",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "The research topic to search for.",
                    },
                    "collected_papers": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "arxiv_id": {"type": "string"},
                                "authors": {"type": "array", "items": {"type": "string"}},
                                "abstract": {"type": "string"},
                                "published": {"type": "string"},
                                "url": {"type": "string"},
                                "categories": {"type": "array", "items": {"type": "string"}},
                                "primary_category": {"type": "string"},
                            },
                        },
                        "description": "Papers already collected so far.",
                    },
                    "iteration": {
                        "type": "integer",
                        "description": "Current iteration number (0-based).",
                    },
                    "zero_results": {
                        "type": "boolean",
                        "description": "Whether the previous search returned zero results.",
                    },
                },
                "required": ["topic", "collected_papers", "iteration"],
            },
        ),
        Tool(
            name="generate_query_from_titles",
            description="Generate an arXiv search query from topic, iteration, and previously collected paper titles.",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "The research topic."},
                    "iteration": {"type": "integer", "description": "Current iteration number (1-based)."},
                    "collected_titles": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Already collected paper titles.",
                    },
                },
                "required": ["topic", "iteration", "collected_titles"],
            },
        ),
        Tool(
            name="evaluate_sufficiency",
            description="Evaluate whether collected papers are sufficient for a research digest.",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "The research topic.",
                    },
                    "papers": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "arxiv_id": {"type": "string"},
                                "authors": {"type": "array", "items": {"type": "string"}},
                                "abstract": {"type": "string"},
                                "published": {"type": "string"},
                                "url": {"type": "string"},
                                "categories": {"type": "array", "items": {"type": "string"}},
                                "primary_category": {"type": "string"},
                            },
                        },
                        "description": "Papers collected so far.",
                    },
                    "paper_summaries": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "arxiv_id": {"type": "string"},
                                "title": {"type": "string"},
                                "summary": {"type": "string"},
                            },
                        },
                        "description": "Paper summaries collected so far.",
                    },
                },
                "required": ["topic"],
                "anyOf": [
                    {"required": ["papers"]},
                    {"required": ["paper_summaries"]}
                ],
            },
        ),
        Tool(
            name="search_papers",
            description="Search arXiv for papers matching a query.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query for arXiv.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return.",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="summarize_paper",
            description="Summarize one paper for research evidence gathering.",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "The research topic."},
                    "title": {"type": "string", "description": "The paper title."},
                    "abstract": {"type": "string", "description": "The paper abstract."},
                },
                "required": ["topic", "title", "abstract"],
            },
        ),
        Tool(
            name="stream_digest",
            description="Stream the synthesized research digest from collected papers.",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "The research topic.",
                    },
                    "papers": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "arxiv_id": {"type": "string"},
                                "authors": {"type": "array", "items": {"type": "string"}},
                                "abstract": {"type": "string"},
                                "published": {"type": "string"},
                                "url": {"type": "string"},
                                "categories": {"type": "array", "items": {"type": "string"}},
                                "primary_category": {"type": "string"},
                            },
                        },
                        "description": "Papers to synthesize into a digest.",
                    },
                },
                "required": ["topic", "papers"],
            },
        ),
        Tool(
            name="stream_digest_from_summaries",
            description="Stream the synthesized research digest from paper summaries.",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "The research topic."},
                    "paper_summaries": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "arxiv_id": {"type": "string"},
                                "title": {"type": "string"},
                                "summary": {"type": "string"},
                            },
                        },
                        "description": "Paper summaries to synthesize into a digest.",
                    },
                },
                "required": ["topic", "paper_summaries"],
            },
        ),
    ]


# ──────────────────────────────────────────────────────────────────────────────
# Tool Implementation Handlers
# ──────────────────────────────────────────────────────────────────────────────


def _papers_from_dicts(papers_data: list[dict]) -> List[Paper]:
    """Convert paper dictionaries to Paper objects."""
    papers = []
    for p in papers_data:
        paper = Paper(
            arxiv_id=p.get("arxiv_id", ""),
            title=p.get("title", ""),
            authors=p.get("authors", []),
            abstract=p.get("abstract", ""),
            published=p.get("published", ""),
            url=p.get("url", ""),
            categories=p.get("categories", []),
            primary_category=p.get("primary_category", ""),
        )
        papers.append(paper)
    return papers


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls from the agent."""
    try:
        if name == "generate_query":
            collected_papers = _papers_from_dicts(arguments.get("collected_papers", []))
            query = await _generate_query_impl(
                topic=arguments["topic"],
                collected_papers=collected_papers,
                iteration=arguments["iteration"],
                zero_results=arguments.get("zero_results", False),
            )
            return [TextContent(type="text", text=query)]

        elif name == "generate_query_from_titles":
            collected_titles = arguments.get("collected_titles", []) or []
            pseudo_papers = [
                Paper(
                    arxiv_id="",
                    title=str(title),
                    authors=[],
                    abstract="",
                    published="",
                    url="",
                    categories=[],
                    primary_category="",
                )
                for title in collected_titles
            ]
            query = await _generate_query_impl(
                topic=arguments["topic"],
                collected_papers=pseudo_papers,
                iteration=max(int(arguments.get("iteration", 1)) - 1, 0),
                zero_results=False,
            )
            return [TextContent(type="text", text=query)]

        elif name == "evaluate_sufficiency":
            if "paper_summaries" in arguments:
                summaries = arguments.get("paper_summaries", []) or []
                result = await _evaluate_sufficiency_from_summaries_impl(
                    topic=arguments["topic"],
                    paper_summaries=summaries,
                )
            else:
                papers = _papers_from_dicts(arguments.get("papers", []))
                result = await _evaluate_sufficiency_impl(
                    topic=arguments["topic"],
                    papers=papers,
                )
            return [TextContent(type="text", text=json.dumps(result))]

        elif name == "search_papers":
            papers = await search_arxiv(
                query=arguments["query"],
                max_results=arguments.get("max_results", 5),
            )
            papers_data = [p.to_dict() for p in papers]
            return [TextContent(type="text", text=json.dumps(papers_data))]

        elif name == "stream_digest":
            papers = _papers_from_dicts(arguments.get("papers", []))
            # Collect all chunks from the async generator
            digest_text = ""
            async for chunk in _stream_digest(arguments["topic"], papers):
                digest_text += chunk
            return [TextContent(type="text", text=digest_text)]

        elif name == "summarize_paper":
            summary = await _summarize_paper_impl(
                topic=arguments["topic"],
                title=arguments["title"],
                abstract=arguments["abstract"],
            )
            return [TextContent(type="text", text=summary)]

        elif name == "stream_digest_from_summaries":
            digest_text = ""
            async for chunk in _stream_digest_from_summaries(
                arguments["topic"],
                arguments.get("paper_summaries", []),
            ):
                digest_text += chunk
            return [TextContent(type="text", text=digest_text)]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        logger.exception("Error in tool call %s", name)
        return [TextContent(type="text", text=f"Error: {str(e)}")]


# ──────────────────────────────────────────────────────────────────────────────
# Tool Implementation Functions
# ──────────────────────────────────────────────────────────────────────────────


async def _generate_query_impl(
    topic: str,
    collected_papers: List[Paper],
    iteration: int,
    zero_results: bool = False,
) -> str:
    """Generate an arXiv search query for the given iteration."""
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


async def _evaluate_sufficiency_impl(topic: str, papers: List[Paper]) -> dict:
    """Evaluate whether collected papers are sufficient."""
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


async def _evaluate_sufficiency_from_summaries_impl(topic: str, paper_summaries: list[dict]) -> dict:
    """Evaluate sufficiency using summary snippets from iterative workflow."""
    if len(paper_summaries) < 3:
        return {
            "sufficient": False,
            "reason": "Need at least 3 relevant summarized papers.",
            "missing": "Insufficient paper coverage across methods/findings.",
        }

    snippet = "\n".join(
        f"- {item.get('title', '')}: {str(item.get('summary', ''))[:220]}"
        for item in paper_summaries[:10]
    )
    system = (
        "You are a research quality evaluator. Decide whether evidence is enough "
        "to produce a high-quality digest."
    )
    user = (
        f"Topic: {topic}\n"
        f"Summaries:\n{snippet}\n\n"
        "Return JSON: {\"sufficient\": bool, \"reason\": \"...\", \"missing\": \"...\"}"
    )
    return await _call_json(system, user)


# ──────────────────────────────────────────────────────────────────────────────
# Server Initialization
# ──────────────────────────────────────────────────────────────────────────────


async def main():
    """Run the MCP server."""
    logger.info("Research Digest Agent MCP Server running on stdio...")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="research-digest-agent-tools",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    asyncio.run(main())
