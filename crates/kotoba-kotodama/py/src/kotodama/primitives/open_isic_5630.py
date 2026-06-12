from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_5630_classify(**kwargs: Any) -> dict[str, Any]:
    """Beverage serving activities

    This class includes the preparation and serving of beverages for immediate consumption on the premises.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "5630":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 5630."}
    return await task_open_isic_classify_entity(**kwargs)
