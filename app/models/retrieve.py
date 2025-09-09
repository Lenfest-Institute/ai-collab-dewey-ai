from pydantic import BaseModel, Field
from typing import List


class DateRange(BaseModel): 
    start_date: str = Field(..., description="start_date")
    end_date: str = Field(..., description="end_date")


class SearchParams(BaseModel):
    query: str = Field(..., description="query")
    date_range: DateRange = Field(..., description="date_range")
    authors: List[str] = Field(..., description="authors")
