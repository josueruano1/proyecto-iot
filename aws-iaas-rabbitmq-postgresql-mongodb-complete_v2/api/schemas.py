from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OrderCreate(BaseModel):
    description: str = Field(..., min_length=1)
    status: str = Field(default="created", min_length=1, max_length=50)
    metadata: dict[str, Any] = Field(default_factory=dict)


class OrderUpdate(BaseModel):
    description: str | None = None
    status: str | None = None
    metadata: dict[str, Any] | None = None

    model_config = ConfigDict(extra="forbid")


class OrderResponse(BaseModel):
    order_id: int
    description: str
    status: str
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class AcceptedTaskResponse(BaseModel):
    task_id: UUID
    status: str
    done: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaskResponse(BaseModel):
    task_id: UUID
    operation: str
    target_order_id: int | None = None
    status: str
    done: bool
    payload: dict[str, Any]
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class HealthResponse(BaseModel):
    status: str
    database: str
