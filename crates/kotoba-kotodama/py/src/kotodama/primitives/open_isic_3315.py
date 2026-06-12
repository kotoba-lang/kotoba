from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_3315_classify(**kwargs: Any) -> dict[str, Any]:
    """Repair of transport equipment, except motor vehicles.

    This class includes the repair and maintenance of transport equipment other than motor vehicles.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "3315":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 3315."}
    return await task_open_isic_classify_entity(**kwargs)
