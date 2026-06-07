from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_8510_classify(**kwargs: Any) -> dict[str, Any]:
    """Pre-primary and primary education

    This class includes pre-primary and primary education activities.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "8510":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 8510."}
    return await task_open_isic_classify_entity(**kwargs)
