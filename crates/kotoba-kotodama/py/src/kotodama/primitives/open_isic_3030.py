from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_3030_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of air and spacecraft and related machinery.

    This class includes the manufacture of airplanes, helicopters, spacecraft and related machinery and equipment.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "3030":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 3030."}
    return await task_open_isic_classify_entity(**kwargs)
