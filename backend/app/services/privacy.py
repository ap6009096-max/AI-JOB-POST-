from __future__ import annotations

from typing import Any

PROTECTED_DISCLOSURE_KEYS = frozenset(
    {
        "gender",
        "sex",
        "race",
        "ethnicity",
        "national_origin",
        "religion",
        "disability",
        "sexual_orientation",
        "marital_status",
        "pregnancy",
        "veteran_status",
        "age",
        "date_of_birth",
        "dob",
        "citizenship",
        "immigration_status",
        "genetic_information",
        "demographics",
        "eeo",
        "protected_disclosures",
    }
)


def strip_protected_disclosures(payload: Any) -> Any:
    if isinstance(payload, dict):
        cleaned: dict[str, Any] = {}
        for key, value in payload.items():
            if str(key).strip().lower() in PROTECTED_DISCLOSURE_KEYS:
                continue
            cleaned[key] = strip_protected_disclosures(value)
        return cleaned
    if isinstance(payload, list):
        return [strip_protected_disclosures(item) for item in payload]
    return payload
