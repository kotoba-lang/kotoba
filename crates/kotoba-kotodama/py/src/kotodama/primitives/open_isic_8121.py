from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_8121_classify(**kwargs: Any) -> dict[str, Any]:
    """General cleaning of buildings

    This class includes the cleaning of all types of buildings, such as offices, factories, shops, institutions and other business and professional premises and multiunit residential buildings.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "8121":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 8121."}
    return await task_open_isic_classify_entity(**kwargs)
