from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_9499_classify(**kwargs: Any) -> dict[str, Any]:
    """Activities of other membership organizations n.e.c.

    This class includes the activities of other membership organizations not elsewhere classified.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "9499":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 9499."}
    return await task_open_isic_classify_entity(**kwargs)
