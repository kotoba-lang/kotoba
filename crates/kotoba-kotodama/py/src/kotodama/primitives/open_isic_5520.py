from typing import Any
from kotodama.primitives.open_isic import task_open_isic_classify_entity


async def task_open_isic_5520_classify(**kwargs: Any) -> dict[str, Any]:
    """Camping grounds, recreational vehicle parks and trailer parks

    This class includes the provision of accommodation in campgrounds, trailer parks and recreational camps.
    """
    code = kwargs.get("isicClassCode", "")
    if code != "5520":
        return {"ok": False, "error": f"Invalid ISIC code {code}. Expected exact match for 5520."}
    return await task_open_isic_classify_entity(**kwargs)
