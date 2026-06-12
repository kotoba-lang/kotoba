from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_9529_classify(**kwargs: Any) -> dict[str, Any]:
    """Repair of other personal and household goods

    This class includes the repair of personal and household goods not elsewhere classified.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "9529":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 9529."}
    return await task_open_isic_classify_entity(**kwargs)
