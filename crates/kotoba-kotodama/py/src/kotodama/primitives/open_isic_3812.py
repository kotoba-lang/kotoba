from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_3812_classify(**kwargs: Any) -> dict[str, Any]:
    """Collection of hazardous waste.

    This class includes the collection of solid or non-solid hazardous waste, e.g. explosive, oxidizing, flammable, toxic, irritant, carcinogenic, corrosive or infectious materials.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "3812":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 3812."}
    return await task_open_isic_classify_entity(**kwargs)
