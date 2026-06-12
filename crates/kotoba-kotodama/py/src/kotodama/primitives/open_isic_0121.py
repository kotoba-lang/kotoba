from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0121_classify(**kwargs: Any) -> dict[str, Any]:
    """Growing of grapes

    This class includes the growing of grapes in vineyards, for wine and for table consumption.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0121":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0121."}
    return await task_open_isic_classify_entity(**kwargs)
