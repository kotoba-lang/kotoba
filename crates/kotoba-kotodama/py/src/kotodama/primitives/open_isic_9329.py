from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_9329_classify(**kwargs: Any) -> dict[str, Any]:
    """Other amusement and recreation activities n.e.c.

    This class includes other amusement and recreation activities not elsewhere classified.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "9329":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 9329."}
    return await task_open_isic_classify_entity(**kwargs)
