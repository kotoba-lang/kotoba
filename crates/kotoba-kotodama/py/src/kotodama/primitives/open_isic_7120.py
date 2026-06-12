from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_7120_classify(**kwargs: Any) -> dict[str, Any]:
    """Technical testing and analysis

    This class includes the performance of physical, chemical and other analytical testing of all types of materials and products.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "7120":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 7120."}
    return await task_open_isic_classify_entity(**kwargs)
