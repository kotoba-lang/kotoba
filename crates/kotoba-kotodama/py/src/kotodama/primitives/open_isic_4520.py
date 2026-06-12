from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_4520_classify(**kwargs: Any) -> dict[str, Any]:
    """Maintenance and repair of motor vehicles

    This class includes the maintenance and repair of motor vehicles.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "4520":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 4520."}
    return await task_open_isic_classify_entity(**kwargs)
