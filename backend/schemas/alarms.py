# schemas/alarms.py
from pydantic import BaseModel
from typing import Optional, Literal

class AlarmRule(BaseModel):
    alarm_code_name: str
    operator_action: Literal["TRASCURABILE", "MONITORA", "SCALA", "INVESTIGATE", "TOLERABLE", "MONITOR", "ESCALATE"]
    note: Optional[str] = ""

class WizardPayload(BaseModel):
    rules: list[AlarmRule]

class UpdateRulePayload(BaseModel):
    alarm_code_name: str
    operator_action: str
    note: Optional[str] = ""
    new_alarm_entry: Optional[dict] = None
