from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2814_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of bearings, gears, gearing and driving elements.

    This class includes the manufacture of ball and roller bearings, gears and gearing, and power transmission equipment.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2814":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2814."}
    return await task_open_isic_classify_entity(**kwargs)
