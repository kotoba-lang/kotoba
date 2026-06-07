from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_2812_classify(**kwargs: Any) -> dict[str, Any]:
    """Manufacture of fluid power equipment.

    This class includes the manufacture of hydraulic and pneumatic components and systems.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "2812":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 2812."}
    return await task_open_isic_classify_entity(**kwargs)
