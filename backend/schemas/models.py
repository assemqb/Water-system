"""Pydantic schemas for REST API."""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class FilterRequest(BaseModel):
    """Dashboard filter parameters."""

    sources: Optional[List[str]] = Field(default=None, description="data_source values")
    regions: Optional[List[str]] = None
    basins: Optional[List[str]] = None
    years: Optional[List[int]] = None
    pollutants: Optional[List[str]] = None
    lang: Literal["en", "ru", "kk"] = "kk"


class CompareRequest(BaseModel):
    region_a: str
    year_a: int
    region_b: str
    year_b: int
    sources: Optional[List[str]] = None
    regions: Optional[List[str]] = None
    basins: Optional[List[str]] = None
    years: Optional[List[int]] = None
    pollutants: Optional[List[str]] = None


class MLRequest(FilterRequest):
    target: str = "WQI_Score"


class ChatRequest(FilterRequest):
    message: str = Field(..., min_length=1, max_length=2000)
    lang: Literal["en", "ru", "kk"] = "kk"
