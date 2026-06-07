from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_3530_classify(**kwargs: Any) -> dict[str, Any]:
    """Steam and air conditioning supply.

    This class includes the provision of steam, hot water and air conditioning from a central source.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "3530":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 3530."}
    return await task_open_isic_classify_entity(**kwargs)
