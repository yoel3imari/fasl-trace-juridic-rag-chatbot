"""
Chat schemas — request/response models for the streaming chat endpoint.
"""

from pydantic import BaseModel, Field
from typing import Literal


class ChatStreamRequest(BaseModel):
    query: str = Field(..., min_length=1, description="User's query text")
    collection_id: str | None = Field(None, description="Optional collection scope")


class ProcessingStepResponse(BaseModel):
    id: str
    label: str
    status: Literal["pending", "active", "complete"]
