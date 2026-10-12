from typing import List
from pydantic import BaseModel, AwareDatetime

class ActivityEntry(BaseModel):
    activity_id: str
    stage: str
    summary: str
    sku: str
    occurred_at: AwareDatetime

class ActivityRepository:
    def __init__(self):
        self._activities = []
        
    def list_activity(self) -> List[ActivityEntry]:
        return self._activities
