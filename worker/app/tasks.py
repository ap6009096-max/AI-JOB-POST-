from pydantic import BaseModel, Field


class TaskPayload(BaseModel):
    task_type: str = Field(examples=["parse_resume", "index_job"])
    reference_id: str
    payload: dict = Field(default_factory=dict)
