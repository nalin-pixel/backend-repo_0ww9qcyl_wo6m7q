from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class Draw(BaseModel):
    # EuroJackpot draw: 5 main numbers (1..50) and 2 euro numbers (1..12)
    date: date = Field(..., description="Draw date (YYYY-MM-DD)")
    main: List[int] = Field(..., min_items=5, max_items=5, description="Five main numbers")
    euro: List[int] = Field(..., min_items=2, max_items=2, description="Two euro numbers")
    source: Optional[str] = Field(None, description="Optional data source or note")

    @field_validator("main")
    @classmethod
    def validate_main(cls, v: List[int]) -> List[int]:
        if len(set(v)) != 5:
            raise ValueError("Main numbers must be unique and length 5")
        if not all(1 <= n <= 50 for n in v):
            raise ValueError("Main numbers must be in 1..50")
        return v

    @field_validator("euro")
    @classmethod
    def validate_euro(cls, v: List[int]) -> List[int]:
        if len(set(v)) != 2:
            raise ValueError("Euro numbers must be unique and length 2")
        if not all(1 <= n <= 12 for n in v):
            raise ValueError("Euro numbers must be in 1..12")
        return v


class DrawOut(Draw):
    id: str = Field(..., alias="_id")
    created_at: datetime
    updated_at: datetime


class Prediction(BaseModel):
    # Store one prediction result and metadata
    main: List[int] = Field(..., min_items=5, max_items=5)
    euro: List[int] = Field(..., min_items=2, max_items=2)
    seed: Optional[str] = None
    method: str = Field("consensus", description="algorithm name or 'consensus'")
    notes: Optional[str] = None

    @field_validator("main")
    @classmethod
    def v_main(cls, v: List[int]) -> List[int]:
        if len(set(v)) != 5 or not all(1 <= n <= 50 for n in v):
            raise ValueError("Main numbers invalid")
        return v

    @field_validator("euro")
    @classmethod
    def v_euro(cls, v: List[int]) -> List[int]:
        if len(set(v)) != 2 or not all(1 <= n <= 12 for n in v):
            raise ValueError("Euro numbers invalid")
        return v


class PredictionOut(Prediction):
    id: str = Field(..., alias="_id")
    created_at: datetime
    updated_at: datetime
    matched: Optional[dict] = None  # how many hits against latest draw


class BulkDraws(BaseModel):
    # Allow massive or single data input in multiple formats
    csv: Optional[str] = Field(None, description="CSV with columns: date, main1..main5, euro1, euro2")
    json: Optional[list] = Field(None, description="List of draw objects")
    text: Optional[str] = Field(None, description="Free text; one draw per line -> date; m1 m2 m3 m4 m5; e1 e2")
