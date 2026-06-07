from __future__ import annotations
from pydantic import BaseModel, ConfigDict
from typing import Literal

class BaseObservation(BaseModel):
    model_config = ConfigDict(extra="allow")

    actorDid: str
    createdAt: int
    tier: Literal["A", "B", "C"]
    internal_only: bool = False
