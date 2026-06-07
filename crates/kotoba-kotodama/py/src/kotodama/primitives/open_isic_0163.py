from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_0163_classify(**kwargs: Any) -> dict[str, Any]:
    """Post-harvest crop activities.

    This class includes post-harvest crop activities aimed at preparing agricultural products for the primary market.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "0163":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 0163."}
    return await task_open_isic_classify_entity(**kwargs)
