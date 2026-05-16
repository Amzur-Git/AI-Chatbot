from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypedDict

from pydantic import BaseModel, Field


class DigestRequest(BaseModel):
    topic: str = Field(..., min_length=3, max_length=300)


@dataclass
class Paper:
    arxiv_id: str
    title: str
    authors: list[str]
    abstract: str
    published: str
    url: str
    categories: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "arxiv_id": self.arxiv_id,
            "title": self.title,
            "authors": self.authors,
            "abstract": self.abstract,
            "published": self.published,
            "url": self.url,
            "categories": self.categories,
        }


class PaperSummary(BaseModel):
    arxiv_id: str
    title: str
    summary: str
    relevance_score: float = 0.0


class QueryPlan(BaseModel):
    query: str
    reasoning: str


class SufficiencyDecision(BaseModel):
    sufficient: bool
    reason: str
    missing_information: str = ""


class ResearchState(TypedDict):
    topic: str
    iteration: int
    max_iterations: int
    query: str
    candidate_papers: list[dict]
    relevant_papers: list[dict]
    collected_papers: list[dict]
    paper_summaries: list[dict]
    sufficient: bool
    sufficiency_reason: str
    missing_information: str
