from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2593_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of cutlery, hand tools and general hardware.

    This class includes the manufacture of cutlery, hand tools and general hardware of metal.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2593":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2593."}
    return await task_open_isic_classify_entity(**kwargs)
