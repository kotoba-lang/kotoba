from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_9319_classify(**kwargs: Any) -> dict[str, Any]:
    """Other sports activities

    This class includes the activities of other sports activities not elsewhere classified.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "9319":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 9319."}
    return await task_open_isic_classify_entity(**kwargs)
