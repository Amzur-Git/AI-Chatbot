from __future__ import annotations

import asyncio
import logging
import xml.etree.ElementTree as et
from urllib.parse import urlencode

import httpx

from .models import Paper

logger = logging.getLogger(__name__)

_ARXIV_API = "https://export.arxiv.org/api/query"
_NS = {
    "atom": "http://www.w3.org/2005/Atom",
}

_arxiv_lock = asyncio.Lock()
_last_request_ts: float = 0.0
_MIN_INTERVAL_SECONDS = 4.0


def _parse_feed(xml_text: str) -> list[Paper]:
    root = et.fromstring(xml_text)
    papers: list[Paper] = []

    for entry in root.findall("atom:entry", _NS):
        title_el = entry.find("atom:title", _NS)
        summary_el = entry.find("atom:summary", _NS)
        id_el = entry.find("atom:id", _NS)
        published_el = entry.find("atom:published", _NS)

        if title_el is None or id_el is None:
            continue

        title = (title_el.text or "").strip().replace("\n", " ")
        abstract = (summary_el.text or "").strip().replace("\n", " ") if summary_el is not None else ""
        url = (id_el.text or "").strip()
        published = (published_el.text or "")[:10] if published_el is not None else ""
        arxiv_id = url.split("/")[-1]

        authors = [
            (author.find("atom:name", _NS).text or "").strip()
            for author in entry.findall("atom:author", _NS)
            if author.find("atom:name", _NS) is not None
        ]

        categories = [c.get("term", "") for c in entry.findall("atom:category", _NS)]

        papers.append(
            Paper(
                arxiv_id=arxiv_id,
                title=title,
                authors=authors,
                abstract=abstract,
                published=published,
                url=url,
                categories=[c for c in categories if c],
            )
        )

    return papers


async def search_arxiv(query: str, max_results: int = 8) -> list[Paper]:
    global _last_request_ts

    params = urlencode(
        {
            "search_query": query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }
    )
    url = f"{_ARXIV_API}?{params}"

    async with _arxiv_lock:
        now = asyncio.get_event_loop().time()
        wait_for = _last_request_ts + _MIN_INTERVAL_SECONDS - now
        if wait_for > 0:
            await asyncio.sleep(wait_for)

        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                    response = await client.get(url, headers={"User-Agent": "ResearchDigestAgent/2.0"})

                if response.status_code == 429:
                    backoff = 6 + (attempt * 4)
                    logger.warning("arXiv 429 for query '%s', waiting %ss", query, backoff)
                    await asyncio.sleep(backoff)
                    continue

                response.raise_for_status()
                _last_request_ts = asyncio.get_event_loop().time()
                return _parse_feed(response.text)
            except httpx.TimeoutException:
                logger.warning("arXiv timeout on attempt %s", attempt + 1)
                await asyncio.sleep(3)
            except Exception as exc:
                logger.error("arXiv search failed: %s", exc)
                break

    return []
