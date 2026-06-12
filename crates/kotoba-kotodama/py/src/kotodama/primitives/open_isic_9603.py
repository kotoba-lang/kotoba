from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_9603_classify(**kwargs: Any) -> dict[str, Any]:
    """Funeral and related activities

    This class includes the activities of funeral homes and funeral parlors.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "9603":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 9603."}
    return await task_open_isic_classify_entity(**kwargs)
