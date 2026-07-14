from pydantic import BaseModel, Field, ValidationError
from typing import List, Literal, Optional
from datetime import datetime
from uuid import UUID


class LLMProviderBase(BaseModel):
    provider_type: Literal["openai", "anthropic", "ollama"] = Field(
        ..., description="openai | anthropic | ollama"
    )
    base_url: Optional[str] = Field(None, description="None for Ollama default")
    api_version: Optional[str] = Field(None, description="e.g. 'v1' for OpenAI")


class LLMProviderCreate(LLMProviderBase):
    pass


_OMIT = object()


class LLMProviderUpdate(BaseModel):
    base_url: Optional[str] | object = _OMIT
    api_version: Optional[str] = _OMIT
    is_active: Optional[bool] = _OMIT


class LLMProviderResponse(LLMProviderBase):
    id: UUID
    user_id: UUID
    is_active: bool
    has_api_key: bool = False
    warning: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LLMProviderListResponse(BaseModel):
    items: List[LLMProviderResponse]
    total: int
    skip: int
    limit: int


class APIKeySet(BaseModel):
    api_key: str = Field(
        ...,
        min_length=1,
        max_length=4096,
        description="Plaintext API key to encrypt and store",
    )


class APIKeyResponse(BaseModel):
    has_api_key: bool
    masked_key: Optional[str] = None
    updated_at: Optional[datetime] = None
