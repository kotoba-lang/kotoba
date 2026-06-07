from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_3319_classify(**kwargs: Any) -> dict[str, Any]:
    """Repair of other equipment.

    This class includes the repair and maintenance of equipment not elsewhere classified.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "3319":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 3319."}
    return await task_open_isic_classify_entity(**kwargs)
