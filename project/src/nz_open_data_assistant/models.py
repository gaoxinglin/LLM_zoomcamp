from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class Resource(BaseModel):
    id: str
    name: str = "Resource"
    url: str
    format: str = ""
    datastore_active: bool = False


class Dataset(BaseModel):
    id: str
    name: str
    title: str
    description: str = ""
    organization: str = "Unknown publisher"
    tags: list[str] = Field(default_factory=list)
    groups: list[str] = Field(default_factory=list)
    license_title: str = "Not specified"
    metadata_created: str | None = None
    metadata_modified: str | None = None
    url: str
    resources: list[Resource] = Field(default_factory=list)

    @property
    def formats(self) -> list[str]:
        return sorted({resource.format for resource in self.resources if resource.format})

    @property
    def searchable_text(self) -> str:
        return "\n".join(
            [
                f"Title: {self.title}",
                f"Publisher: {self.organization}",
                f"Topics: {', '.join(self.tags + self.groups)}",
                f"Formats: {', '.join(self.formats)}",
                f"Description: {self.description}",
            ]
        )


class SearchMode(StrEnum):
    LEXICAL = "lexical"
    VECTOR = "vector"
    HYBRID = "hybrid"


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    limit: int = Field(default=5, ge=1, le=20)
    mode: SearchMode = SearchMode.LEXICAL
    rewrite: bool = False
    rerank: bool = True


class SearchResult(BaseModel):
    dataset: Dataset
    score: float
    rank: int
    matched_by: list[str] = Field(default_factory=list)


class AnswerRequest(SearchRequest):
    use_llm: bool = True


class Citation(BaseModel):
    dataset_id: str
    title: str
    url: str
    publisher: str
    updated: str | None = None


class AnswerResponse(BaseModel):
    answer: str
    citations: list[Citation]
    results: list[SearchResult]
    used_llm: bool
    request_id: str
    latency_ms: float


class Filter(BaseModel):
    field: str
    operator: Literal["=", "!=", ">", ">=", "<", "<=", "contains"] = "="
    value: str | int | float | bool

    @field_validator("field")
    @classmethod
    def valid_identifier(cls, value: str) -> str:
        if not value.replace("_", "").isalnum():
            raise ValueError("Field names may contain only letters, numbers, and underscores")
        return value


class DataQueryPlan(BaseModel):
    dataset_id: str
    resource_id: str
    adapter: Literal["ckan", "arcgis"]
    fields: list[str] = Field(default_factory=list, max_length=20)
    filters: list[Filter] = Field(default_factory=list, max_length=10)
    order_by: str | None = None
    descending: bool = False
    limit: int = Field(default=20, ge=1, le=100)


class DataQueryResult(BaseModel):
    plan: DataQueryPlan
    columns: list[str]
    rows: list[dict[str, Any]]
    source_url: str
    row_count: int


class FeedbackRequest(BaseModel):
    request_id: str
    rating: Literal[-1, 1]
    comment: str | None = Field(default=None, max_length=1000)


class HealthResponse(BaseModel):
    status: str
    datasets: int
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
