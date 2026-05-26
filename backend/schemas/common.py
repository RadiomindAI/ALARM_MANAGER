# schemas/common.py
from pydantic import BaseModel
from typing import Optional

class StatusResponse(BaseModel):
    status: str
    message: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    message: str
    alarm_kb_exists: bool
    operator_kb_exists: bool
