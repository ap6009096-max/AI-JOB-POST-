from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class JobGraphState(TypedDict, total=False):
    job_id: str
    current_node: str
    status: str
    errors: Annotated[list[dict[str, str]], operator.add]
    skipped: Annotated[list[dict[str, str]], operator.add]
    steps: Annotated[list[dict[str, str]], operator.add]
    checks: Annotated[list[dict[str, str]], operator.add]
    fields: dict[str, Any]
    normalized: dict[str, Any]
    job_json: dict[str, Any]
    review: str
    validation_ok: bool
