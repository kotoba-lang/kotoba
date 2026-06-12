from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_7990_classify(**kwargs: Any) -> dict[str, Any]:
    """Other reservation service and related activities

    This class includes other reservation services not elsewhere classified.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "7990":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 7990."}
    return await task_open_isic_classify_entity(**kwargs)
