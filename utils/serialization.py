from __future__ import annotations

from datetime import date, datetime
from typing import Any


def serialize_value(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, dict):
        return {str(k): serialize_value(v) for k, v in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [serialize_value(item) for item in value]

    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return serialize_value(to_dict())

    if hasattr(value, "__dict__"):
        return serialize_value(vars(value))

    return value
