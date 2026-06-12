from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_6190_classify(**kwargs: Any) -> dict[str, Any]:
    """Other telecommunications activities.

    This class includes other telecommunications activities not elsewhere classified.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "6190":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 6190."}
    return await task_open_isic_classify_entity(**kwargs)
