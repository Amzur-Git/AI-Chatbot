"""
Research paper search client.

Primary:  Semantic Scholar API (indexes arXiv + all major venues, generous rate limit)
Fallback: arXiv Atom API (direct HTTP, with backoff)

Semantic Scholar docs: https://api.semanticscholar.org/api-docs/
"""
from __future__ import annotations

import asyncio
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import List
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)

_S2_API = "https://api.semanticscholar.org/graph/v1/paper/search"
_S2_FIELDS = "paperId,title,authors,abstract,year,externalIds,openAccessPdf,publicationTypes,venue"


def _s2_headers() -> dict:
    """Build S2 request headers — include API key if configured."""
    import os
    h = {"User-Agent": "ResearchDigestAgent/1.0"}
    key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "").strip()
    if key:
        h["x-api-key"] = key
    return h

_ARXIV_API = "https://export.arxiv.org/api/query"
_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}

_arxiv_lock = asyncio.Lock()
_last_arxiv_time: float = 0.0
_ARXIV_MIN_INTERVAL = 4.0

_s2_lock = asyncio.Lock()
_last_s2_time: float = 0.0
_S2_MIN_INTERVAL = 3.0    # Semantic Scholar: 100 req / 5 min → ~3 s safe interval


@dataclass
class Paper:
    arxiv_id: str
    title: str
    authors: list[str]
    abstract: str
    published: str          # YYYY-MM-DD or YYYY
    url: str
    categories: list[str] = field(default_factory=list)
    primary_category: str = ""

    def to_dict(self) -> dict:
        return {
            "arxiv_id": self.arxiv_id,
            "title": self.title,
            "authors": self.authors[:5],
            "abstract": self.abstract[:600],
            "published": self.published,
            "url": self.url,
            "categories": self.categories,
            "primary_category": self.primary_category,
        }


# ── Semantic Scholar ─────────────────────────────────────────────────────────

def _strip_field_prefixes(query: str) -> str:
    """Remove arXiv-style field prefixes (ti:, abs:, au:) for plain-text APIs."""
    import re
    q = re.sub(r'\b(ti|abs|au|cat|id):', '', query)
    q = re.sub(r'["()]', '', q)
    q = re.sub(r'\s+(AND|OR|NOT)\s+', ' ', q, flags=re.IGNORECASE)
    return q.strip() or query


async def _search_semantic_scholar(query: str, max_results: int) -> List[Paper]:
    global _last_s2_time
    plain_query = _strip_field_prefixes(query)
    logger.info("SemanticScholar search: '%s'", plain_query)
    params = urlencode({
        "query": plain_query,
        "limit": min(max_results, 10),
        "fields": _S2_FIELDS,
    })
    url = f"{_S2_API}?{params}"
    headers = _s2_headers()

    async with _s2_lock:
        # respect rate limit
        now = asyncio.get_event_loop().time()
        gap = _last_s2_time + _S2_MIN_INTERVAL - now
        if gap > 0:
            await asyncio.sleep(gap)

        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            for attempt in range(3):
                try:
                    resp = await client.get(url, headers=headers)
                    if resp.status_code == 429:
                        wait = _S2_MIN_INTERVAL * (attempt + 2)
                        logger.warning("SemanticScholar 429 — waiting %.1f s (attempt %d)", wait, attempt + 1)
                        await asyncio.sleep(wait)
                        continue
                    resp.raise_for_status()
                    _last_s2_time = asyncio.get_event_loop().time()
                    data = resp.json()
                    papers: List[Paper] = []
                    for item in data.get("data", []):
                        title = (item.get("title") or "").strip()
                        if not title:
                            continue
                        abstract = (item.get("abstract") or "").replace("\n", " ").strip()
                        year = str(item.get("year") or "")
                        authors = [a.get("name", "") for a in (item.get("authors") or [])]
                        ext = item.get("externalIds") or {}
                        arxiv_id = ext.get("ArXiv", "") or item.get("paperId", "")
                        pdf_info = item.get("openAccessPdf") or {}
                        url_link = pdf_info.get("url") or f"https://www.semanticscholar.org/paper/{item.get('paperId','')}"
                        if ext.get("ArXiv"):
                            url_link = f"https://arxiv.org/abs/{ext['ArXiv']}"
                        venue = item.get("venue") or "arXiv"
                        papers.append(Paper(
                            arxiv_id=arxiv_id or item.get("paperId", ""),
                            title=title,
                            authors=authors,
                            abstract=abstract,
                            published=year,
                            url=url_link,
                            categories=[venue],
                            primary_category=venue,
                        ))
                    logger.info("SemanticScholar '%s' → %d papers", query, len(papers))
                    return papers
                except httpx.TimeoutException:
                    logger.warning("SemanticScholar timeout (attempt %d)", attempt + 1)
                    await asyncio.sleep(3)
                except Exception as exc:
                    logger.error("SemanticScholar error: %s", exc)
                    break
    return []


# ── arXiv fallback ───────────────────────────────────────────────────────────

def _parse_arxiv_feed(xml_text: str) -> List[Paper]:
    root = ET.fromstring(xml_text)
    papers: List[Paper] = []
    for entry in root.findall("atom:entry", _NS):
        title_el   = entry.find("atom:title",   _NS)
        summary_el = entry.find("atom:summary", _NS)
        pub_el     = entry.find("atom:published", _NS)
        id_el      = entry.find("atom:id", _NS)

        title    = (title_el.text or "").strip().replace("\n", " ") if title_el is not None else ""
        abstract = (summary_el.text or "").strip().replace("\n", " ") if summary_el is not None else ""
        pub      = (pub_el.text or "")[:10] if pub_el is not None else ""
        url      = (id_el.text or "").strip() if id_el is not None else ""
        arxiv_id = url.split("/")[-1]

        authors = [
            (a.find("atom:name", _NS).text or "").strip()
            for a in entry.findall("atom:author", _NS)
            if a.find("atom:name", _NS) is not None
        ]
        cats = [t.get("term", "") for t in entry.findall("atom:category", _NS)]
        primary_el = entry.find("{http://arxiv.org/schemas/atom}primary_category")
        primary = primary_el.get("term", cats[0] if cats else "") if primary_el is not None else (cats[0] if cats else "")

        if title and url:
            papers.append(Paper(arxiv_id=arxiv_id, title=title, authors=authors,
                                abstract=abstract, published=pub, url=url,
                                categories=cats, primary_category=primary))
    return papers


async def _search_arxiv_fallback(query: str, max_results: int) -> List[Paper]:
    global _last_arxiv_time
    params = urlencode({"search_query": query, "start": 0, "max_results": max_results,
                        "sortBy": "relevance", "sortOrder": "descending"})
    url = f"{_ARXIV_API}?{params}"
    headers = {"User-Agent": "ResearchDigestAgent/1.0"}

    async with _arxiv_lock:
        now = asyncio.get_event_loop().time()
        gap = _last_arxiv_time + _ARXIV_MIN_INTERVAL - now
        if gap > 0:
            await asyncio.sleep(gap)

        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
                    resp = await client.get(url, headers=headers)
                if resp.status_code == 429:
                    wait = _ARXIV_MIN_INTERVAL * (attempt + 2)
                    logger.warning("arXiv 429 — waiting %.1f s", wait)
                    await asyncio.sleep(wait)
                    continue
                resp.raise_for_status()
                _last_arxiv_time = asyncio.get_event_loop().time()
                papers = _parse_arxiv_feed(resp.text)
                logger.info("arXiv '%s' → %d papers", query, len(papers))
                return papers
            except httpx.TimeoutException:
                logger.warning("arXiv timeout (attempt %d)", attempt + 1)
                await asyncio.sleep(5)
            except Exception as exc:
                logger.error("arXiv error: %s", exc)
                break
    return []


# ── Public API ───────────────────────────────────────────────────────────────

async def search_arxiv(query: str, max_results: int = 5) -> List[Paper]:
    """
    Search for papers.  Tries Semantic Scholar first; falls back to arXiv API.
    Returns (papers, source) where source is 's2', 'arxiv', or 'none'.
    """
    papers = await _search_semantic_scholar(query, max_results)
    if papers:
        return papers
    logger.info("Semantic Scholar returned 0 — trying arXiv fallback")
    return await _search_arxiv_fallback(query, max_results)


def rate_limit_hint() -> str:
    """Return a helpful hint when both APIs return 0 papers."""
    import os
    has_key = bool(os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "").strip())
    if not has_key:
        return (
            "Both Semantic Scholar and arXiv are rate-limiting this IP from repeated requests. "
            "Wait 2–3 minutes and try again, OR add a free Semantic Scholar API key to backend/.env "
            "(SEMANTIC_SCHOLAR_API_KEY=...) from https://www.semanticscholar.org/product/api"
        )
    return "APIs are temporarily rate-limiting. Wait 1–2 minutes and try again."

import asyncio
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import List
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)

_ARXIV_API = "https://export.arxiv.org/api/query"
_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
    "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
}

# Global lock so parallel calls still respect the rate limit
_arxiv_lock = asyncio.Lock()
_last_request_time: float = 0.0
_MIN_INTERVAL = 4.0   # seconds — arXiv asks for ≥3 s


@dataclass
class Paper:
    arxiv_id: str
    title: str
    authors: list[str]
    abstract: str
    published: str          # YYYY-MM-DD
    url: str
    categories: list[str] = field(default_factory=list)
    primary_category: str = ""

    def to_dict(self) -> dict:
        return {
            "arxiv_id": self.arxiv_id,
            "title": self.title,
            "authors": self.authors[:5],
            "abstract": self.abstract[:600],
            "published": self.published,
            "url": self.url,
            "categories": self.categories,
            "primary_category": self.primary_category,
        }


def _parse_feed(xml_text: str) -> List[Paper]:
    root = ET.fromstring(xml_text)
    papers: List[Paper] = []
    for entry in root.findall("atom:entry", _NS):
        title_el = entry.find("atom:title", _NS)
        summary_el = entry.find("atom:summary", _NS)
        published_el = entry.find("atom:published", _NS)
        id_el = entry.find("atom:id", _NS)

        title = (title_el.text or "").strip().replace("\n", " ") if title_el is not None else ""
        abstract = (summary_el.text or "").strip().replace("\n", " ") if summary_el is not None else ""
        published_raw = (published_el.text or "")[:10] if published_el is not None else ""
        url = (id_el.text or "").strip() if id_el is not None else ""
        arxiv_id = url.split("/")[-1]

        authors = [
            (a.find("atom:name", _NS).text or "").strip()
            for a in entry.findall("atom:author", _NS)
            if a.find("atom:name", _NS) is not None
        ]

        cats = [
            t.get("term", "")
            for t in entry.findall("atom:category", _NS)
        ]
        primary_el = entry.find("arxiv:primary_category", _NS)
        primary = primary_el.get("term", cats[0] if cats else "") if primary_el is not None else (cats[0] if cats else "")

        if title and url:
            papers.append(Paper(
                arxiv_id=arxiv_id,
                title=title,
                authors=authors,
                abstract=abstract,
                published=published_raw,
                url=url,
                categories=cats,
                primary_category=primary,
            ))
    return papers


async def search_arxiv(query: str, max_results: int = 5) -> List[Paper]:
    """Async arXiv Atom API search with rate-limiting and retry."""
    global _last_request_time
    params = urlencode({
        "search_query": query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending",
    })
    url = f"{_ARXIV_API}?{params}"

    async with _arxiv_lock:
        # Respect rate limit
        now = asyncio.get_event_loop().time()
        gap = _last_request_time + _MIN_INTERVAL - now
        if gap > 0:
            await asyncio.sleep(gap)

        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                    resp = await client.get(url, headers={"User-Agent": "ResearchDigestAgent/1.0"})
                if resp.status_code == 429:
                    wait = _MIN_INTERVAL * (attempt + 2)
                    logger.warning("arXiv 429 — waiting %.1f s (attempt %d)", wait, attempt + 1)
                    await asyncio.sleep(wait)
                    continue
                resp.raise_for_status()
                _last_request_time = asyncio.get_event_loop().time()
                papers = _parse_feed(resp.text)
                logger.info("arXiv '%s' → %d papers", query, len(papers))
                return papers
            except httpx.TimeoutException:
                logger.warning("arXiv timeout (attempt %d)", attempt + 1)
                await asyncio.sleep(3)
            except Exception as exc:
                logger.error("arXiv error: %s", exc)
                break
        return []
