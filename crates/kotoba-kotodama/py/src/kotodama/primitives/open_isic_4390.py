from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4390_classify(**kwargs: Any) -> dict[str, Any]:
    """Other specialised construction activities.

    This class includes specialised construction activities not elsewhere classified.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4390":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4390."}
    return await task_open_isic_classify_entity(**kwargs)
