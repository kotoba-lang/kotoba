from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_6630_classify(**kwargs: Any) -> dict[str, Any]:
    """Fund management activities.

    This class includes portfolio management and related investment advisory activities.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "6630":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 6630."}
    return await task_open_isic_classify_entity(**kwargs)
