from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2930_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of parts and accessories for motor vehicles.

    This class includes the manufacture of parts, components and accessories for motor vehicles.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2930":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2930."}
    return await task_open_isic_classify_entity(**kwargs)
