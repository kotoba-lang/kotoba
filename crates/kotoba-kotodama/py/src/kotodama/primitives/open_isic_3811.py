from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_3811_classify(**kwargs: Any) -> dict[str, Any]:
    """Collection of non-hazardous waste.

    This class includes the collection of non-hazardous solid or non-solid waste, including mixed materials.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "3811":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 3811."}
    return await task_open_isic_classify_entity(**kwargs)
