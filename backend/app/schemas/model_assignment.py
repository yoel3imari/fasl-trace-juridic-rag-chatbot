from pydantic import BaseModel, ConfigDict, Field
from typing import List, Literal, Optional
from datetime import datetime
from uuid import UUID


class ModelAssignmentBase(BaseModel):
    provider_id: UUID = Field(..., description="FK to llm_providers.id")
    model_name: str = Field(..., min_length=1, max_length=255, description="e.g. gpt-4o, claude-3-5-sonnet")
    system_function: Literal["retrieval", "generation", "evaluation"] = Field(
        ..., description="retrieval | generation | evaluation"
    )


class ModelAssignmentCreate(ModelAssignmentBase):
    pass


class ModelAssignmentUpdate(BaseModel):
    model_name: Optional[str] = None
    is_active: Optional[bool] = None


class ModelAssignmentResponse(ModelAssignmentBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    is_active: bool
    health_status: Optional[str] = None
    health_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ModelAssignmentListResponse(BaseModel):
    items: List[ModelAssignmentResponse]
    total: int
    skip: int
    limit: int
